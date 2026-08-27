"""Audit read-model and storage contract checks."""

# pyright: reportArgumentType=false, reportCallIssue=false
# Pydantic accepts validation aliases dynamically; this test exercises those aliases.

import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4
from unittest.mock import patch

_ENVIRONMENT = {
    "RUNTIME_DATABASE_URL": "postgresql+psycopg://runtime:password@db/student_project",
    "AUTH_DATABASE_URL": "postgresql+psycopg://auth:password@db/student_project",
    "ASSISTANT_DATABASE_URL": "postgresql+psycopg://assistant:password@db/student_project",
    "MINIO_ACCESS_KEY": "local-user", "MINIO_SECRET_KEY": "local-password",
    "SMTP_FROM": "noreply@example.test", "SESSION_SECRET": "test-session-secret",
    "RECOVERY_TOKEN_SECRET": "test-recovery-secret",
}


class AuditContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.environment = patch.dict("os.environ", _ENVIRONMENT, clear=False)
        cls.environment.start()

    @classmethod
    def tearDownClass(cls):
        cls.environment.stop()

    def test_migration_protects_append_only_audit_storage(self):
        source = Path("migrations/versions/20260330_14_audit_module.py").read_text()
        for invariant in (
            "ENABLE ROW LEVEL SECURITY", "FORCE ROW LEVEL SECURITY",
            "audit_events_tenant_admin_select", "reject_historical_mutation",
            "REVOKE INSERT, UPDATE, DELETE ON audit_events FROM app_runtime",
            "append_audit_event", "SECURITY DEFINER", "SET search_path = public",
            "ingestion_runs_append_only", "REVOKE UPDATE, DELETE ON ingestion_runs FROM app_runtime",
        ):
            self.assertIn(invariant, source)

    def test_audit_query_is_bounded_and_uses_normalized_union(self):
        from app.api.audit import AuditQuery
        from app.repositories.audit import AUDIT_EVENTS_SQL

        self.assertEqual(AuditQuery().per_page, 25)
        self.assertEqual(AuditQuery(page=2, per_page=50).offset, 50)
        with self.assertRaises(ValueError):
            AuditQuery(per_page=30)
        with self.assertRaises(ValueError):
            AuditQuery(from_at=datetime.now(UTC) - timedelta(days=32), to_at=datetime.now(UTC))  # pyright: ignore[reportCallIssue] -- Pydantic accepts legacy validation aliases at runtime
        for source in ("audit_events", "experiment_status_transitions", "ingestion_runs", "UNION ALL", "ESCAPE"):
            self.assertIn(source, AUDIT_EVENTS_SQL)

    def test_date_only_ranges_are_inclusive_and_datetime_endpoints_are_exclusive(self):
        from app.api.audit import AuditQuery
        from app.repositories.audit import AUDIT_EVENTS_SQL

        # Pyright cannot model Pydantic's runtime alias parsing for from/to.
        date_only = AuditQuery(**{"from": "2026-01-01", "to": "2026-01-31"})  # pyright: ignore[reportArgumentType]
        self.assertEqual(date_only.from_at, datetime(2026, 1, 1, tzinfo=UTC))
        self.assertEqual(date_only.to_at, datetime(2026, 2, 1, tzinfo=UTC))
        self.assertIn("e.occurred_at < :to_at", AUDIT_EVENTS_SQL)
        self.assertNotIn("e.occurred_at <= :to_at", AUDIT_EVENTS_SQL)

        exact = AuditQuery(**{"from": datetime(2026, 1, 1, 12, tzinfo=UTC), "to": datetime(2026, 1, 1, 13, tzinfo=UTC)})  # pyright: ignore[reportCallIssue, reportArgumentType]
        self.assertEqual(exact.to_at, datetime(2026, 1, 1, 13, tzinfo=UTC))
        with self.assertRaises(ValueError):
            AuditQuery(**{"from": "2026-01-01", "to": "2026-02-01"})  # pyright: ignore[reportArgumentType]
        AuditQuery(**{"from": "2026-01-01", "to": "2026-01-31"})  # pyright: ignore[reportArgumentType]

        with self.assertRaises(ValueError):
            AuditQuery(**{"from": datetime(2026, 1, 1, tzinfo=UTC), "to": datetime(2026, 2, 1, 0, 0, 1, tzinfo=UTC)})  # pyright: ignore[reportArgumentType]

    def test_migration_15_binds_definer_calls_to_request_context_and_restores_revision_14_on_downgrade(self):
        repair = Path("migrations/versions/20260330_15_audit_rls_repair.py").read_text()
        revision_14 = Path("migrations/versions/20260330_14_audit_module.py").read_text()
        for invariant in (
            "p_tenant IS DISTINCT FROM NULLIF(current_setting('app.tenant_id', true), '')::uuid",
            "p_actor IS DISTINCT FROM NULLIF(current_setting('app.user_id', true), '')::uuid",
            "p_actor IS NOT NULL", "p_action <> 'auth.recovery.request'", "p_outcome NOT IN ('success', 'rate_limited')",
        ):
            self.assertIn(invariant, repair)
        downgrade = repair.split("def downgrade() -> None:", 1)[1]
        for definition in (
            "CREATE POLICY audit_events_definer_insert ON audit_events FOR INSERT WITH CHECK (true)",
            "CREATE OR REPLACE FUNCTION append_audit_event(",
            "CREATE OR REPLACE FUNCTION recovery_request_count",
        ):
            self.assertIn(definition, downgrade)
            self.assertIn(definition, revision_14)

    def test_repository_counts_an_empty_out_of_range_page(self):
        from app.repositories.audit import AuditRepository

        class Database:
            def __init__(self) -> None:
                self.calls = 0

            def execute(self, statement: object, values: dict):
                self.calls += 1
                if self.calls == 1:
                    return type("Result", (), {"mappings": lambda self: type("Mappings", (), {"all": lambda self: []})()})()
                return type("Result", (), {"scalar_one": lambda self: 3})()

        items, total = AuditRepository(Database()).list(  # type: ignore[arg-type, reportCallIssue]
            uuid4(), page=9, per_page=10, from_at=datetime.now(UTC) - timedelta(days=1),
            to_at=datetime.now(UTC), actor_id=None, action=None, outcome=None, search="",
        )
        self.assertEqual(items, [])
        self.assertEqual(total, 3)

    def test_audit_helper_uses_definer_function_only(self):
        from app.audit import append_audit_event
        self.assertTrue(callable(append_audit_event))
        source = Path("app/audit.py").read_text()
        self.assertIn("SELECT append_audit_event", source)
        self.assertNotIn("INSERT INTO audit_events", source)

    def test_audit_route_is_registered(self):
        from app.main import app
        methods = {(getattr(route, "path", ""), method) for route in app.routes for method in getattr(route, "methods", set())}
        self.assertIn(("/api/audit-events", "GET"), methods)


if __name__ == "__main__":
    unittest.main()
