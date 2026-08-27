"""Focused static, behavior, and syntax contracts for local demo operations."""

import ast
import os
import subprocess
import unittest
from pathlib import Path
from typing import Callable, cast
from unittest.mock import patch


PROJECT = Path(__file__).resolve().parents[2]
SCRIPTS = PROJECT / "scripts"


class DemoScriptTests(unittest.TestCase):
    def test_seed_is_deterministic_and_covers_security_fixture_domains(self) -> None:
        source = (SCRIPTS / "seed-security-fixtures.py").read_text(encoding="utf-8")
        ast.parse(source)
        self.assertIn("uuid5", source)
        self.assertIn('("admin", "member", "viewer")', source)
        self.assertIn('("alpha", "Alpha Research Lab")', source)
        self.assertIn('("beta", "Beta Evaluation Lab")', source)
        for table in ("experiments", "results", "metrics", "documents", "chunks", "embeddings"):
            self.assertIn(f"INSERT INTO {table}", source)
        for variable in (
            "ALPHA_ADMIN_EMAIL", "ALPHA_MEMBER_EMAIL", "ALPHA_VIEWER_EMAIL",
            "BETA_ADMIN_EMAIL", "BETA_MEMBER_EMAIL", "BETA_VIEWER_EMAIL",
            "FIXTURE_PASSWORD",
        ):
            self.assertIn(variable, source)
        self.assertIn("FIXTURE_EMAIL_VARIABLES", source)
        self.assertIn("pg_insert(users_table)", source)
        self.assertIn("on_conflict_do_update", source)
        self.assertNotIn("DEMO_FIXTURE_PASSWORD", source)
        self.assertNotIn("FIXTURE_EMBEDDING", source)
        for secret_artifact in ("session_token", "recovery_token", "csrf_token"):
            self.assertNotIn(secret_artifact, source)

    def test_fixture_environment_matches_backend_email_validation_without_leaking_values(self) -> None:
        source = (SCRIPTS / "seed-security-fixtures.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        selected: list[ast.stmt] = [
            node
            for node in tree.body
            if (
                isinstance(node, ast.FunctionDef)
                and node.name == "load_fixture_credentials"
            )
            or (
                isinstance(node, ast.Assign)
                and any(
                    isinstance(target, ast.Name) and target.id == "FIXTURE_EMAIL_VARIABLES"
                    for target in node.targets
                )
            )
        ]
        namespace: dict[str, object] = {"os": os}
        exec(compile(ast.Module(body=selected, type_ignores=[]), "fixture-environment", "exec"), namespace)
        load = cast(Callable[[], tuple[dict[str, dict[str, str]], str]], namespace["load_fixture_credentials"])
        valid = {
            "ALPHA_ADMIN_EMAIL": " Alpha.Admin@example.com ",
            "ALPHA_MEMBER_EMAIL": "alpha.member@bdia.com",
            "ALPHA_VIEWER_EMAIL": "alpha.viewer@example.com",
            "BETA_ADMIN_EMAIL": "Beta.Admin@example.com",
            "BETA_MEMBER_EMAIL": "beta.member@bdia.com",
            "BETA_VIEWER_EMAIL": "beta.viewer@example.com",
            "FIXTURE_PASSWORD": "eight-ok",
        }
        with patch.dict(os.environ, valid, clear=True):
            emails, password = load()
        self.assertEqual(emails["alpha"]["admin"], "Alpha.Admin@example.com")
        self.assertEqual(emails["beta"]["viewer"], "beta.viewer@example.com")
        self.assertEqual(password, valid["FIXTURE_PASSWORD"])
        self.assertEqual(len(password), 8)

        invalid_cases = {
            "missing": {name: value for name, value in valid.items() if name != "ALPHA_VIEWER_EMAIL"},
            "reserved-domain": valid | {"ALPHA_VIEWER_EMAIL": "viewer@example.test"},
            "malformed": valid | {"ALPHA_VIEWER_EMAIL": "not-an-email"},
            "duplicate": valid | {"ALPHA_VIEWER_EMAIL": "alpha.member@BDIA.COM"},
            "short-password": valid | {"FIXTURE_PASSWORD": "seven!!"},
        }
        for case, environment in invalid_cases.items():
            with self.subTest(case=case), patch.dict(os.environ, environment, clear=True):
                with self.assertRaises(SystemExit) as raised:
                    load()
                message = str(raised.exception)
                for value in environment.values():
                    self.assertNotIn(value, message)

    def test_compose_defines_bounded_pgadmin_and_fixture_environment(self) -> None:
        source = (PROJECT / "compose.yaml").read_text(encoding="utf-8")
        for marker in (
            "name: bdia-project",
            "dpage/pgadmin4:9.17",
            "PGADMIN_DEFAULT_EMAIL: ${PGADMIN_DEFAULT_EMAIL}",
            "PGADMIN_DEFAULT_PASSWORD: ${PGADMIN_DEFAULT_PASSWORD}",
            '"${PGADMIN_PORT:-5050}:80"',
            "student-project-pgadmin:/var/lib/pgadmin",
            "condition: service_healthy",
            "http://127.0.0.1/misc/ping",
            "start_period: 20s",
        ):
            self.assertIn(marker, source)
        self.assertEqual(source.count("student-project-pgadmin:"), 2)
        for variable in (
            "ALPHA_ADMIN_EMAIL", "ALPHA_MEMBER_EMAIL", "ALPHA_VIEWER_EMAIL",
            "BETA_ADMIN_EMAIL", "BETA_MEMBER_EMAIL", "BETA_VIEWER_EMAIL",
            "FIXTURE_PASSWORD",
        ):
            self.assertIn(f"{variable}: ${{{variable}}}", source)
        self.assertIn("http://embeddings-api:8000", source)
        self.assertIn("${EMBEDDINGS_API_PORT:-8011}:8000", source)
        pgadmin_environment = source.split("  pgadmin:", 1)[1].split("    ports:", 1)[0]
        self.assertNotIn("${ADMIN_EMAIL}", pgadmin_environment)
        self.assertNotIn("${FIXTURE_PASSWORD}", pgadmin_environment)

    def test_compose_bootstraps_queryable_tenant_documents_before_api_start(self) -> None:
        source = (PROJECT / "compose.yaml").read_text(encoding="utf-8")
        bootstrap = source.split("\n  demo-bootstrap:\n", 1)[1].split("\n  db-role-reconcile:", 1)[0]
        api = source.split("\n  api:\n", 1)[1].split("\n  db:", 1)[0]

        self.assertIn('restart: "no"', bootstrap)
        self.assertNotIn("profiles:", bootstrap)
        self.assertIn("MIGRATOR_DATABASE_URL", bootstrap)
        self.assertIn("MINIO_ENDPOINT: minio:9000", bootstrap)
        self.assertIn("EMBEDDINGS_API_URL: http://embeddings-api:8000", bootstrap)
        self.assertIn(".:/workspace:ro", bootstrap)
        self.assertIn("alembic upgrade head", bootstrap)
        self.assertIn("python /workspace/scripts/seed-security-fixtures.py", bootstrap)
        self.assertIn("python /workspace/scripts/seed-tenant-documents.py", bootstrap)
        for dependency in ("db", "minio-init", "embeddings-api"):
            self.assertIn(f"{dependency}:", bootstrap)
        self.assertIn("demo-bootstrap:", api)
        self.assertIn("condition: service_completed_successfully", api)

    def test_verifier_maps_required_proofs_to_executable_checks(self) -> None:
        source = (SCRIPTS / "verify-stack.sh").read_text(encoding="utf-8")
        for marker in (
            "/health",
            "/salud",
            "embeddings-api",
            "student-assets",
            "tests.test_experiments",
            "tests.test_documents",
            "tests.test_assistant_sql",
            "tests.test_identity_http",
            "tests.test_rls_integration",
            "tests.test_tenant_context",
        ):
            self.assertIn(marker, source)
        self.assertIn("set -eu", source)
        self.assertIn('TEST_WEB_ORIGIN="http://localhost:$WEB_PORT"', source)
        self.assertIn('-e TEST_WEB_ORIGIN="$TEST_WEB_ORIGIN"', source)
        self.assertIn("db pgadmin minio mailpit embeddings-api", source)
        self.assertNotIn("set -x", source)

    def test_reset_is_local_scoped_and_requires_confirmation(self) -> None:
        source = (SCRIPTS / "reset-local.sh").read_text(encoding="utf-8")
        for marker in (
            'EXPECTED_PROJECT="bdia-project"',
            "APP_ENV",
            "DOCKER_HOST",
            "--ci-confirm",
            "CI:-",
            "RESET $PROJECT",
            'label=com.docker.compose.project=$PROJECT',
            "down --volumes --remove-orphans",
        ):
            self.assertIn(marker, source)
        for unsafe in ("docker volume prune", "docker system prune", "rm -rf"):
            self.assertNotIn(unsafe, source)

    def test_shell_scripts_parse_and_help_is_non_destructive(self) -> None:
        for name in ("verify-stack.sh", "reset-local.sh"):
            result = subprocess.run(
                ["sh", "-n", str(SCRIPTS / name)], capture_output=True, text=True, check=False
            )
            self.assertEqual(result.returncode, 0, result.stderr)
        help_result = subprocess.run(
            [str(SCRIPTS / "reset-local.sh"), "--help"], capture_output=True, text=True, check=False
        )
        self.assertEqual(help_result.returncode, 0, help_result.stderr)
        self.assertIn("--ci-confirm", help_result.stdout)


if __name__ == "__main__":
    unittest.main()
