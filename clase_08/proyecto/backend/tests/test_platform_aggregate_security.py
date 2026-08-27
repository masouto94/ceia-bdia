"""Contracts for bounded platform aggregate reads and actor-derived platform audit."""

import os
import unittest
from pathlib import Path

from sqlalchemy import create_engine, text


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "migrations/versions/20260330_19_platform_read_functions.py"
PLATFORM = ROOT / "app/api/platform.py"
CLI = ROOT / "app/cli/seed_platform_admin.py"

FORBIDDEN_COLUMNS = (
    "object_key", "password_hash", "output_summary", "input_summary", "embedding", "chunk",
)


class PlatformAggregateMigrationTests(unittest.TestCase):
    def test_functions_are_owned_by_platform_read_owner_and_fixed(self) -> None:
        source = MIGRATION.read_text(encoding="utf-8")
        self.assertIn('down_revision = "20260330_18"', source)
        self.assertIn("SET ROLE platform_read_owner", source)
        for fn in (
            "platform_read_actor(p_proof varchar) RETURNS uuid",
            "platform_dashboard_summary(p_proof varchar)",
            "platform_tenant_overview(p_proof varchar, p_search varchar, p_limit integer, p_offset integer)",
            "platform_tenant_detail(p_proof varchar, p_tenant uuid)",
        ):
            self.assertIn(fn, source)
        self.assertEqual(source.count("SECURITY DEFINER"), source.count("SET search_path = pg_catalog, public"))
        self.assertNotIn("EXECUTE format", source)
        self.assertNotIn("|| p_action", source)

    def test_public_and_app_runtime_acls_are_exact(self) -> None:
        source = MIGRATION.read_text(encoding="utf-8")
        self.assertIn("REVOKE ALL ON FUNCTION public.platform_read_actor(varchar) FROM PUBLIC", source)
        self.assertNotIn("GRANT EXECUTE ON FUNCTION public.platform_read_actor(varchar) TO app_runtime", source)
        for fn in (
            "public.platform_dashboard_summary(varchar)",
            "public.platform_tenant_overview(varchar,varchar,integer,integer)",
            "public.platform_tenant_detail(varchar,uuid)",
        ):
            self.assertIn(f"REVOKE ALL ON FUNCTION {fn} FROM PUBLIC", source)
            self.assertIn(f"GRANT EXECUTE ON FUNCTION {fn} TO app_runtime", source)

    def test_pagination_is_bounded_server_side(self) -> None:
        source = MIGRATION.read_text(encoding="utf-8")
        self.assertIn("LEAST(GREATEST(COALESCE(p_limit,20),1),50)", source)
        self.assertIn("GREATEST(COALESCE(p_offset,0),0)", source)
        self.assertIn("char_length(v_search) > 120", source)

    def test_no_forbidden_content_columns_are_selected(self) -> None:
        source = MIGRATION.read_text(encoding="utf-8")
        functions_block = source[source.index("CREATE FUNCTION public.platform_read_actor"):source.index("RESET ROLE;\n      SET ROLE project_owner;\n      REVOKE CREATE ON SCHEMA public FROM platform_read_owner")]
        for forbidden in FORBIDDEN_COLUMNS:
            self.assertNotIn(forbidden, functions_block)

    def test_exposed_projections_never_return_session_material(self) -> None:
        source = MIGRATION.read_text(encoding="utf-8")
        for signature in (
            "platform_dashboard_summary(p_proof varchar)\n      RETURNS TABLE(",
            "platform_tenant_overview(p_proof varchar, p_search varchar, p_limit integer, p_offset integer)\n      RETURNS TABLE(",
            "platform_tenant_detail(p_proof varchar, p_tenant uuid)\n      RETURNS TABLE(",
        ):
            start = source.index(signature) + len(signature)
            projection = source[start : source.index(")", start)]
            for forbidden in ("token_hash", "csrf_hash", "password_hash", "session_proof", "user_id uuid"):
                self.assertNotIn(forbidden, projection)

    def test_platform_login_and_logout_audit_are_actor_derived_and_fixed(self) -> None:
        source = MIGRATION.read_text(encoding="utf-8")
        self.assertIn("'platform.login','success',NULL,'{}'::jsonb", source)
        self.assertIn("'platform.logout','success',NULL,'{}'::jsonb", source)
        self.assertIn("RETURNING user_id INTO v_user", source)
        # Logout derives the actor from the matched session row, never from a caller-supplied id.
        self.assertNotIn("VALUES(gen_random_uuid(),p_token", source)
        self.assertIn("action IN ('platform.login', 'platform.logout')", source)

    def test_downgrade_preserves_post_use_audit_and_identity_evidence(self) -> None:
        source = MIGRATION.read_text(encoding="utf-8")
        downgrade = source[source.index("def downgrade"):]
        self.assertIn("post-use downgrade is disabled", downgrade)
        self.assertIn("EXISTS (SELECT 1 FROM public.platform_admins)", downgrade)
        self.assertNotIn("DELETE FROM public.audit_events", downgrade)
        self.assertNotIn("DROP TABLE", downgrade)


