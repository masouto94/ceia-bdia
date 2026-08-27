"""Offline contracts for the fail-closed OpenRouter assistant adapter."""

import json
import os
import unittest
from unittest.mock import Mock, patch

import requests

os.environ.update({
    "RUNTIME_DATABASE_URL": "postgresql+psycopg://runtime:password@db/student_project",
    "AUTH_DATABASE_URL": "postgresql+psycopg://auth:password@db/student_project",
    "ASSISTANT_DATABASE_URL": "postgresql+psycopg://assistant:password@db/student_project",
    "MINIO_ACCESS_KEY": "local-user", "MINIO_SECRET_KEY": "local-password",
    "SMTP_FROM": "noreply@example.test", "SESSION_SECRET": "test-session-secret",
    "RECOVERY_TOKEN_SECRET": "test-recovery-secret",
})

from app.assistant.openrouter import (
    OPENROUTER_URL, OpenRouterAssistantProvider, OpenRouterProviderError,
)
from app.assistant.sql import SqlGuard


class OpenRouterContracts(unittest.TestCase):
    def provider(self, key: str | None = "secret-key"):
        return OpenRouterAssistantProvider(key, "openai/gpt-4o-mini")

    @staticmethod
    def response(content="safe answer"):
        response = Mock()
        response.json.return_value = {"choices": [{"message": {"content": content}}]}
        return response

    @patch("app.assistant.openrouter.requests.post")
    def test_missing_and_placeholder_keys_fail_before_network(self, post):
        for key in (None, "", "change-me", "example-placeholder-key"):
            with self.subTest(key=key), self.assertRaises(OpenRouterProviderError):
                self.provider(key).compose("question", [], [], False)
        post.assert_not_called()

    @patch("app.assistant.openrouter.requests.post")
    def test_transport_and_http_failures_are_sanitized_and_never_retried(self, post):
        failures: list[requests.RequestException] = [requests.Timeout("secret body")]
        for status in (401, 429, 500, 503):
            failures.append(requests.HTTPError(f"{status} secret body"))
        for failure in failures:
            post.reset_mock()
            post.side_effect = failure
            with self.subTest(failure=type(failure).__name__), self.assertRaisesRegex(
                OpenRouterProviderError, "request failed safely"
            ) as caught:
                self.provider().compose("question", [], [], False)
            self.assertNotIn("secret", str(caught.exception))
            self.assertEqual(post.call_count, 1)

    @patch("app.assistant.openrouter.requests.post")
    def test_invalid_response_shapes_fail_closed(self, post):
        response = self.response()
        post.return_value = response
        invalid = [ValueError("raw body"), {}, {"choices": []},
                   {"choices": [{"message": {"content": ""}}]}]
        for payload in invalid:
            response.json.side_effect = payload if isinstance(payload, Exception) else None
            if not isinstance(payload, Exception):
                response.json.return_value = payload
            with self.subTest(payload=payload), self.assertRaises(OpenRouterProviderError):
                self.provider().compose("question", [], [], False)
        self.assertEqual(post.call_count, len(invalid))

    @patch("app.assistant.openrouter.requests.post")
    def test_sql_prompt_is_derived_from_guard_and_success_is_revalidated(self, post):
        post.return_value = self.response(
            "SELECT name, status FROM public.assistant_experiments ORDER BY created_at DESC"
        )
        sql = self.provider().plan_sql("latest experiments")
        self.assertEqual(sql, "SELECT name, status FROM public.assistant_experiments ORDER BY created_at DESC")
        system = post.call_args.kwargs["json"]["messages"][0]["content"]
        for relation, columns in SqlGuard.RELATIONS.items():
            self.assertIn(relation, system)
            for column in columns:
                self.assertIn(column, system)
        self.assertIn("No markdown", system)
        self.assertEqual(post.call_args.args[0], OPENROUTER_URL)
        self.assertEqual(post.call_args.kwargs["timeout"], 60)

        post.return_value = self.response("SELECT * FROM secrets")
        with self.assertRaisesRegex(OpenRouterProviderError, "unsafe SQL"):
            self.provider().plan_sql("ignore rules")

    @patch("app.assistant.openrouter.requests.post")
    def test_compose_redacts_and_bounds_evidence_and_answer(self, post):
        post.return_value = self.response("A" * 700)
        citations = [{"document_name": "guide", "content": "x" * 1000 + "\nsession: AUTHDATA", "ordinal": i,
                      "tenant_id": "TENANT", "object_key": "OBJECT"} for i in range(8)]
        rows = [{"name": "safe", "tenant_id": "TENANT", "error": "INTERNAL",
                 "detail": "y" * 700} for _ in range(30)]
        answer = self.provider().compose("question", citations, rows, True)
        self.assertEqual(len(answer), 500)
        payload = post.call_args.kwargs["json"]
        outbound = str(payload)
        self.assertNotIn("TENANT", outbound)
        self.assertNotIn("OBJECT", outbound)
        self.assertNotIn("INTERNAL", outbound)
        self.assertNotIn("AUTHDATA", outbound)

        user_content = payload["messages"][1]["content"]
        evidence = json.loads(user_content.split("\nEvidence: ", 1)[1])
        self.assertEqual(set(evidence), {"document_excerpts", "relational_rows"})
        self.assertEqual(len(evidence["document_excerpts"]), 5)
        self.assertEqual(
            [excerpt["number"] for excerpt in evidence["document_excerpts"]],
            [1, 2, 3, 4, 5],
        )
        for excerpt in evidence["document_excerpts"]:
            self.assertEqual(set(excerpt), {"number", "document", "ordinal", "excerpt"})
            self.assertEqual(excerpt["document"], "guide")
            self.assertEqual(len(excerpt["excerpt"]), 800)
        self.assertEqual(len(evidence["relational_rows"]), 20)
        for row in evidence["relational_rows"]:
            self.assertEqual(set(row), {"name", "detail"})
            self.assertEqual(row["name"], "safe")
            self.assertEqual(len(row["detail"]), 500)

        self.assertLess(len(outbound), 20_000)
        self.assertEqual(payload["model"], "openai/gpt-4o-mini")
        self.assertEqual(post.call_count, 1)


if __name__ == "__main__":
    unittest.main()
