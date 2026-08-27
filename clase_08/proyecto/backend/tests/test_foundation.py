import unittest
from unittest.mock import patch


class BackendFoundationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.environment = patch.dict(
            "os.environ",
            {
                "RUNTIME_DATABASE_URL": "postgresql+psycopg://runtime:password@db/student_project",
                "AUTH_DATABASE_URL": "postgresql+psycopg://auth:password@db/student_project",
                "ASSISTANT_DATABASE_URL": "postgresql+psycopg://assistant:password@db/student_project",
                "MINIO_ACCESS_KEY": "local-user",
                "MINIO_SECRET_KEY": "local-password",
                "SMTP_FROM": "noreply@example.test",
                "SESSION_SECRET": "test-session-secret",
                "RECOVERY_TOKEN_SECRET": "test-recovery-secret",
                "OPENROUTER_API_KEY": "",
            },
            clear=True,
        )
        cls.environment.start()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.environment.stop()
    def test_health_contract(self) -> None:
        from app.main import health_check

        self.assertEqual(
            health_check(),
            {"status": "ok", "service": "project-api"},
        )

    def test_error_handlers_localize_framework_validation_and_internal_errors(self) -> None:
        import asyncio
        import json

        from fastapi.exceptions import RequestValidationError
        from starlette.exceptions import HTTPException
        from starlette.requests import Request

        from app.main import http_error, request_validation_error, unexpected_error

        request = Request({"type": "http", "method": "GET", "path": "/", "headers": []})
        for status, detail in ((404, "No se encontró el recurso solicitado."), (405, "Método no permitido.")):
            with self.subTest(status=status):
                response = asyncio.run(http_error(request, HTTPException(status_code=status, detail="Not Found")))
                self.assertEqual(response.status_code, status)
                self.assertEqual(json.loads(bytes(response.body)), {"detail": detail})

        validation_cases = (
            ({"type": "missing", "loc": ("body", "password"), "input": {}}, "Este campo es obligatorio."),
            ({"type": "value_error", "loc": ("body", "email"), "input": "invalid", "ctx": {"reason": "English"}}, "Ingresá un correo electrónico válido."),
            ({"type": "string_too_short", "loc": ("body", "password"), "input": "short", "ctx": {"min_length": 8}}, "La contraseña debe tener al menos 8 caracteres."),
        )
        for error, expected in validation_cases:
            with self.subTest(expected=expected):
                response = asyncio.run(request_validation_error(request, RequestValidationError([error])))
                self.assertEqual(response.status_code, 422)
                issue = json.loads(bytes(response.body))["detail"][0]
                self.assertEqual(issue["msg"], expected)
                self.assertIn("loc", issue)
                self.assertIn("type", issue)
                self.assertNotIn("input", issue)
                self.assertNotIn("ctx", issue)

        internal = asyncio.run(unexpected_error(request, RuntimeError("database password or internal implementation")))
        self.assertEqual(internal.status_code, 500)
        self.assertEqual(json.loads(bytes(internal.body)), {"detail": "Ocurrió un error interno. Intentá nuevamente más tarde."})
        self.assertNotIn("database password", bytes(internal.body).decode())

    def test_runtime_and_admin_settings_have_separate_database_boundaries(self) -> None:
        # Ignore both the process environment and configured dotenv source so
        # host credentials cannot affect this local-defaults contract.
        with patch.dict("os.environ", {}, clear=True):
            from app.core.config import AdminToolSettings, RuntimeSettings

            settings = RuntimeSettings(  # pyright: ignore[reportCallIssue] -- pydantic-settings runtime-only source control
                _env_file=None,  # pyright: ignore[reportCallIssue] -- pydantic-settings runtime-only source control
                runtime_database_url="postgresql+psycopg://runtime:password@db/student_project",
                auth_database_url="postgresql+psycopg://auth:password@db/student_project",
                assistant_database_url="postgresql+psycopg://assistant:password@db/student_project",
                minio_access_key="local-user",
                minio_secret_key="local-password",
                smtp_from="noreply@example.test",
                session_secret="test-session-secret",
                recovery_token_secret="test-recovery-secret",
            )
            admin = AdminToolSettings(  # pyright: ignore[reportCallIssue] -- pydantic-settings runtime-only source control
                _env_file=None,  # pyright: ignore[reportCallIssue] -- pydantic-settings runtime-only source control
                migrator_database_url="postgresql+psycopg://migrator:password@db/student_project",
            )

        self.assertEqual(settings.max_upload_bytes, 25 * 1024 * 1024)
        self.assertEqual(settings.embedding_dimension, 384)
        self.assertEqual(settings.embeddings_api_url, "http://embeddings-api:8000")
        self.assertTrue(settings.openrouter_api_key is None)
        self.assertEqual(settings.openrouter_model, "openai/gpt-4o-mini")
        self.assertFalse(hasattr(settings, "migrator_database_url"))
        self.assertFalse(hasattr(admin, "runtime_database_url"))


if __name__ == "__main__":
    unittest.main()
