"""Focused contracts for deterministic security fixture data and credentials."""

import importlib.util
import os
import unittest
from contextlib import contextmanager
from pathlib import Path
from typing import Mapping


FIXTURE_EMAILS = {
    "alpha": {
        "admin": "admin-alpha@example.com",
        "member": "member-alpha@example.com",
        "viewer": "viewer-alpha@example.com",
    },
    "beta": {
        "admin": "admin-beta@example.com",
        "member": "member-beta@example.com",
        "viewer": "viewer-beta@example.com",
    },
}
FIXTURE_VARIABLES = {
    "alpha": {
        "admin": "ALPHA_ADMIN_EMAIL",
        "member": "ALPHA_MEMBER_EMAIL",
        "viewer": "ALPHA_VIEWER_EMAIL",
    },
    "beta": {
        "admin": "BETA_ADMIN_EMAIL",
        "member": "BETA_MEMBER_EMAIL",
        "viewer": "BETA_VIEWER_EMAIL",
    },
}


@contextmanager
def fixture_environment(overrides: Mapping[str, str | None]):
    original = os.environ.copy()
    try:
        for name, value in overrides.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value
        yield
    finally:
        os.environ.clear()
        os.environ.update(original)


SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "seed-security-fixtures.py"


def load_seed_module():
    spec = importlib.util.spec_from_file_location("seed_security_fixtures", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class RecordingConnection:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, object]]] = []

    def execute(self, statement, parameters: dict[str, object]) -> None:
        self.calls.append((str(statement), parameters))


class SeedSecurityFixturesTests(unittest.TestCase):
    def test_all_six_fixture_emails_are_required_login_payloads_and_map_to_tenants(self) -> None:
        from app.api.auth import LoginPayload

        seed = load_seed_module()
        environment = {
            name: FIXTURE_EMAILS[tenant][role]
            for tenant, roles in FIXTURE_VARIABLES.items()
            for role, name in roles.items()
        } | {"FIXTURE_PASSWORD": "fixture-password"}

        with fixture_environment(environment):
            emails, password = seed.load_fixture_credentials()

        self.assertEqual(password, "fixture-password")
        self.assertEqual(emails, FIXTURE_EMAILS)
        self.assertEqual(seed.FIXTURE_EMAIL_VARIABLES, FIXTURE_VARIABLES)
        normalized = []
        for tenant, roles in emails.items():
            for role, email in roles.items():
                payload = LoginPayload(email=email, password=password)
                self.assertEqual(str(payload.email), FIXTURE_EMAILS[tenant][role])
                normalized.append(str(payload.email))
        self.assertEqual(len(normalized), 6)
        self.assertEqual(len(set(normalized)), 6)

    def test_each_six_identity_variable_is_required_without_exposing_values(self) -> None:
        seed = load_seed_module()
        environment = {
            name: FIXTURE_EMAILS[tenant][role]
            for tenant, roles in FIXTURE_VARIABLES.items()
            for role, name in roles.items()
        } | {"FIXTURE_PASSWORD": "fixture-password"}

        for name in environment:
            with self.subTest(name=name), fixture_environment(environment | {name: None}):
                with self.assertRaisesRegex(SystemExit, name) as error:
                    seed.load_fixture_credentials()
                self.assertNotIn(FIXTURE_EMAILS["alpha"]["admin"], str(error.exception))
                self.assertNotIn(FIXTURE_EMAILS["beta"]["admin"], str(error.exception))

    def test_invalid_and_duplicate_variables_name_only_the_offending_variables(self) -> None:
        seed = load_seed_module()
        environment = {
            name: FIXTURE_EMAILS[tenant][role]
            for tenant, roles in FIXTURE_VARIABLES.items()
            for role, name in roles.items()
        } | {"FIXTURE_PASSWORD": "fixture-password"}

        with fixture_environment(environment | {"BETA_VIEWER_EMAIL": "not-an-email"}):
            with self.assertRaisesRegex(SystemExit, "BETA_VIEWER_EMAIL") as error:
                seed.load_fixture_credentials()
            self.assertNotIn("not-an-email", str(error.exception))

        with fixture_environment(environment | {"BETA_VIEWER_EMAIL": FIXTURE_EMAILS["alpha"]["admin"]}):
            with self.assertRaisesRegex(SystemExit, "ALPHA_ADMIN_EMAIL.*BETA_VIEWER_EMAIL") as error:
                seed.load_fixture_credentials()
            self.assertNotIn(FIXTURE_EMAILS["alpha"]["admin"], str(error.exception))

    def test_vector_rows_keep_matching_tenant_and_chunk_after_stale_reruns(self) -> None:
        seed = load_seed_module()
        connection = RecordingConnection()

        for _ in range(2):
            for slug in ("alpha", "beta"):
                tenant_id = seed.fixture_id(f"tenant/{slug}")
                document_id = seed.fixture_id(f"tenant/{slug}/document")
                chunk_id = seed.fixture_id(f"tenant/{slug}/chunk")
                seed.seed_fixture_chunk_and_embedding(
                    connection=connection,
                    tenant_id=tenant_id,
                    document_id=document_id,
                    chunk_id=chunk_id,
                    embedding_id=seed.fixture_id(f"tenant/{slug}/embedding"),
                    content=f"{slug} fixture",
                    embedding="[0.0,0.0]",
                )

        self.assertEqual(len(connection.calls), 16)
        for offset in range(0, len(connection.calls), 4):
            delete_embeddings, delete_chunks, chunk_insert, embedding_insert = connection.calls[offset : offset + 4]
            self.assertIn("DELETE FROM embeddings", delete_embeddings[0])
            self.assertIn("DELETE FROM chunks", delete_chunks[0])
            self.assertIn("INSERT INTO chunks", chunk_insert[0])
            self.assertIn("INSERT INTO embeddings", embedding_insert[0])
            self.assertEqual(chunk_insert[1]["tenant"], embedding_insert[1]["tenant"])
            self.assertEqual(chunk_insert[1]["id"], embedding_insert[1]["chunk"])


if __name__ == "__main__":
    unittest.main()
