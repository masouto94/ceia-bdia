"""Static contracts for least-privilege PostgreSQL role provisioning."""

import unittest
from pathlib import Path


PROJECT = Path(__file__).resolve().parents[2]
ROLES = PROJECT / "infra/postgres/00-create-roles.sh"
RECONCILE = PROJECT / "infra/postgres/01-ensure-platform-roles.sql"
FOUNDATION_MIGRATION = PROJECT / "backend/migrations/versions/20260330_01_mvp_rls_foundation.py"


class DatabaseRoleMatrixTests(unittest.TestCase):
    def test_bootstrap_requires_five_distinct_secret_domains_without_echoing_them(self) -> None:
        source = ROLES.read_text(encoding="utf-8")
        for variable in (
            "POSTGRES_PASSWORD", "PROJECT_MIGRATOR_PASSWORD", "APP_RUNTIME_PASSWORD",
            "AUTH_RUNTIME_PASSWORD", "ASSISTANT_READER_PASSWORD",
        ):
            self.assertIn(variable, source)
        self.assertIn("credential values must be pairwise distinct", source)
        self.assertIn("\\getenv", source)
        self.assertNotIn("set -x", source)

    def test_roles_are_noinherit_and_memberships_are_set_only(self) -> None:
        source = ROLES.read_text(encoding="utf-8")
        for role in ("project_owner", "project_migrator", "app_runtime", "auth_runtime", "assistant_reader", "session_issuer_owner", "platform_read_owner"):
            self.assertIn(f"CREATE ROLE {role}", source)
        self.assertGreaterEqual(source.count("NOINHERIT"), 7)
        self.assertLess(
            source.index("CREATE ROLE project_migrator"),
            source.index("GRANT USAGE, CREATE ON SCHEMA public TO project_migrator"),
        )
        for edge in (
            "GRANT project_owner TO project_migrator WITH ADMIN FALSE, INHERIT FALSE, SET TRUE",
            "GRANT session_issuer_owner TO project_owner WITH ADMIN FALSE, INHERIT FALSE, SET TRUE",
            "GRANT platform_read_owner TO project_owner WITH ADMIN FALSE, INHERIT FALSE, SET TRUE",
        ):
            self.assertIn(edge, source)

    def test_fresh_migration_keeps_owner_authority_for_foundation_grants(self) -> None:
        source = FOUNDATION_MIGRATION.read_text(encoding="utf-8")
        self.assertLess(
            source.index('op.execute("GRANT USAGE ON SCHEMA public'),
            source.index('op.execute("RESET ROLE")'),
        )
        self.assertNotIn("ON ALL TABLES IN SCHEMA public", source)

    def test_existing_volume_reconciliation_validates_all_credential_pairs_before_mutation(self) -> None:
        source = RECONCILE.read_text(encoding="utf-8")
        self.assertIn("pg_advisory_xact_lock", source)
        self.assertIn("credentials_valid", source)
        self.assertIn("(1 / 0)::text", source)
        self.assertLess(source.index("credentials_valid"), source.index("BEGIN;"))
        self.assertEqual(source.count(" IS DISTINCT FROM "), 10)
        self.assertNotIn("RAISE NOTICE", source)

    def test_reconciliation_caller_fails_closed_before_psql(self) -> None:
        compose = (PROJECT / "compose.yaml").read_text(encoding="utf-8")
        reconcile = compose[compose.index("  db-role-reconcile:\n") : compose.index("  pgadmin:\n")]
        self.assertIn("credential contract rejected", reconcile)
        self.assertLess(reconcile.index("credential contract rejected"), reconcile.index("psql --host=db"))


if __name__ == "__main__":
    unittest.main()
