"""RED contracts for isolated post-password session issuance."""

import os
import unittest
from pathlib import Path

os.environ.update({
    "RUNTIME_DATABASE_URL": "postgresql+psycopg://runtime:password@db/student_project",
    "AUTH_DATABASE_URL": "postgresql+psycopg://auth:password@db/student_project",
    "ASSISTANT_DATABASE_URL": "postgresql+psycopg://assistant:password@db/student_project",
    "MINIO_ACCESS_KEY": "local-user", "MINIO_SECRET_KEY": "local-password",
    "SMTP_FROM": "noreply@example.test", "SESSION_SECRET": "test-session-secret",
    "RECOVERY_TOKEN_SECRET": "test-recovery-secret",
})


class SessionIssuanceSecurityTests(unittest.TestCase):
    def test_issuer_is_private_and_auth_runtime_only_after_password_verification(self) -> None:
        auth = Path("app/api/auth.py").read_text(encoding="utf-8")
        issuer = Path("app/security/session_issuer.py")
        migration = Path("migrations/versions/20260330_17_session_proof_rls.py")
        self.assertTrue(issuer.exists())
        self.assertTrue(migration.exists())
        source = issuer.read_text(encoding="utf-8")
        sql = migration.read_text(encoding="utf-8")
        self.assertIn("AuthSessionLocal", source)
        self.assertIn("issue_tenant_session", source)
        self.assertIn("verify_password(payload.password", auth)
        login = auth[auth.index("def login("):auth.index("@router.get(\"/auth/session\")")]
        self.assertLess(login.index("verify_password(payload.password"), login.index("_mint_tenant_session"))
        self.assertNotIn("INSERT INTO sessions", auth)
        self.assertIn("session_issuer_owner", sql)
        self.assertIn("GRANT EXECUTE ON FUNCTION public.issue_tenant_session", sql)
        self.assertIn("REVOKE ALL ON sessions FROM auth_runtime", sql)
        self.assertIn("REVOKE ALL ON sessions FROM app_runtime", sql)
        self.assertIn("CREATE POLICY memberships_session_issuer_lookup", sql)
        self.assertIn("GRANT SELECT ON public.users, public.memberships, public.sessions, public.recovery_tokens TO session_issuer_owner", sql)
        self.assertIn("GRANT INSERT, UPDATE ON public.sessions TO session_issuer_owner", sql)

    def test_logout_is_proof_and_csrf_bound_without_caller_selected_session(self) -> None:
        source = Path("app/api/auth.py").read_text(encoding="utf-8")
        self.assertIn("revoke_own_session", source)
        self.assertNotIn("UPDATE sessions SET revoked_at=now() WHERE id=:id", source)

    def test_recovery_revocation_derives_its_target_from_the_recovery_proof(self) -> None:
        source = Path("app/api/auth.py").read_text(encoding="utf-8")
        migration = Path("migrations/versions/20260330_17_session_proof_rls.py").read_text(encoding="utf-8")
        recovery = source[source.index("def recovery_confirm("):source.index("@router.get(\"/members\")")]
        self.assertIn("public.revoke_recovery_sessions(:proof)", recovery)
        self.assertNotIn("UPDATE sessions SET revoked_at", recovery)
        self.assertIn("CREATE FUNCTION public.revoke_recovery_sessions(p_token varchar)", migration)
        self.assertIn("GRANT EXECUTE ON FUNCTION public.revoke_recovery_sessions(varchar) TO app_runtime", migration)

    def test_login_audit_restores_derived_tenant_context_before_auditing(self) -> None:
        source = Path("app/api/auth.py").read_text(encoding="utf-8")
        login = source[source.index("def login("):source.index("@router.get(\"/auth/session\")")]
        tenant_lookup = login.index("sole_active_membership_tenant")
        audit = login.index('_audit(db, "login"')
        self.assertIn("set_config('app.tenant_id', :value, true)", login[tenant_lookup:audit])

    def test_runtime_session_resolution_uses_only_a_digest_bound_definer_resolver(self) -> None:
        source = Path("app/api/auth.py").read_text(encoding="utf-8")
        self.assertIn("SELECT * FROM public.resolve_runtime_session(:proof)", source)
        self.assertIn('{"proof": digest}', source)
        self.assertNotIn("FROM sessions WHERE token_hash=:hash", source)
        self.assertNotIn("csrf_hash", source[source.index("def _session"):source.index("def _csrf")])

    def test_registration_bootstrap_is_auth_only_and_cannot_use_runtime_writes(self) -> None:
        auth = Path("app/api/auth.py").read_text(encoding="utf-8")
        issuer = Path("app/security/session_issuer.py").read_text(encoding="utf-8")
        migration = Path("migrations/versions/20260330_17_session_proof_rls.py").read_text(encoding="utf-8")
        register = auth[auth.index("def register("):auth.index("@router.post(\"/auth/login\")")]
        self.assertIn("register_tenant_bootstrap", register)
        self.assertNotIn("INSERT INTO users", register)
        self.assertNotIn("INSERT INTO tenants", register)
        self.assertIn("AuthSessionLocal", issuer)
        self.assertIn("def register_tenant_bootstrap", issuer)
        self.assertIn("CREATE FUNCTION public.register_tenant_bootstrap", migration)
        self.assertIn("SECURITY DEFINER", migration)
        self.assertIn("GRANT EXECUTE ON FUNCTION public.register_tenant_bootstrap", migration)
        self.assertIn("TO auth_runtime", migration)
        self.assertIn("REVOKE ALL ON FUNCTION public.register_tenant_bootstrap", migration)


if __name__ == "__main__":
    unittest.main()
