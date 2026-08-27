"""Focused static and unit proof for guarded read-only Text-to-SQL."""

# pyright: reportMissingImports=false

import os
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import Mock, patch
from uuid import uuid4

from sqlalchemy.sql import Select

os.environ.update({
    "RUNTIME_DATABASE_URL": "postgresql+psycopg://runtime:password@db/student_project",
    "AUTH_DATABASE_URL": "postgresql+psycopg://auth:password@db/student_project",
    "ASSISTANT_DATABASE_URL": "postgresql+psycopg://assistant:password@db/student_project",
    "MINIO_ACCESS_KEY": "local-user", "MINIO_SECRET_KEY": "local-password",
    "SMTP_FROM": "noreply@example.test", "SESSION_SECRET": "test-session-secret",
    "RECOVERY_TOKEN_SECRET": "test-recovery-secret",
})

from app.assistant.sql import SqlExecutionError, SqlExecutor, SqlGuard, SqlRejected


class ProofContext:
    def __init__(self, user_id=None, tenant_id=None, session_digest="a" * 64):
        self.user_id = user_id or uuid4()
        self.tenant_id = tenant_id or uuid4()
        self.session_digest = session_digest


class FakeResult:
    def __init__(self, rows): self.rows = rows
    def mappings(self): return self
    def all(self): return self.rows


class FakeSession:
    def __init__(self, rows): self.rows, self.executed, self.closed = rows, [], False
    @contextmanager
    def begin(self): yield self
    def execute(self, statement, values=None):
        self.executed.append((statement, values or {}))
        if isinstance(statement, Select): return FakeResult(self.rows)
        return FakeResult([])
    def close(self): self.closed = True


class AssistantSqlTests(unittest.TestCase):
    def test_guard_accepts_only_the_small_curated_select_grammar(self) -> None:
        guard = SqlGuard()
        self.assertEqual(
            set(guard.RELATIONS),
            {"public.assistant_experiments", "public.assistant_results", "public.assistant_metrics"},
        )
        self.assertEqual(
            guard.validate(" SELECT name, status FROM public.assistant_experiments ORDER BY created_at desc "),
            "SELECT name, status FROM public.assistant_experiments ORDER BY created_at DESC",
        )
        rejected = (
            "UPDATE experiments SET name=x", "DROP TABLE experiments",
            "SELECT name FROM public.assistant_experiments; SELECT id FROM public.assistant_results",
            "SELECT name FROM public.assistant_experiments -- evade", "SELECT set_config FROM public.assistant_experiments",
            "SELECT name FROM public.experiments", "SELECT name FROM experiments",
            "SELECT pg_sleep FROM public.assistant_experiments",
            "WITH x AS (DELETE FROM metrics) SELECT name FROM public.assistant_experiments",
            "SELECT * FROM public.assistant_experiments", "SELECT name FROM public.assistant_documents",
            "SELECT name FROM assistant.experiments",
        )
        for query in rejected:
            with self.subTest(query=query), self.assertRaises(SqlRejected): guard.validate(query)

    def test_rejection_and_missing_or_invalid_proof_happen_before_data_access(self) -> None:
        factory = Mock()
        executor = SqlExecutor(factory)
        with self.assertRaises(SqlRejected):
            executor.execute("DELETE FROM experiments", context=ProofContext())
        with self.assertRaises(PermissionError):
            executor.execute("SELECT name FROM public.assistant_experiments", context=ProofContext(session_digest="invalid"))
        factory.assert_not_called()

    def test_executor_uses_allow_list_objects_and_structured_limit(self) -> None:
        guard = SqlGuard()
        session = FakeSession([{"name": "safe", "status": "done"}])
        context = ProofContext()
        result = SqlExecutor(lambda: session, guard).execute(
            "SELECT name, status FROM public.assistant_experiments ORDER BY created_at desc",
            context=context,
        )
        setup_statements = [str(statement) for statement, _ in session.executed[:-1]]
        statement = session.executed[-1][0]
        relation = guard.TABLES["public.assistant_experiments"]

        self.assertEqual(result.query, "SELECT name, status FROM public.assistant_experiments ORDER BY created_at DESC")
        self.assertEqual(result.rows, [{"name": "safe", "status": "done"}])
        self.assertIn("SET TRANSACTION READ ONLY", setup_statements[0])
        self.assertTrue(any("statement_timeout" in value for value in setup_statements))
        self.assertTrue(any("app.session_proof" in value for value in setup_statements))
        self.assertTrue(any("app.account_scope" in value for value in setup_statements))
        self.assertTrue(any("app.tenant_id" in value for value in setup_statements))
        self.assertIsInstance(statement, Select)
        self.assertIs(statement.get_final_froms()[0], relation)
        selected = list(statement.selected_columns)
        self.assertIs(selected[0], relation.c.name)
        self.assertIs(selected[1], relation.c.status)
        ordering = list(statement._order_by_clauses)[0]
        self.assertIs(ordering.element, relation.c.created_at)
        self.assertTrue(str(ordering).endswith(" DESC"))
        compiled = statement.compile()
        self.assertIn(201, compiled.params.values())
        self.assertIn("LIMIT", str(compiled))
        self.assertTrue(session.closed)

    def test_row_and_serialized_output_limits_fail_safely(self) -> None:
        with patch("app.assistant.sql.settings.sql_max_rows", 1):
            with self.assertRaises(SqlExecutionError):
                SqlExecutor(lambda: FakeSession([{"id": 1}, {"id": 2}])).execute(
                    "SELECT id FROM public.assistant_experiments", context=ProofContext())
        with patch("app.assistant.sql.settings.sql_max_result_bytes", 2):
            with self.assertRaises(SqlExecutionError):
                SqlExecutor(lambda: FakeSession([{"name": "large"}])).execute(
                    "SELECT name FROM public.assistant_experiments", context=ProofContext())

    def test_migration_uses_public_curated_views_with_least_privilege(self) -> None:
        migration = Path("migrations/versions/20260330_09_assistant_sql.py").read_text()
        views = "public.assistant_experiments,public.assistant_results,public.assistant_metrics"
        for name in views.split(","):
            self.assertIn(f"CREATE VIEW {name} WITH (security_barrier=true)", migration)
        self.assertNotIn("CREATE SCHEMA", migration)
        self.assertNotIn("DROP SCHEMA", migration)
        self.assertIn("REVOKE ALL ON SCHEMA public FROM assistant_reader", migration)
        base_tables = "public.experiments,public.results,public.metrics,public.documents,public.chunks,public.embeddings"
        revoke_tables = migration.index(f"REVOKE ALL ON {base_tables} FROM assistant_reader")
        self.assertNotIn("REVOKE ALL ON ALL TABLES IN SCHEMA public", migration)
        grant_usage = migration.index("GRANT USAGE ON SCHEMA public TO assistant_reader")
        grant_views = migration.index(f"GRANT SELECT ON {views} TO assistant_reader")
        self.assertLess(revoke_tables, grant_usage)
        self.assertLess(grant_usage, grant_views)
        self.assertIn(f"REVOKE ALL ON {views} FROM PUBLIC", migration)
        self.assertIn(f"REVOKE ALL ON {views} FROM assistant_reader", migration)
        self.assertIn("current_setting('app.tenant_id'", migration)
        self.assertIn("DROP VIEW public.assistant_metrics,public.assistant_results,public.assistant_experiments", migration)


if __name__ == "__main__":
    unittest.main()
