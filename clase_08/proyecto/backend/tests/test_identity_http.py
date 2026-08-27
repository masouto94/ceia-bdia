"""Run against the isolated Compose API with TEST_API_URL and MAILPIT_URL set."""

# pyright: reportMissingImports=false

import hashlib
import hmac
import json
import os
import re
import unittest
from datetime import date, timedelta
from time import sleep

import psycopg

from app.security.password import hash_password
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, urlopen
from uuid import uuid4


BASE_URL = os.getenv("TEST_API_URL", "")
MAILPIT_URL = os.getenv("MAILPIT_URL", "")
WEB_ORIGIN = os.getenv("TEST_WEB_ORIGIN", "http://localhost:5173")


@unittest.skipUnless(BASE_URL and MAILPIT_URL, "set TEST_API_URL and MAILPIT_URL for identity HTTP probes")
class IdentityHttpTests(unittest.TestCase):
    def request(self, path: str, payload: dict | None = None, headers: dict | None = None, method: str | None = None) -> tuple[int, dict, dict]:
        request = Request(f"{BASE_URL}{path}", headers={"Host": "api", **(headers or {})}, method=method or ("POST" if payload is not None else "GET"))
        if payload is not None:
            request.data = json.dumps(payload).encode()
            request.add_header("Content-Type", "application/json")
        try:
            with urlopen(request, timeout=10) as response:
                headers_out = dict(response.headers)
                headers_out["Set-Cookie"] = ", ".join(response.headers.get_all("Set-Cookie", []))
                return response.status, headers_out, json.loads(response.read())
        except HTTPError as error:
            return error.code, dict(error.headers), json.loads(error.read())

    @staticmethod
    def cookies(headers: dict) -> tuple[str, str]:
        values = headers.get("Set-Cookie", "").split(", ")
        return tuple(re.search(r"(?:session_token|csrf_token)=([^;]+)", value).group(1) for value in values)  # type: ignore[return-value]

    def csrf_headers(self, session: str, csrf: str) -> dict[str, str]:
        return {"Origin": WEB_ORIGIN, "Cookie": f"session_token={session}; csrf_token={csrf}", "X-CSRF-Token": csrf}

    @staticmethod
    def bind_runtime_proof(cursor: psycopg.Cursor, session: str, identity: dict) -> None:
        """Bind the same active HTTP session proof before app_runtime inspection."""
        digest = hmac.new(os.environ["SESSION_SECRET"].encode(), session.encode(), hashlib.sha256).hexdigest()
        cursor.execute(
            "SELECT set_config('app.session_proof', %s, true), set_config('app.account_scope', 'tenant', true), set_config('app.user_id', %s, true), set_config('app.tenant_id', %s, true)",
            (digest, identity["user_id"], identity["tenant_id"]),
        )

    def upload_text_document(self, name: str, content: str, headers: dict[str, str]) -> tuple[int, dict]:
        boundary = f"----documents-{uuid4().hex}"
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

    def test_seeded_stack_new_admin_can_create_viewer(self) -> None:
        email = f"seed-regression-owner-{uuid4()}@example.com"
        status, headers, registered = self.request(
            "/api/auth/register",
            {"email": email, "password": "correct-horse", "tenant_name": "Seed Regression Lab"},
        )
        self.assertEqual((status, registered["role"]), (201, "admin"))
        session, csrf = self.cookies(headers)
        session_status = self.request("/api/auth/session", headers={"Cookie": f"session_token={session}"})
        self.assertEqual((session_status[0], session_status[2]["capabilities"]), (200, ["members:manage"]))
        viewer_email = f"seed-regression-viewer-{uuid4()}@example.com"
        created = self.request(
            "/api/members",
            {"email": viewer_email, "role": "viewer"},
            self.csrf_headers(session, csrf),
        )
        self.assertEqual((created[0], created[2]["role"]), (201, "viewer"))

    def test_document_list_is_db_backed_paginated_escaped_and_tenant_scoped(self) -> None:
        status, headers, owner = self.request(
            "/api/auth/register",
            {"email": f"document-owner-{uuid4()}@example.com", "password": "correct-horse", "tenant_name": "Document List Lab"},
        )
        self.assertEqual((status, owner["role"]), (201, "admin"))
        session, csrf = self.cookies(headers)
        authenticated = {"Cookie": f"session_token={session}"}
        mutation_headers = self.csrf_headers(session, csrf)
        empty = self.request("/api/documents", headers=authenticated)
        self.assertEqual((empty[0], empty[2]), (200, {"items": [], "total": 0, "page": 1, "per_page": 10, "pages": 0}))

        literal_name = f"literal%_ {uuid4()}.txt"
        pending_name = f"alpha pending {uuid4()}.txt"
        ready_name = f"zeta ready {uuid4()}.txt"
        pending_literal = self.upload_text_document(literal_name, "literal wildcard content", mutation_headers)
        pending = self.upload_text_document(pending_name, "pending content", mutation_headers)
        ready = self.upload_text_document(ready_name, "ready content", mutation_headers)
        for created, expected_name in ((pending_literal, literal_name), (pending, pending_name), (ready, ready_name)):
            self.assertEqual((created[0], created[1]["name"], created[1]["content_type"], created[1]["ingestion_status"]), (201, expected_name, "text/plain", "pending"))
            self.assertGreater(created[1]["size_bytes"], 0)
        self.assertEqual(self.request(f"/api/documents/{ready[1]['id']}/ingest", headers=mutation_headers, method="POST")[0], 200)
        detail = self.request(f"/api/documents/{ready[1]['id']}", headers=authenticated)
        self.assertEqual(detail[0], 200)
        self.assertEqual(detail[2]["active_chunk_count"], 1)
        self.assertEqual(detail[2]["latest_run"]["status"], "ready")

        default = self.request("/api/documents", headers=authenticated)
        self.assertEqual(default[0], 200)
        self.assertEqual((default[2]["total"], default[2]["page"], default[2]["per_page"], default[2]["pages"]), (3, 1, 10, 1))
        self.assertEqual(set(default[2]["items"][0]), {"id", "name", "content_type", "size_bytes", "ingestion_status"})
        self.assertEqual({item["id"] for item in default[2]["items"]}, {pending_literal[1]["id"], pending[1]["id"], ready[1]["id"]})

        page = self.request("/api/documents?page=2&per_page=1", headers=authenticated)
        self.assertEqual((page[0], page[2]["total"], page[2]["page"], page[2]["per_page"], page[2]["pages"], len(page[2]["items"])), (200, 3, 2, 1, 3, 1))
        escaped = self.request(f"/api/documents?search={quote('literal%_')}", headers=authenticated)
        self.assertEqual((escaped[0], escaped[2]["total"], escaped[2]["items"][0]["id"]), (200, 1, pending_literal[1]["id"]))
        self.assertEqual(self.request("/api/documents?status=pending", headers=authenticated)[2]["total"], 2)
        self.assertEqual(self.request("/api/documents?status=ready", headers=authenticated)[2]["total"], 1)
        for sort in ("name:asc", "name:desc", "status:asc", "status:desc"):
            with self.subTest(sort=sort):
                sorted_response = self.request(f"/api/documents?sort={quote(sort)}", headers=authenticated)
                self.assertEqual((sorted_response[0], sorted_response[2]["total"]), (200, 3))
                values = [item["name"] if sort.startswith("name") else item["ingestion_status"] for item in sorted_response[2]["items"]]
                self.assertEqual(values, sorted(values, reverse=sort.endswith("desc")))
        for query in ("status=unknown", "sort=name;DROP%20TABLE%20documents"):
            with self.subTest(query=query):
                self.assertEqual(self.request(f"/api/documents?{query}", headers=authenticated)[0], 422)

        viewer_email = f"document-viewer-{uuid4()}@example.com"
        self.assertEqual(self.request("/api/members", {"email": viewer_email, "role": "viewer"}, mutation_headers)[0], 201)
        self.assertEqual(self.request("/api/auth/recovery/request", {"email": viewer_email})[0], 202)
        with urlopen(f"{MAILPIT_URL}/api/v1/messages", timeout=10) as response:
            token_match = re.search(r"token=([A-Za-z0-9_-]+)", json.loads(response.read())["messages"][0]["Snippet"])
        self.assertIsNotNone(token_match)
        viewer_token = token_match.group(1) if token_match else ""
        self.assertEqual(self.request("/api/auth/recovery/confirm", {"token": viewer_token, "password": "viewer-password"})[0], 200)
        _, viewer_headers, _ = self.request("/api/auth/login", {"email": viewer_email, "password": "viewer-password"})
        viewer_session, _ = self.cookies(viewer_headers)
        viewer_headers = {"Cookie": f"session_token={viewer_session}"}
        self.assertEqual(self.request("/api/documents", headers=viewer_headers)[0], 200)
        self.assertEqual(self.request(f"/api/documents/{ready[1]['id']}", headers=viewer_headers)[0], 200)

        _, other_headers, _ = self.request(
            "/api/auth/register",
            {"email": f"document-other-{uuid4()}@example.com", "password": "correct-horse", "tenant_name": "Other Document List Lab"},
        )
        other_session, _ = self.cookies(other_headers)
        isolated = self.request("/api/documents", headers={"Cookie": f"session_token={other_session}"})
        self.assertEqual((isolated[0], isolated[2]["total"], isolated[2]["items"]), (200, 0, []))
        self.assertEqual(self.request(f"/api/documents/{ready[1]['id']}", headers={"Cookie": f"session_token={other_session}"})[0], 404)

    def test_document_reprocessing_replaces_active_chunks_without_stale_embeddings(self) -> None:
        status, headers, owner = self.request(
            "/api/auth/register",
            {"email": f"document-reprocess-owner-{uuid4()}@example.com", "password": "correct-horse", "tenant_name": "Document Reprocess Lab"},
        )
        self.assertEqual((status, owner["role"]), (201, "admin"))
        session, csrf = self.cookies(headers)
        mutation_headers = self.csrf_headers(session, csrf)
        read_headers = {"Cookie": f"session_token={session}"}
        document = self.upload_text_document(
            f"reprocess-{uuid4()}.txt",
            "reprocessing must preserve one retrievable document chunk across rebuilds",
            mutation_headers,
        )
        self.assertEqual((document[0], document[1]["ingestion_status"]), (201, "pending"))
        document_id = document[1]["id"]

        def retrieve() -> dict:
            status, _, body = self.request("/api/documents/retrieve", {"query": "retrievable rebuild document"}, read_headers)
            self.assertEqual(status, 200)
            self.assertTrue(any(citation["document_id"] == document_id for citation in body["citations"]))
            return body

        for attempt in range(3):
            with self.subTest(attempt=attempt + 1):
                ingested = self.request(f"/api/documents/{document_id}/ingest", headers=mutation_headers, method="POST")
                self.assertEqual((ingested[0], ingested[2]["ingestion_status"]), (200, "ready"))
                retrieve()

        database_url = os.environ["TEST_DATABASE_URL"].replace("postgresql+psycopg://", "postgresql://", 1)
        with psycopg.connect(database_url) as connection:
            with connection.cursor() as cursor:
                self.bind_runtime_proof(cursor, session, owner)
                cursor.execute("SELECT count(*), bool_and(active) FROM chunks WHERE tenant_id=%s AND document_id=%s", (owner["tenant_id"], document_id))
                self.assertEqual(cursor.fetchone(), (1, True))
                cursor.execute("SELECT count(*) FROM embeddings WHERE tenant_id=%s AND chunk_id IN (SELECT id FROM chunks WHERE tenant_id=%s AND document_id=%s)", (owner["tenant_id"], owner["tenant_id"], document_id))
                self.assertEqual(cursor.fetchone(), (1,))
                cursor.execute("SELECT count(*) FROM ingestion_runs WHERE tenant_id=%s AND document_id=%s AND status='ready'", (owner["tenant_id"], document_id))
                self.assertEqual(cursor.fetchone(), (3,))

        _, other_headers, _ = self.request(
            "/api/auth/register",
            {"email": f"document-reprocess-other-{uuid4()}@example.com", "password": "correct-horse", "tenant_name": "Other Reprocess Lab"},
        )
        other_session, _ = self.cookies(other_headers)
        isolated = self.request("/api/documents/retrieve", {"query": "retrievable rebuild document"}, {"Cookie": f"session_token={other_session}"})
        self.assertEqual((isolated[0], isolated[2]["citations"]), (200, []))

    def test_experiment_list_default_status_filter_search_sort_and_tenant_isolation(self) -> None:
        owner_email = f"experiment-list-owner-{uuid4()}@example.com"
        status, headers, _ = self.request(
            "/api/auth/register",
            {"email": owner_email, "password": "correct-horse", "tenant_name": "Experiment List Lab"},
        )
        self.assertEqual(status, 201)
        session, csrf = self.cookies(headers)
        authenticated = {"Cookie": f"session_token={session}"}
        mutation_headers = self.csrf_headers(session, csrf)

        self.assertEqual(self.request("/api/experiments", headers=authenticated)[0], 200)
        draft = self.request("/api/experiments", {"name": f"alpha {uuid4()}"}, mutation_headers)
        self.assertEqual(draft[0], 201)
        running = self.request("/api/experiments", {"name": f"beta {uuid4()}"}, mutation_headers)
        self.assertEqual(running[0], 201)
        self.assertEqual(
            self.request(f"/api/experiments/{running[2]['id']}", {"status": "running"}, mutation_headers, "PATCH")[0],
            200,
        )

        unfiltered = self.request("/api/experiments?search=beta&sort=name:asc", headers=authenticated)
        self.assertEqual(unfiltered[0], 200)
        self.assertEqual((unfiltered[2]["total"], [item["id"] for item in unfiltered[2]["items"]]), (1, [running[2]["id"]]))
        filtered = self.request("/api/experiments?status=running&sort=name:asc", headers=authenticated)
        self.assertEqual(filtered[0], 200)
        self.assertEqual((filtered[2]["total"], [item["id"] for item in filtered[2]["items"]]), (1, [running[2]["id"]]))

        _, other_headers, _ = self.request(
            "/api/auth/register",
            {"email": f"experiment-list-other-{uuid4()}@example.com", "password": "correct-horse", "tenant_name": "Other Experiment List Lab"},
        )
        other_session, _ = self.cookies(other_headers)
        isolated = self.request("/api/experiments", headers={"Cookie": f"session_token={other_session}"})
        self.assertEqual((isolated[0], isolated[2]["total"]), (200, 0))

    def test_experiment_archive_restore_http_contract(self) -> None:
        status, headers, owner = self.request(
            "/api/auth/register",
            {"email": f"experiment-archive-owner-{uuid4()}@example.com", "password": "correct-horse", "tenant_name": "Experiment Archive Lab"},
        )
        self.assertEqual(status, 201)
        session, csrf = self.cookies(headers)
        authenticated = {"Cookie": f"session_token={session}"}
        mutation_headers = self.csrf_headers(session, csrf)

        terminal = self.request("/api/experiments", {"name": f"terminal {uuid4()}"}, mutation_headers)
        self.assertEqual(terminal[0], 201)
        experiment_id = terminal[2]["id"]
        renamed = self.request(f"/api/experiments/{experiment_id}", {"name": "renamed terminal"}, mutation_headers, "PATCH")
        self.assertEqual((renamed[0], renamed[2]["name"]), (200, "renamed terminal"))
        self.assertEqual(self.request(f"/api/experiments/{experiment_id}", {"status": "running"}, mutation_headers, "PATCH")[0], 200)
        result = self.request(
            f"/api/experiments/{experiment_id}/results",
            {"status": "completed", "terminal_status": "completed", "metrics": []},
            mutation_headers,
        )
        self.assertEqual(result[0], 201)
        before_archive = self.request(f"/api/experiments/{experiment_id}", headers=authenticated)
        self.assertEqual((before_archive[0], before_archive[2]["status"], len(before_archive[2]["results"]), len(before_archive[2]["status_history"])), (200, "completed", 1, 2))

        archived = self.request(f"/api/experiments/{experiment_id}", {"archived": True}, mutation_headers, "PATCH")
        self.assertEqual((archived[0], archived[2]["status"], archived[2]["archived_by"]), (200, "completed", owner["user_id"]))
        self.assertIsNotNone(archived[2]["archived_at"])
        self.assertEqual(self.request("/api/experiments", headers=authenticated)[2]["total"], 0)
        archived_list = self.request("/api/experiments?archived=true", headers=authenticated)
        self.assertEqual((archived_list[0], archived_list[2]["total"], [item["id"] for item in archived_list[2]["items"]]), (200, 1, [experiment_id]))
        self.assertEqual(self.request(f"/api/experiments/{experiment_id}", {"status": "failed"}, mutation_headers, "PATCH")[0], 409)
        self.assertEqual(self.request(f"/api/experiments/{experiment_id}/results", {"status": "failed"}, mutation_headers)[0], 409)
        after_archive = self.request(f"/api/experiments/{experiment_id}", headers=authenticated)
        self.assertEqual((after_archive[2]["results"], after_archive[2]["status_history"]), (before_archive[2]["results"], before_archive[2]["status_history"]))

        draft = self.request("/api/experiments", {"name": f"draft {uuid4()}"}, mutation_headers)
        self.assertEqual(draft[0], 201)
        self.assertEqual(self.request(f"/api/experiments/{draft[2]['id']}", {"archived": True}, mutation_headers, "PATCH")[0], 200)
        self.assertEqual(self.request("/api/experiments", headers=authenticated)[2]["total"], 0)
        self.assertEqual(self.request("/api/experiments?archived=true", headers=authenticated)[2]["total"], 2)

        running = self.request("/api/experiments", {"name": f"running {uuid4()}"}, mutation_headers)
        self.assertEqual(running[0], 201)
        self.assertEqual(self.request(f"/api/experiments/{running[2]['id']}", {"status": "running"}, mutation_headers, "PATCH")[0], 200)
        self.assertEqual(self.request(f"/api/experiments/{running[2]['id']}", {"archived": True}, mutation_headers, "PATCH")[0], 409)

        _, other_headers, _ = self.request(
            "/api/auth/register",
            {"email": f"experiment-archive-other-{uuid4()}@example.com", "password": "correct-horse", "tenant_name": "Other Experiment Archive Lab"},
        )
        other_session, other_csrf = self.cookies(other_headers)
        self.assertEqual(self.request(f"/api/experiments/{experiment_id}", {"archived": False}, self.csrf_headers(other_session, other_csrf), "PATCH")[0], 404)

        restored = self.request(f"/api/experiments/{experiment_id}", {"archived": False}, mutation_headers, "PATCH")
        self.assertEqual((restored[0], restored[2]["archived_at"], restored[2]["archived_by"]), (200, None, None))
        after_restore = self.request(f"/api/experiments/{experiment_id}", headers=authenticated)
        self.assertEqual((after_restore[2]["results"], after_restore[2]["status_history"]), (before_archive[2]["results"], before_archive[2]["status_history"]))
        self.assertEqual((self.request("/api/experiments", headers=authenticated)[2]["total"], self.request("/api/experiments?archived=true", headers=authenticated)[2]["total"]), (2, 1))

        database_url = os.environ["TEST_DATABASE_URL"].replace("postgresql+psycopg://", "postgresql://", 1)
        with psycopg.connect(database_url) as connection:
            with connection.cursor() as cursor:
                self.bind_runtime_proof(cursor, session, owner)
                cursor.execute("SELECT action, metadata FROM audit_events WHERE tenant_id=%s AND resource=%s AND action IN ('experiment.archived', 'experiment.restored') ORDER BY created_at", (owner["tenant_id"], f"experiment:{experiment_id}"))
                audit_rows = cursor.fetchall()
        self.assertEqual(audit_rows, [("experiment.archived", {"archived": True, "previous_archived": False}), ("experiment.restored", {"archived": False, "previous_archived": True})])

    def test_dashboard_live_contract_is_tenant_scoped_and_date_bounded(self) -> None:
        owner_email = f"dashboard-owner-{uuid4()}@example.com"
        status, headers, owner = self.request(
            "/api/auth/register",
            {"email": owner_email, "password": "correct-horse", "tenant_name": "Dashboard Lab"},
        )
        self.assertEqual((status, owner["role"]), (201, "admin"))
        session, csrf = self.cookies(headers)
        authenticated = {"Cookie": f"session_token={session}"}
        mutation_headers = self.csrf_headers(session, csrf)
        experiment = self.request("/api/experiments", {"name": f"Dashboard experiment {uuid4()}"}, mutation_headers)
        self.assertEqual(experiment[0], 201)
        experiment_id = experiment[2]["id"]
        self.assertEqual(self.request(f"/api/experiments/{experiment_id}", {"status": "running"}, mutation_headers, "PATCH")[0], 200)
        first_result = self.request(
            f"/api/experiments/{experiment_id}/results",
            {"status": "completed", "input_summary": "first", "output_summary": "first", "metrics": [{"name": "accuracy", "type": "number", "value": 0.91, "unit": "%", "step": 1}]},
            mutation_headers,
        )
        self.assertEqual(first_result[0], 201)
        sleep(0.01)
        second_result = self.request(
            f"/api/experiments/{experiment_id}/results",
            {"status": "completed", "input_summary": "second", "output_summary": "second", "metrics": [{"name": "accuracy", "type": "number", "value": 0.42, "unit": "%", "step": 2}]},
            mutation_headers,
        )
        self.assertEqual(second_result[0], 201)

        today = date.today()
        dashboard = self.request(f"/api/dashboard?from={today.isoformat()}&to={today.isoformat()}", headers=authenticated)
        self.assertEqual(dashboard[0], 200)
        body = dashboard[2]
        self.assertEqual(set(body), {"range", "kpis", "daily", "statuses", "items", "total", "page", "per_page", "pages"})
        self.assertEqual(body["range"], {"from": today.isoformat(), "to": today.isoformat()})
        self.assertEqual(set(body["kpis"]), {"total", "running", "completed", "results"})
        self.assertEqual((body["kpis"]["total"], body["kpis"]["results"]), (1, 2))
        self.assertEqual(body["daily"], [{"date": today.isoformat(), "experiments": 1, "results": 2, "metric_average": 0.665}])
        self.assertEqual(body["statuses"], [{"status": "running", "count": 1}])
        self.assertEqual((body["total"], body["page"], body["per_page"], body["pages"]), (1, 1, 10, 1))
        self.assertEqual(len(body["items"]), 1)
        self.assertEqual(set(body["items"][0]), {"id", "name", "status", "created_at", "result_count", "latest_metric"})
        self.assertEqual((body["items"][0]["id"], body["items"][0]["result_count"], body["items"][0]["latest_metric"]), (experiment_id, 2, 0.42))

        yesterday = today - timedelta(days=1)
        changed_range = self.request(f"/api/dashboard?from={yesterday.isoformat()}&to={yesterday.isoformat()}", headers=authenticated)
        self.assertEqual(changed_range[0], 200)
        self.assertEqual((changed_range[2]["kpis"], changed_range[2]["total"], changed_range[2]["items"]), ({"total": 0, "running": 0, "completed": 0, "results": 0}, 0, []))
        self.assertEqual(changed_range[2]["daily"], [{"date": yesterday.isoformat(), "experiments": 0, "results": 0, "metric_average": None}])

        _, other_headers, _ = self.request(
            "/api/auth/register",
            {"email": f"dashboard-other-{uuid4()}@example.com", "password": "correct-horse", "tenant_name": "Other Dashboard Lab"},
        )
        other_session, _ = self.cookies(other_headers)
        isolated = self.request(f"/api/dashboard?from={today.isoformat()}&to={today.isoformat()}", headers={"Cookie": f"session_token={other_session}"})
        self.assertEqual(isolated[0], 200)
        self.assertEqual((isolated[2]["kpis"], isolated[2]["total"], isolated[2]["items"]), ({"total": 0, "running": 0, "completed": 0, "results": 0}, 0, []))

    def test_invalid_email_payloads_return_422_without_identity_side_effects(self) -> None:
        invalid_email = "not-an-email"
        with urlopen(f"{MAILPIT_URL}/api/v1/messages", timeout=10) as response:
            mail_count = len(json.loads(response.read())["messages"])

        for path, payload in (
            ("/api/auth/register", {"email": invalid_email, "password": "correct-horse", "tenant_name": "Test Lab"}),
            ("/api/auth/login", {"email": invalid_email, "password": "correct-horse"}),
            ("/api/auth/recovery/request", {"email": invalid_email}),
            ("/api/members", {"email": invalid_email, "role": "viewer"}),
        ):
            with self.subTest(path=path):
                status, headers, _ = self.request(path, payload)
                self.assertEqual(status, 422)
                self.assertNotIn("session_token=", headers.get("Set-Cookie", ""))

        with urlopen(f"{MAILPIT_URL}/api/v1/messages", timeout=10) as response:
            self.assertEqual(len(json.loads(response.read())["messages"]), mail_count)

    def test_registration_login_recovery_and_roles(self) -> None:
        email = f"owner-{uuid4()}@example.com"
        status, headers, registered = self.request("/api/auth/register", {"email": email, "password": "correct-horse", "tenant_name": "Test Lab"})
        self.assertEqual(status, 201)
        self.assertEqual(registered["role"], "admin")
        session, csrf = self.cookies(headers)
        tenant = registered["tenant_id"]
        self.assertEqual(self.request("/api/tenants/select", {"tenant_id": tenant}, self.csrf_headers(session, csrf))[0], 404)
        session_status = self.request("/api/auth/session", headers={"Cookie": f"session_token={session}"})
        self.assertEqual(session_status[0], 200)
        self.assertEqual(session_status[2], {"user_id": registered["user_id"], "tenant_id": tenant, "tenant_name": "Test Lab", "role": "admin", "capabilities": ["members:manage"]})
        viewer_email = f"viewer-{uuid4()}@example.com"
        self.assertEqual(self.request("/api/members")[0], 401)
        self.assertEqual(self.request("/api/members", {"email": viewer_email, "role": "viewer"}, self.csrf_headers(session, csrf))[0], 201)
        listed = self.request("/api/members?page=1&per_page=10&sort=email:asc", headers={"Cookie": f"session_token={session}"})
        self.assertEqual(listed[0], 200)
        self.assertEqual(set(listed[2]), {"items", "total", "page", "per_page", "pages"})
        self.assertEqual((listed[2]["total"], listed[2]["page"], listed[2]["per_page"], listed[2]["pages"]), (2, 1, 10, 1))
        self.assertEqual([item["email"] for item in listed[2]["items"]], sorted((email, viewer_email)))
        self.assertTrue(any(item["user_id"] == registered["user_id"] and item["role"] == "admin" for item in listed[2]["items"]))
        self.assertTrue(any(item["email"] == viewer_email and item["status"] == "active" and item["password_setup_required"] for item in listed[2]["items"]))
        self.assertEqual(self.request(f"/api/members?search={viewer_email.upper()}", headers={"Cookie": f"session_token={session}"})[2]["total"], 1)
        self.assertEqual(self.request("/api/members?search=no-match", headers={"Cookie": f"session_token={session}"})[2], {"items": [], "total": 0, "page": 1, "per_page": 10, "pages": 0})
        self.assertEqual(self.request("/api/members?role=viewer", headers={"Cookie": f"session_token={session}"})[2]["total"], 1)
        self.assertEqual(self.request("/api/members?status=active", headers={"Cookie": f"session_token={session}"})[2]["total"], 2)
        for sort in ("email:asc", "email:desc", "role:asc", "role:desc", "status:asc", "status:desc", "created_at:asc", "created_at:desc"):
            with self.subTest(sort=sort):
                self.assertEqual(self.request(f"/api/members?sort={sort}", headers={"Cookie": f"session_token={session}"})[0], 200)
        for query in ("page=0", "per_page=11", "role=owner", "status=pending", "sort=email;DROP%20TABLE%20users", f"tenant_id={uuid4()}"):
            with self.subTest(query=query):
                denied = self.request(f"/api/members?{query}", headers={"Cookie": f"session_token={session}"})
                self.assertEqual(denied[0], 422)
                self.assertIn("Los datos enviados no son válidos.", str(denied[2]))
        created = self.request("/api/experiments", {"name": "Model comparison"}, self.csrf_headers(session, csrf))
        self.assertEqual((created[0], created[2]["status"]), (201, "draft"))
        experiment_id = created[2]["id"]
        running = self.request(f"/api/experiments/{experiment_id}", {"status": "running"}, self.csrf_headers(session, csrf), "PATCH")
        self.assertEqual((running[0], running[2]["status"]), (200, "running"))
        result = self.request(f"/api/experiments/{experiment_id}/results", {"status": "completed", "terminal_status": "completed", "transition_reason": "  run verified  ", "input_summary": "dataset v1", "output_summary": "trained", "metrics": [{"name": "accuracy", "type": "number", "value": 0.91, "unit": "%", "step": 1}]}, self.csrf_headers(session, csrf))
        self.assertEqual((result[0], result[2]["metrics"][0]["value_type"], result[2]["experiment"]["status"]), (201, "number", "completed"))
        detail = self.request(f"/api/experiments/{experiment_id}", headers={"Cookie": f"session_token={session}"})
        self.assertEqual((detail[2]["status"], len(detail[2]["results"])), ("completed", 1))
        self.assertEqual(
            [(item["previous_status"], item["next_status"], item["actor_id"], item["reason"]) for item in detail[2]["status_history"]],
            [("draft", "running", registered["user_id"], None), ("running", "completed", registered["user_id"], "run verified")],
        )
        invalid_closure = self.request(f"/api/experiments/{experiment_id}/results", {"status": "failed", "terminal_status": "failed"}, self.csrf_headers(session, csrf))
        self.assertEqual(invalid_closure[0], 409)
        self.assertEqual(len(self.request(f"/api/experiments/{experiment_id}", headers={"Cookie": f"session_token={session}"})[2]["results"]), 1)
        self.assertEqual(self.request(f"/api/experiments/{experiment_id}", {"status": "running"}, self.csrf_headers(session, csrf), "PATCH")[0], 409)
        self.assertEqual(self.request(f"/api/experiments/{experiment_id}/results/{result[2]['id']}", {"output_summary": "edited"}, self.csrf_headers(session, csrf), "PATCH")[0], 404)

        login_status, login_headers, _ = self.request("/api/auth/login", {"email": email, "password": "correct-horse"})
        self.assertEqual(login_status, 200)
        login_session, _ = self.cookies(login_headers)
        self.assertEqual(self.request("/api/auth/session", headers={"Cookie": f"session_token={login_session}"})[2]["tenant_id"], tenant)

        known = self.request("/api/auth/recovery/request", {"email": email})
        unknown = self.request("/api/auth/recovery/request", {"email": f"unknown-{uuid4()}@example.com"})
        self.assertEqual((known[0], known[2]), (202, {"message": "Si la cuenta existe, se enviaron las instrucciones de recuperación."}))
        self.assertEqual((known[0], known[2]), (unknown[0], unknown[2]))
        with urlopen(f"{MAILPIT_URL}/api/v1/messages", timeout=10) as response:
            match = re.search(r"token=([A-Za-z0-9_-]+)", json.loads(response.read())["messages"][0]["Snippet"])
        self.assertIsNotNone(match)
        token = match.group(1) if match else ""
        self.assertEqual(self.request("/api/auth/recovery/confirm", {"token": token, "password": "updated-password"})[0], 200)
        self.assertEqual(self.request("/api/auth/recovery/confirm", {"token": token, "password": "another-password"})[0], 400)
        self.assertEqual(self.request("/api/auth/recovery/confirm", {"token": "expired-or-forged", "password": "another-password"})[0], 400)

        self.assertEqual(self.request("/api/auth/recovery/request", {"email": viewer_email})[0], 202)
        with urlopen(f"{MAILPIT_URL}/api/v1/messages", timeout=10) as response:
            match = re.search(r"token=([A-Za-z0-9_-]+)", json.loads(response.read())["messages"][0]["Snippet"])
        viewer_token = match.group(1) if match else ""
        self.assertTrue(viewer_token)
        self.assertEqual(self.request("/api/auth/recovery/confirm", {"token": viewer_token, "password": "viewer-password"})[0], 200)
        _, viewer_headers, _ = self.request("/api/auth/login", {"email": viewer_email, "password": "viewer-password"})
        viewer_session, viewer_csrf = self.cookies(viewer_headers)
        viewer_status = self.request("/api/auth/session", headers={"Cookie": f"session_token={viewer_session}"})
        self.assertEqual(viewer_status[2]["role"], "viewer")
        self.assertEqual(viewer_status[2]["capabilities"], [])
        denied_email = f"denied-{uuid4()}@example.com"
        self.assertEqual(self.request("/api/members", headers={"Cookie": f"session_token={viewer_session}"})[0], 403)
        self.assertEqual(self.request("/api/members", {"email": denied_email, "role": "member"}, self.csrf_headers(viewer_session, viewer_csrf))[0], 403)
        self.assertEqual(self.request(f"/api/experiments/{experiment_id}", headers={"Cookie": f"session_token={viewer_session}"})[0], 200)
        self.assertEqual(self.request("/api/experiments", {"name": "denied"}, self.csrf_headers(viewer_session, viewer_csrf))[0], 403)
        with urlopen(f"{MAILPIT_URL}/api/v1/messages", timeout=10) as response:
            before = len(json.loads(response.read())["messages"])
        self.assertEqual(self.request("/api/auth/recovery/request", {"email": denied_email})[0], 202)
        with urlopen(f"{MAILPIT_URL}/api/v1/messages", timeout=10) as response:
            self.assertEqual(len(json.loads(response.read())["messages"]), before)
        self.assertEqual(self.request("/api/invitations")[0], 404)

        other_email = f"owner-{uuid4()}@example.com"
        _, other_headers, _ = self.request("/api/auth/register", {"email": other_email, "password": "correct-horse", "tenant_name": "Other Lab"})
        other_session, other_csrf = self.cookies(other_headers)
        if other_session:
            isolated = self.request("/api/members", headers={"Cookie": f"session_token={other_session}"})
            self.assertEqual((isolated[0], isolated[2]["total"]), (200, 1))
            self.assertNotIn(email, [item["email"] for item in isolated[2]["items"]])
            self.assertEqual(self.request(f"/api/experiments/{experiment_id}", headers={"Cookie": f"session_token={other_session}"})[0], 404)
            self.assertEqual(self.request("/api/members", {"email": viewer_email, "role": "member"}, self.csrf_headers(other_session, other_csrf))[0], 409)

            unassigned_email = f"unassigned-{uuid4()}@example.com"
            database_url = os.environ["TEST_DATABASE_URL"].replace("postgresql+psycopg://", "postgresql://", 1)
            with psycopg.connect(database_url) as connection:
                with connection.cursor() as cursor:
                    cursor.execute("INSERT INTO users (id,email,password_hash) VALUES (%s,%s,%s)", (str(uuid4()), unassigned_email, hash_password("correct-horse")))
            self.assertEqual(self.request("/api/auth/login", {"email": unassigned_email, "password": "correct-horse"})[0], 403)

    def test_admin_can_manage_tenant_memberships_with_auditable_last_admin_protection(self) -> None:
        status, headers, owner = self.request(
            "/api/auth/register",
            {"email": f"membership-owner-{uuid4()}@example.com", "password": "correct-horse", "tenant_name": "Membership Lab"},
        )
        self.assertEqual(status, 201)
        owner_session, owner_csrf = self.cookies(headers)
        owner_mutation_headers = self.csrf_headers(owner_session, owner_csrf)

        viewer_email = f"membership-viewer-{uuid4()}@example.com"
        created = self.request("/api/members", {"email": viewer_email, "role": "viewer"}, owner_mutation_headers)
        self.assertEqual(created[0], 201)
        membership_id = created[2]["user_id"]

        edited = self.request(f"/api/members/{membership_id}", {"role": "member"}, owner_mutation_headers, "PATCH")
        self.assertEqual((edited[0], edited[2]), (200, {"membership_id": membership_id, "user_id": membership_id, "role": "member", "active": True}))
        deactivated = self.request(f"/api/members/{membership_id}", {"active": False}, owner_mutation_headers, "PATCH")
        self.assertEqual((deactivated[0], deactivated[2]["active"]), (200, False))
        reactivated = self.request(f"/api/members/{membership_id}", {"active": True}, owner_mutation_headers, "PATCH")
        self.assertEqual((reactivated[0], reactivated[2]["active"]), (200, True))

        self.assertEqual(self.request(f"/api/members/{owner['user_id']}", {"active": False}, owner_mutation_headers, "PATCH")[0], 409)
        self.assertEqual(self.request(f"/api/members/{owner['user_id']}", {"role": "member"}, owner_mutation_headers, "PATCH")[0], 409)
        self.assertEqual(self.request(f"/api/members/{membership_id}", {}, owner_mutation_headers, "PATCH")[0], 422)
        self.assertEqual(self.request(f"/api/members/{membership_id}", {"role": "member"}, owner_mutation_headers, "PATCH")[0], 409)

        _, other_headers, other_owner = self.request(
            "/api/auth/register",
            {"email": f"membership-other-{uuid4()}@example.com", "password": "correct-horse", "tenant_name": "Other Membership Lab"},
        )
        other_session, _ = self.cookies(other_headers)
        self.assertEqual(self.request(f"/api/members/{membership_id}", {"active": False}, self.csrf_headers(other_session, self.cookies(other_headers)[1]), "PATCH")[0], 404)

        self.assertEqual(self.request("/api/auth/recovery/request", {"email": viewer_email})[0], 202)
        with urlopen(f"{MAILPIT_URL}/api/v1/messages", timeout=10) as response:
            token_match = re.search(r"token=([A-Za-z0-9_-]+)", json.loads(response.read())["messages"][0]["Snippet"])
        assert token_match is not None
        self.assertEqual(self.request("/api/auth/recovery/confirm", {"token": token_match.group(1), "password": "viewer-password"})[0], 200)
        _, viewer_headers, _ = self.request("/api/auth/login", {"email": viewer_email, "password": "viewer-password"})
        viewer_session, viewer_csrf = self.cookies(viewer_headers)
        self.assertEqual(self.request(f"/api/members/{membership_id}", {"role": "viewer"}, self.csrf_headers(viewer_session, viewer_csrf), "PATCH")[0], 403)

        combined = self.request(
            f"/api/members/{membership_id}", {"role": "viewer", "active": False}, owner_mutation_headers, "PATCH"
        )
        self.assertEqual((combined[0], combined[2]["role"], combined[2]["active"]), (200, "viewer", False))
        database_url = os.environ["TEST_DATABASE_URL"].replace("postgresql+psycopg://", "postgresql://", 1)
        with psycopg.connect(database_url) as connection:
            with connection.cursor() as cursor:
                self.bind_runtime_proof(cursor, owner_session, owner)
                cursor.execute(
                    "SELECT action, outcome, resource, metadata FROM audit_events "
                    "WHERE tenant_id=%s AND actor_id=%s AND resource=%s "
                    "AND action LIKE 'membership.%%' ORDER BY created_at, id",
                    (owner["tenant_id"], owner["user_id"], f"membership:{membership_id}"),
                )
                audit_rows = cursor.fetchall()
        self.assertCountEqual(
            audit_rows,
            [
                ("membership.created", "success", f"membership:{membership_id}", {"role": "viewer", "active": True}),
                ("membership.role_changed", "success", f"membership:{membership_id}", {"previous_role": "viewer", "role": "member"}),
                ("membership.activation_changed", "success", f"membership:{membership_id}", {"previous_active": True, "active": False}),
                ("membership.activation_changed", "success", f"membership:{membership_id}", {"previous_active": False, "active": True}),
                ("membership.role_changed", "success", f"membership:{membership_id}", {"previous_role": "member", "role": "viewer"}),
                ("membership.activation_changed", "success", f"membership:{membership_id}", {"previous_active": True, "active": False}),
            ],
        )



if __name__ == "__main__":
    unittest.main()
