"""Focused orchestration and HTTP contracts for the tenant-safe assistant."""

import os
import unittest
from unittest.mock import Mock, patch
from uuid import uuid4

from pydantic import ValidationError

os.environ.update({
    "RUNTIME_DATABASE_URL": "postgresql+psycopg://runtime:password@db/student_project",
    "AUTH_DATABASE_URL": "postgresql+psycopg://auth:password@db/student_project",
    "ASSISTANT_DATABASE_URL": "postgresql+psycopg://assistant:password@db/student_project",
    "MINIO_ACCESS_KEY": "local-user", "MINIO_SECRET_KEY": "local-password",
    "SMTP_FROM": "noreply@example.test", "SESSION_SECRET": "test-session-secret",
    "RECOVERY_TOKEN_SECRET": "test-recovery-secret",
})

from app.api.assistant import AssistantRequest, query_assistant
from app.assistant.service import AssistantService, AssistantUnavailable, TrustedAssistantContext
from app.assistant.sql import SqlResult


SESSION_DIGEST = "a" * 64


class Provider:
    def plan_sql(self, prompt):
        return "SELECT name, status FROM public.assistant_experiments"

    def compose(self, prompt, citations, rows, relational_available):
        return f"documents={len(citations)} rows={len(rows)} relational={relational_available}"


class AssistantContracts(unittest.TestCase):
    def setUp(self) -> None:
        self.context = TrustedAssistantContext(uuid4(), uuid4(), "viewer", SESSION_DIGEST)

    def test_document_and_relational_results_include_safe_provenance(self) -> None:
        documents = Mock()
        documents.retrieve.return_value = [{
            "chunk_id": str(uuid4()), "document_id": str(uuid4()),
            "document_name": "guide.md", "ordinal": 0, "content": "safe excerpt",
        }]
        sql = Mock()
        sql.execute.return_value = SqlResult(
            "SELECT name, status FROM public.assistant_experiments",
            [{"name": "demo", "status": "done"}], 35,
        )
        result = AssistantService(documents, sql, Provider()).answer("summarize", "combined", self.context)

        self.assertEqual(result["status"], "complete")
        self.assertEqual(result["citations"][0]["document_name"], "guide.md")
        self.assertEqual(result["relational"]["sql_provenance"], {
            "query": "SELECT name, status FROM public.assistant_experiments", "row_count": 1,
        })
        serialized = str(result)
        self.assertNotIn("object_key", serialized)
        self.assertNotIn("experiments WHERE tenant_id", serialized)
        called = sql.execute.call_args.kwargs
        self.assertEqual(called["context"], self.context)
        self.assertNotIn("verifies_membership", called)

    def test_auto_is_truthfully_partial_and_fails_closed_when_every_source_is_unavailable(self) -> None:
        documents, sql = Mock(), Mock()
        documents.retrieve.side_effect = RuntimeError("provider internals")
        sql.execute.return_value = SqlResult(
            "SELECT name, status FROM public.assistant_experiments", [{"name": "safe"}], 15,
        )
        partial = AssistantService(documents, sql, Provider()).answer("status", "auto", self.context)
        self.assertEqual((partial["resolved_mode"], partial["status"], partial["unavailable"]),
                         ("combined", "partial", ["document"]))
        self.assertNotIn("provider internals", str(partial))

        sql.execute.side_effect = RuntimeError("database internals")
        with self.assertRaises(AssistantUnavailable):
            AssistantService(documents, sql, Provider()).answer("status", "combined", self.context)

    def test_request_is_bounded_and_cannot_select_tenant_or_mode_outside_allowlist(self) -> None:
        for payload in (
            {"prompt": "x", "mode": "other"},
            {"prompt": "x", "tenant_id": str(uuid4())},
            {"prompt": "x" * 1001},
        ):
            with self.subTest(payload=payload), self.assertRaises(ValidationError):
                AssistantRequest.model_validate(payload)

    def test_http_boundary_derives_context_only_from_opaque_session(self) -> None:
        user, tenant = uuid4(), uuid4()
        db, service = Mock(), Mock()
        service.answer.return_value = {"status": "complete"}
        with (patch("app.api.assistant._session", return_value={"user_id": user, "session_digest": SESSION_DIGEST}) as session,
              patch("app.api.assistant._tenant_context", return_value=tenant) as authorize,
              patch("app.api.assistant._service", return_value=service)):
            result = query_assistant(AssistantRequest(prompt="safe", mode="document"), "opaque", db)

        self.assertEqual(result, {"status": "complete"})
        session.assert_called_once_with(db, "opaque")
        self.assertEqual(authorize.call_args.args[2], {"admin", "member", "viewer"})
        context = service.answer.call_args.args[2]
        self.assertEqual((context.user_id, context.tenant_id), (user, tenant))
        self.assertEqual(context.session_digest, SESSION_DIGEST)


if __name__ == "__main__":
    unittest.main()