class PlatformRouteAggregateTests(unittest.TestCase):
    def test_new_routes_are_proof_gated_and_avoid_forbidden_path_names(self) -> None:
        source = PLATFORM.read_text(encoding="utf-8")
        self.assertIn('"/summary"', source)
        self.assertIn('"/tenant-overview"', source)
        self.assertIn('"/tenant-overview/{tenant_id}"', source)
        for forbidden in ("dashboard", "tenants", "aggregate", "audit-events"):
            self.assertNotIn(f'"/{forbidden}"', source)
        for route in ("def summary", "def tenant_overview", "def tenant_overview_detail"):
            self.assertIn(route, source)
        after_logout = source[source.index("def logout"):]
        self.assertNotIn("actor_id", after_logout)
        self.assertNotIn("session_id", after_logout)
        for fn_name in ("def summary", "def tenant_overview", "def tenant_overview_detail"):
            body = source[source.index(fn_name):]
            body = body[: body.index("\n\n\n")] if "\n\n\n" in body else body
            self.assertIn("_platform_session(db,", body)

    def test_pagination_query_params_are_declaratively_bounded(self) -> None:
        source = PLATFORM.read_text(encoding="utf-8")
        self.assertIn("Query(max_length=120)", source)
        self.assertIn("Query(ge=1, le=_MAX_PAGE_SIZE)", source)
        self.assertIn("Query(ge=0)", source)


class PlatformCliAuditTests(unittest.TestCase):
    def test_rotate_and_disable_persist_actorless_fixed_audit_events(self) -> None:
        source = CLI.read_text(encoding="utf-8")
        self.assertIn("'platform.credential_rotated','success'", source)
        self.assertIn("'platform.admin_disabled','success'", source)
        self.assertIn("actor_id,tenant_id,action,outcome,resource,metadata", source)
        # No raw email, password, or hash may enter the audit resource/metadata.
        rotate_block = source[source.index("platform.credential_rotated") - 200 : source.index("platform.credential_rotated") + 200]
        self.assertNotIn("args.email", rotate_block)
        self.assertNotIn("password_hash", rotate_block[rotate_block.index("VALUES") :] if "VALUES" in rotate_block else rotate_block)


DATABASE_URL = os.getenv("TEST_DATABASE_URL", "")


@unittest.skipUnless(DATABASE_URL, "set TEST_DATABASE_URL to probe platform aggregate grants directly")
class PlatformAggregateLiveGrantTests(unittest.TestCase):
    """Runs only against the runtime (app_runtime) credential exposed by verify-stack.sh.

    This intentionally does not attempt to bootstrap a platform admin: app_runtime holds no
    INSERT authority on platform_admins/sessions (by design), so a full end-to-end proof needs
    the admin-tools CLI plus the running API's HTTP surface. This probe proves the safer, always
    -available half: an invalid/absent proof is rejected before any aggregate row is returned.
    """

    _ZERO_DIGEST = "0" * 64

    @classmethod
    def setUpClass(cls) -> None:
        cls.engine = create_engine(DATABASE_URL, pool_size=1, max_overflow=0)

    def test_invalid_proof_returns_no_aggregate_rows(self) -> None:
        with self.engine.begin() as connection:
            with self.assertRaises(Exception):
                connection.execute(
                    text("SELECT * FROM public.platform_dashboard_summary(:proof)"), {"proof": self._ZERO_DIGEST}
                )

    def test_app_runtime_cannot_select_platform_read_owner_helper(self) -> None:
        with self.engine.begin() as connection:
            with self.assertRaises(Exception):
                connection.execute(
                    text("SELECT public.platform_read_actor(:proof)"), {"proof": self._ZERO_DIGEST}
                )


if __name__ == "__main__":
    unittest.main()
