import unittest
from datetime import UTC, datetime, timedelta
from unittest.mock import patch


_ENVIRONMENT = {
    "RUNTIME_DATABASE_URL": "postgresql+psycopg://runtime:password@db/student_project",
    "AUTH_DATABASE_URL": "postgresql+psycopg://auth:password@db/student_project",
    "ASSISTANT_DATABASE_URL": "postgresql+psycopg://assistant:password@db/student_project",
    "MINIO_ACCESS_KEY": "local-user",
    "MINIO_SECRET_KEY": "local-password",
    "SMTP_FROM": "noreply@example.test",
    "SESSION_SECRET": "test-session-secret",
    "RECOVERY_TOKEN_SECRET": "test-recovery-secret",
}


class IdentitySecurityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.environment = patch.dict("os.environ", _ENVIRONMENT, clear=False)
        cls.environment.start()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.environment.stop()

    def test_passwords_and_opaque_tokens_are_not_reversible(self) -> None:
        from app.security.password import hash_password, verify_password
        from app.security.tokens import TokenCodec

        encoded = hash_password("correct horse battery staple")
        self.assertNotEqual(encoded, "correct horse battery staple")
        self.assertTrue(verify_password("correct horse battery staple", encoded))
        self.assertFalse(verify_password("wrong", encoded))
        token = TokenCodec("test-secret").issue()
        self.assertNotEqual(TokenCodec("test-secret").digest(token), token)

    def test_recovery_token_is_expired_or_consumed_once(self) -> None:
        from app.security.tokens import RecoveryToken

        now = datetime.now(UTC)
        valid = RecoveryToken("digest", now + timedelta(minutes=30))
        self.assertTrue(valid.usable(now))
        self.assertFalse(valid.consume(now + timedelta(seconds=1)).usable(now + timedelta(seconds=2)))
        self.assertFalse(RecoveryToken("digest", now - timedelta(seconds=1)).usable(now))

        from app.api.auth import RecoveryRequest, recovery_request

        class Result:
            def scalar_one(self) -> int:
                return 5

        class Database:
            def __init__(self) -> None:
                self.calls: list[tuple[str, dict]] = []

            def execute(self, statement: object, values: dict) -> Result:
                self.calls.append((str(statement), values))
                return Result()

            def commit(self) -> None:
                pass

        database = Database()
        with patch("app.api.auth.send_recovery") as send_recovery:
            response = recovery_request(RecoveryRequest(email="known@example.com"), database)  # type: ignore[arg-type]
        self.assertEqual(response, {"message": "Si la cuenta existe, se enviaron las instrucciones de recuperación."})
        self.assertEqual(len(database.calls), 2)
        self.assertIn("recovery_request_count", database.calls[0][0])
        send_recovery.assert_not_called()

    def test_invalid_email_payloads_are_rejected_before_identity_side_effects(self) -> None:
        from pydantic import ValidationError

        from app.api.auth import LoginPayload, MemberCreate, RecoveryRequest, RegisterPayload

        payloads = (
            lambda: RegisterPayload(email="not-an-email", password="correct-horse", tenant_name="Test Lab"),
            lambda: LoginPayload(email="not-an-email", password="correct-horse"),
            lambda: RecoveryRequest(email="not-an-email"),
            lambda: MemberCreate(email="not-an-email", role="viewer"),
        )
        for build_payload in payloads:
            with self.subTest(payload=build_payload), self.assertRaises(ValidationError):
                build_payload()

    def test_identity_user_facing_messages_are_professional_spanish(self) -> None:
        from pathlib import Path

        source = Path("app/api/auth.py").read_text(encoding="utf-8")
        frontend_source = Path("../frontend/src/api.ts").read_text(encoding="utf-8")
        expected = (
            "Se requiere autenticación.",
            "Falló la validación de seguridad de la solicitud.",
            "Primero seleccioná un espacio de trabajo.",
            "Tu rol no tiene permiso para realizar esta acción.",
            "El correo electrónico ya está registrado.",
            "El correo electrónico o la contraseña no son válidos.",
            "Se requiere una membresía activa en un espacio de trabajo.",
            "Si la cuenta existe, se enviaron las instrucciones de recuperación.",
            "El código de recuperación no es válido o venció.",
            "El rol debe ser administración, integrante o consulta.",
            "La persona ya pertenece a otro espacio de trabajo.",
        )
        retired = (
            "authentication required",
            "CSRF validation failed",
            "select a tenant first",
            "role is not permitted",
            "email is already registered",
            "invalid credentials",
            "an active tenant membership is required",
            "If the account exists, recovery instructions were sent.",
            "invalid or expired recovery token",
            "role must be admin, member, or viewer",
            "user is already attached to another tenant",
        )
        for message in expected:
            self.assertIn(message, source)
        for message in retired:
            self.assertNotIn(message, source)
        self.assertNotIn("response.statusText", frontend_source)
        self.assertNotIn("return issue.msg", frontend_source)

    def test_recovery_email_is_localized(self) -> None:
        from app.providers.mail import send_recovery

        with patch("app.providers.mail.smtplib.SMTP") as smtp:
            send_recovery("person@example.com", "token")
        message = smtp.return_value.__enter__.return_value.send_message.call_args.args[0]
        self.assertEqual(message["Subject"], "Recuperación de contraseña")
        self.assertEqual(message.get_content().strip(), f"Restablecé tu contraseña: {__import__('app.core.config', fromlist=['settings']).settings.web_public_url}/reset-password?token=token")

    def test_member_list_parameters_only_accept_contract_allowlists(self) -> None:
        from pydantic import ValidationError

        from app.api.auth import MemberListParams, _member_list_sql

        valid = MemberListParams(page=2, per_page=20, search="ADMIN@EXAMPLE.COM", role="admin", status="active", sort="created_at:desc")
        sql, values = _member_list_sql(valid)
        self.assertIn("ORDER BY u.created_at DESC, u.email ASC, u.id ASC", sql)
        self.assertEqual(values["search"], "%admin@example.com%")
        self.assertEqual(values["offset"], 20)
        for field, value in (("page", 0), ("per_page", 11), ("role", "owner"), ("status", "pending"), ("sort", "email; DROP TABLE users")):
            with self.subTest(field=field, value=value), self.assertRaises(ValidationError) as error:
                MemberListParams.model_validate({field: value})
            self.assertIn("El parámetro", str(error.exception))

    def test_member_list_migration_uses_a_non_recursive_admin_helper_under_force_rls(self) -> None:
        from pathlib import Path

        migration = Path("migrations/versions/20260330_06_admin_member_list_rls.py").read_text(encoding="utf-8")
        self.assertIn('down_revision = "20260330_05"', migration)
        self.assertIn("current_tenant_is_admin", migration)
        self.assertIn("memberships_select_admin_tenant", migration)
        self.assertIn("DROP FUNCTION current_tenant_is_admin()", migration)
        self.assertIn("FORCE ROW LEVEL SECURITY",  Path("migrations/versions/20260330_01_mvp_rls_foundation.py").read_text(encoding="utf-8"))
        self.assertNotIn("BYPASSRLS", migration)

    def test_no_invitation_or_tenant_selection_route_is_registered(self) -> None:
        from app.main import app

        paths = {getattr(route, "path", "") for route in app.routes}
        self.assertFalse(any("invitation" in path for path in paths))
        self.assertNotIn("/api/tenants/select", paths)


if __name__ == "__main__":
    unittest.main()
