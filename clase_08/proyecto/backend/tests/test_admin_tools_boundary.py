"""Deployment contracts for isolated API and one-shot administration processes."""

import os
import re
import subprocess
import sys
import unittest
from pathlib import Path


PROJECT = Path(__file__).resolve().parents[2]


def service_block(compose: str, name: str) -> str:
    header = f"  {name}:\n"
    match = re.search(rf"^  {re.escape(name)}:\n", compose, re.MULTILINE)
    assert match is not None
    start = match.start()
    body_start = start + len(header)
    following = re.search(r"^  [a-z][\w-]*:\n", compose[body_start:], re.MULTILINE)
    return compose[start : body_start + following.start()] if following else compose[start:]


class AdminToolsBoundaryTests(unittest.TestCase):
    def test_api_gets_only_runtime_auth_and_assistant_database_urls(self) -> None:
        api = service_block((PROJECT / "compose.yaml").read_text(encoding="utf-8"), "api")
        for key in ("RUNTIME_DATABASE_URL", "AUTH_DATABASE_URL", "ASSISTANT_DATABASE_URL"):
            self.assertIn(key, api)
        for forbidden in ("MIGRATOR_DATABASE_URL", "POSTGRES_PASSWORD", "PROJECT_MIGRATOR_PASSWORD"):
            self.assertNotIn(forbidden, api)

    def test_admin_tools_is_no_port_one_shot_migrator_boundary(self) -> None:
        admin = service_block((PROJECT / "compose.yaml").read_text(encoding="utf-8"), "admin-tools")
        self.assertIn('restart: "no"', admin)
        self.assertIn("MIGRATOR_DATABASE_URL", admin)
        self.assertIn("alembic", admin)
        self.assertNotIn("ports:", admin)
        for forbidden in ("RUNTIME_DATABASE_URL", "AUTH_DATABASE_URL", "ASSISTANT_DATABASE_URL", "POSTGRES_PASSWORD"):
            self.assertNotIn(forbidden, admin)

    def test_admin_tool_settings_load_without_runtime_process_secrets(self) -> None:
        environment = {"MIGRATOR_DATABASE_URL": "postgresql+psycopg://project_migrator:password@db/student_project"}
        result = subprocess.run(
            [sys.executable, "-c", "from app.core.config import AdminToolSettings; print(AdminToolSettings().migrator_database_url)"],
            cwd=PROJECT / "backend",
            env={**os.environ, **environment},
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), environment["MIGRATOR_DATABASE_URL"])

    def test_admin_tools_mounts_the_project_for_the_fixture_seed_entrypoint(self) -> None:
        admin = service_block((PROJECT / "compose.yaml").read_text(encoding="utf-8"), "admin-tools")
        self.assertIn(".:/workspace:ro", admin)

    def test_migrator_has_direct_schema_create_for_alembic_without_inheriting_owner(self) -> None:
        source = (PROJECT / "infra/postgres/00-create-roles.sh").read_text(encoding="utf-8")
        self.assertIn("GRANT USAGE, CREATE ON SCHEMA public TO project_migrator", source)

    def test_reconciliation_is_separate_and_config_excludes_migrator(self) -> None:
        compose = (PROJECT / "compose.yaml").read_text(encoding="utf-8")
        reconcile = service_block(compose, "db-role-reconcile")
        self.assertIn('restart: "no"', reconcile)
        self.assertIn("POSTGRES_PASSWORD", reconcile)
        self.assertNotIn("ports:", reconcile)
        config = (PROJECT / "backend/app/core/config.py").read_text(encoding="utf-8")
        self.assertIn("class RuntimeSettings", config)
        self.assertIn("class AdminToolSettings", config)
        self.assertNotIn("migrator_database_url: str", config.split("class RuntimeSettings", 1)[1].split("class AdminToolSettings", 1)[0])


if __name__ == "__main__":
    unittest.main()
