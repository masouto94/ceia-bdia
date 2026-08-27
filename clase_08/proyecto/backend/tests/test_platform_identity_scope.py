"""Declarative identity-scope migration contracts."""

import unittest
from pathlib import Path


MIGRATION = Path(__file__).resolve().parents[1] / "migrations/versions/20260330_16_platform_identity_scope.py"


class PlatformIdentityScopeTests(unittest.TestCase):
    def test_scope_is_immutable_and_cross_scope_relationships_are_constrained(self) -> None:
        source = MIGRATION.read_text(encoding="utf-8")
        self.assertIn("account_scope", source)
        self.assertIn("users_account_scope_immutable", source)
        self.assertIn("users_scope_key", source)
        self.assertIn("memberships_tenant_identity", source)
        self.assertIn("platform_admins_platform_identity", source)
        self.assertIn("sessions_scope_shape", source)

    def test_revision_defers_temporary_create_until_it_transfers_a_real_function(self) -> None:
        source = MIGRATION.read_text(encoding="utf-8")
        self.assertNotIn("GRANT CREATE ON SCHEMA public TO session_issuer_owner", source)
        self.assertNotIn("REVOKE CREATE ON SCHEMA public FROM session_issuer_owner", source)
        self.assertNotIn("ownership transfer postcondition failed", source)
        self.assertIn("exact function ownership transfer is deferred", source)

    def test_upgrade_and_downgrade_have_a_linked_revision(self) -> None:
        source = MIGRATION.read_text(encoding="utf-8")
        self.assertIn('down_revision = "20260330_15"', source)
        self.assertIn("def upgrade", source)
        self.assertIn("def downgrade", source)


if __name__ == "__main__":
    unittest.main()
