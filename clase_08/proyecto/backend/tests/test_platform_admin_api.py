"""RED contracts for isolated platform administration."""

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PLATFORM = ROOT / "app/api/platform.py"
ISSUER = ROOT / "app/security/session_issuer.py"
MIGRATION = ROOT / "migrations/versions/20260330_18_platform_lifecycle.py"
CLI = ROOT / "app/cli/seed_platform_admin.py"


class PlatformAdminApiTests(unittest.TestCase):
    def test_platform_login_is_generic_and_uses_isolated_issuer(self) -> None:
        source = PLATFORM.read_text(encoding="utf-8")
        issuer = ISSUER.read_text(encoding="utf-8")
        self.assertIn('APIRouter(prefix="/api/platform"', source)
        self.assertIn('"Invalid platform credentials."', source)
        self.assertIn("issue_platform_session", source)
        self.assertIn("def issue_platform_session", issuer)
        self.assertNotIn("tenant_id", source[source.index("def login"):source.index("def logout")])

    def test_platform_logout_requires_current_proof_and_csrf(self) -> None:
        source = PLATFORM.read_text(encoding="utf-8")
        self.assertIn("_csrf", source)
        self.assertIn("revoke_own_session", source)
        self.assertIn("'platform'", source)
        self.assertNotIn("actor_id", source[source.index("def logout"):])
        self.assertNotIn("session_id", source[source.index("def logout"):])

    def test_platform_lifecycle_is_migrator_only_and_atomic(self) -> None:
        migration = MIGRATION.read_text(encoding="utf-8")
        cli = CLI.read_text(encoding="utf-8")
        self.assertIn("issue_platform_session", migration)
        self.assertIn("credential_version", migration)
        self.assertIn("REVOKE ALL ON FUNCTION public.issue_platform_session", migration)
        self.assertIn("TO auth_runtime", migration)
        self.assertIn("platform_admins", migration)
        self.assertNotIn("has_function_privilege('PUBLIC'", migration)
        self.assertLess(migration.index("RESET ROLE;\n      SET ROLE project_owner;\n      REVOKE CREATE"), migration.index("CREATE POLICY audit_events_session_issuer_platform_denial"))
        self.assertIn("--rotate", cli)
        self.assertIn("--disable", cli)
        self.assertIn("getpass", cli)
        self.assertNotIn("add_argument(\"--password\"", cli)

    def test_platform_function_acls_are_changed_by_their_owner_before_final_assertions(self) -> None:
        migration = MIGRATION.read_text(encoding="utf-8")
        acl_start = migration.index("CREATE POLICY audit_events_session_issuer_platform_denial")
        acl_end = migration.index("DO $$ BEGIN", acl_start)
        acl_block = migration[acl_start:acl_end]
        self.assertIn("SET ROLE session_issuer_owner;", acl_block)
        reset_to_owner = "RESET ROLE;\n      SET ROLE project_owner;"
        self.assertIn(reset_to_owner, acl_block)
        self.assertLess(acl_block.index("SET ROLE session_issuer_owner;"), acl_block.index("REVOKE ALL ON FUNCTION"))
        self.assertLess(acl_block.index("GRANT EXECUTE ON FUNCTION public.append_platform_denial() TO app_runtime;"), acl_block.index(reset_to_owner))
        upgrade = migration[migration.index("def upgrade"):migration.index("def downgrade")]
        downgrade = migration[migration.index("def downgrade"):]
        self.assertIn("END $$;\n      RESET ROLE;", upgrade)
        self.assertIn("DROP FUNCTION IF EXISTS public.issue_platform_session(uuid,integer,varchar,varchar,timestamptz);\n      RESET ROLE;", downgrade)


if __name__ == "__main__":
    unittest.main()
