"""Live HTTP contract tests for the tenant-safe audit read model."""

# pyright: reportMissingImports=false

import json
import os
import re
import unittest
from pathlib import Path
from datetime import UTC, datetime, timedelta
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from uuid import uuid4


BASE_URL = os.getenv("TEST_API_URL", "")
MAILPIT_URL = os.getenv("MAILPIT_URL", "")
WEB_ORIGIN = os.getenv("TEST_WEB_ORIGIN", "http://localhost:5173")


@unittest.skipUnless(BASE_URL and MAILPIT_URL, "set TEST_API_URL and MAILPIT_URL for audit HTTP probes")
class AuditHttpTests(unittest.TestCase):
    def request(
        self, path: str, payload: dict | None = None, headers: dict | None = None, method: str | None = None
    ) -> tuple[int, dict, dict]:
        request = Request(
            f"{BASE_URL}{path}",
            headers={"Host": "api", **(headers or {})},
            method=method or ("POST" if payload is not None else "GET"),
        )
        if payload is not None:
            request.data = json.dumps(payload).encode()
            request.add_header("Content-Type", "application/json")
        try:
            with urlopen(request, timeout=30) as response:
                response_headers = dict(response.headers)
                response_headers["Set-Cookie"] = ", ".join(response.headers.get_all("Set-Cookie", []))
                return response.status, response_headers, json.loads(response.read())
        except HTTPError as error:
            return error.code, dict(error.headers), json.loads(error.read())

    @staticmethod
    def cookies(headers: dict) -> tuple[str, str]:
        values = headers.get("Set-Cookie", "").split(", ")
        return tuple(re.search(r"(?:session_token|csrf_token)=([^;]+)", value).group(1) for value in values)  # type: ignore[return-value]

    @staticmethod
    def read_headers(session: str) -> dict[str, str]:
        return {"Cookie": f"session_token={session}"}

    @staticmethod
    def csrf_headers(session: str, csrf: str) -> dict[str, str]:
        return {
            "Origin": WEB_ORIGIN,
            "Cookie": f"session_token={session}; csrf_token={csrf}",
            "X-CSRF-Token": csrf,
        }

    def upload_text_document(self, name: str, content: str, headers: dict[str, str]) -> tuple[int, dict]:
        boundary = f"----audit-{uuid4().hex}"
        body = (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="file"; filename="{name}"\r\n'
            "Content-Type: text/plain\r\n\r\n"
            f"{content}\r\n--{boundary}--\r\n"
        ).encode()
        request = Request(f"{BASE_URL}/api/documents", data=body, headers={"Host": "api", **headers}, method="POST")
        request.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
        try:
            with urlopen(request, timeout=30) as response:
                return response.status, json.loads(response.read())
        except HTTPError as error:
            return error.code, json.loads(error.read())

    def recovery_token(self, email: str) -> str:
        with urlopen(f"{MAILPIT_URL}/api/v1/messages", timeout=10) as response:
            messages = json.loads(response.read())["messages"]
        for message in messages:
            recipients = json.dumps(message.get("To", ""))
            if email in recipients:
                match = re.search(r"token=([A-Za-z0-9_-]+)", message.get("Snippet", ""))
                if match:
                    return match.group(1)
        self.fail(f"Mailpit did not contain a recovery token for {email}")
        return ""

    def audit(self, headers: dict[str, str], **query: str) -> tuple[int, dict]:
        encoded = urlencode(query)
        status, _, body = self.request(f"/api/audit-events?{encoded}" if encoded else "/api/audit-events", headers=headers)
        return status, body

    def test_admin_audit_events_are_normalized_filterable_paginated_and_tenant_safe(self) -> None:
        marker = uuid4().hex
        admin_email = f"audit-admin-{marker}@example.com"
        status, headers, admin = self.request(
            "/api/auth/register",
            {"email": admin_email, "password": "correct-horse", "tenant_name": f"Audit Lab {marker}"},
        )
        self.assertEqual((status, admin["role"]), (201, "admin"))
        admin_session, admin_csrf = self.cookies(headers)
        read_headers = self.read_headers(admin_session)
        write_headers = self.csrf_headers(admin_session, admin_csrf)
        self.assertEqual(self.request("/api/auth/login", {"email": admin_email, "password": "correct-horse"})[0], 200)

        member_email = f"audit-member-{marker}@example.com"
        viewer_email = f"audit-viewer-{marker}@example.com"
        member = self.request("/api/members", {"email": member_email, "role": "viewer"}, write_headers)
        viewer = self.request("/api/members", {"email": viewer_email, "role": "viewer"}, write_headers)
        self.assertEqual((member[0], viewer[0]), (201, 201))
        member_id = member[2]["user_id"]
        self.assertEqual(self.request(f"/api/members/{member_id}", {"role": "member"}, write_headers, "PATCH")[0], 200)
        self.assertEqual(self.request(f"/api/members/{member_id}", {"active": False}, write_headers, "PATCH")[0], 200)
        self.assertEqual(self.request(f"/api/members/{member_id}", {"active": True}, write_headers, "PATCH")[0], 200)

        experiment_name = f"audit experiment {marker}"
        experiment = self.request("/api/experiments", {"name": experiment_name}, write_headers)
        self.assertEqual(experiment[0], 201)
        experiment_id = experiment[2]["id"]
        self.assertEqual(self.request(f"/api/experiments/{experiment_id}", {"status": "running"}, write_headers, "PATCH")[0], 200)
        result = self.request(
            f"/api/experiments/{experiment_id}/results",
            {"status": "completed", "terminal_status": "completed", "metrics": []},
            write_headers,
        )
        self.assertEqual(result[0], 201)
        self.assertEqual(self.request(f"/api/experiments/{experiment_id}", {"archived": True}, write_headers, "PATCH")[0], 200)
        self.assertEqual(self.request(f"/api/experiments/{experiment_id}", {"archived": False}, write_headers, "PATCH")[0], 200)

        document = self.upload_text_document(f"audit-{marker}.txt", "audit ingestion content", write_headers)
        self.assertEqual(document[0], 201)
        document_id = document[1]["id"]
        self.assertEqual(self.request(f"/api/documents/{document_id}/ingest", headers=write_headers, method="POST")[0], 200)
        self.assertEqual(self.request(f"/api/documents/{document_id}/ingest", headers=write_headers, method="POST")[0], 200)

        today = datetime.now(UTC).date()
        date_from = today.isoformat()
        date_to = (today + timedelta(days=1)).isoformat()
        status, all_events = self.audit(read_headers, **{"from": date_from, "to": date_to, "per_page": "100"})
        self.assertEqual(status, 200, all_events)
        items = all_events["items"]
        self.assertGreaterEqual(all_events["total"], len(items))
        self.assertTrue({"audit", "experiment_status", "ingestion"}.issubset({item["source"] for item in items}))
        self.assertTrue(
            {
                "auth.registration",
                "auth.login",
                "membership.created",
                "membership.role_changed",
                "membership.activation_changed",
                "experiment.created",
                "experiment.status_transition",
                "experiment.result_added",
                "experiment.archived",
                "experiment.restored",
                "document.upload",
                "document.ingest.completed",
            }.issubset({item["action"] for item in items})
        )
        self.assertEqual(
            len({(item["source"], item["action"], item["resource"], item["id"]) for item in items}), len(items)
        )
        self.assertEqual(
            sum(item["action"] == "experiment.status_transition" and item["resource"] == f"experiment:{experiment_id}" for item in items),
            2,
        )

        member_events_status, member_events = self.audit(read_headers, actor_id=admin["user_id"], action="membership.role_changed")
        self.assertEqual(member_events_status, 200)
        self.assertEqual((member_events["total"], member_events["items"][0]["resource"]), (1, f"membership:{member_id}"))
        outcome_status, successful = self.audit(read_headers, outcome="success")
        self.assertEqual(outcome_status, 200)
        self.assertTrue(successful["items"] and all(item["outcome"] == "success" for item in successful["items"]))
        search_status, searched = self.audit(read_headers, search=experiment_id)
        self.assertEqual(search_status, 200)
        self.assertEqual((searched["total"], searched["items"][0]["resource"]), (6, f"experiment:{experiment_id}"))
        self.assertEqual(self.audit(read_headers, **{"from": (datetime.now(UTC) - timedelta(days=32)).isoformat(), "to": datetime.now(UTC).isoformat()})[0], 422)

        first_status, first_page = self.audit(read_headers, **{"from": date_from, "to": date_to, "per_page": "10", "page": "1"})
        beyond_status, beyond_page = self.audit(read_headers, **{"from": date_from, "to": date_to, "per_page": "10", "page": "99"})
        self.assertEqual((first_status, beyond_status), (200, 200))
        self.assertGreater(first_page["total"], 10)
        self.assertEqual((beyond_page["items"], beyond_page["total"], beyond_page["pages"]), ([], first_page["total"], first_page["pages"]))

        self.assertEqual(self.request("/api/auth/recovery/request", {"email": member_email})[0], 202)
        self.assertEqual(self.request("/api/auth/recovery/confirm", {"token": self.recovery_token(member_email), "password": "member-password"})[0], 200)
        _, member_login_headers, _ = self.request("/api/auth/login", {"email": member_email, "password": "member-password"})
        member_session, _ = self.cookies(member_login_headers)
        self.assertEqual(self.request("/api/auth/recovery/request", {"email": viewer_email})[0], 202)
        self.assertEqual(self.request("/api/auth/recovery/confirm", {"token": self.recovery_token(viewer_email), "password": "viewer-password"})[0], 200)
        _, viewer_login_headers, _ = self.request("/api/auth/login", {"email": viewer_email, "password": "viewer-password"})
        viewer_session, _ = self.cookies(viewer_login_headers)
        self.assertEqual(self.audit(self.read_headers(member_session))[0], 403)
        self.assertEqual(self.audit(self.read_headers(viewer_session))[0], 403)

        other_email = f"audit-other-{marker}@example.com"
        _, other_headers, other_admin = self.request(
            "/api/auth/register",
            {"email": other_email, "password": "correct-horse", "tenant_name": f"Other Audit Lab {marker}"},
        )
        other_session, other_csrf = self.cookies(other_headers)
        other_document = self.upload_text_document(f"other-audit-{marker}.txt", "other tenant content", self.csrf_headers(other_session, other_csrf))
        self.assertEqual(other_document[0], 201)
        self.assertEqual(self.request("/api/auth/recovery/request", {"email": f"global-recovery-{marker}@example.com"})[0], 202)
        isolated_status, isolated = self.audit(read_headers, **{"from": date_from, "to": date_to, "per_page": "100"})
        self.assertEqual(isolated_status, 200)
        self.assertNotIn(other_email, json.dumps(isolated))
        self.assertNotIn(other_document[1]["id"], json.dumps(isolated))
        self.assertNotIn(f"global-recovery-{marker}@example.com", json.dumps(isolated))
        self.assertNotIn(other_admin["user_id"], json.dumps(isolated))

        safe_detail_keys = {"previous_archived", "archived", "previous_status", "next_status", "role", "previous_role", "active", "previous_active", "content_type", "size_bytes", "chunk_count", "attempt"}
        for item in items:
            self.assertEqual(set(item), {"id", "occurred_at", "actor", "action", "outcome", "resource", "detail", "source"})
            self.assertTrue(set(item["detail"]).issubset(safe_detail_keys))
            self.assertNotIn("password", json.dumps(item["detail"]).lower())
            self.assertNotIn("token", json.dumps(item["detail"]).lower())
            if item["source"] == "ingestion":
                self.assertIsNone(item["actor"])
            elif item["actor"] is not None:
                self.assertEqual(set(item["actor"]), {"user_id", "email"})
                self.assertEqual(item["actor"]["email"], admin_email)


class PlatformAuditContractTests(unittest.TestCase):
    def test_platform_denials_use_fixed_safe_audit_contract(self) -> None:
        source = (Path(__file__).resolve().parents[1] / "app/api/platform.py").read_text(encoding="utf-8")
        self.assertIn("platform.route_denied", source)
        self.assertIn("append_platform_denial", source)
        self.assertIn("_PLATFORM_DENIAL_ACTION", source)
        self.assertNotIn("payload.actor", source)
        self.assertNotIn("payload.metadata", source)


if __name__ == "__main__":
    unittest.main()
