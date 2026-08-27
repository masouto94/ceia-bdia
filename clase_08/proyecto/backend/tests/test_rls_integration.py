# pyright: reportMissingImports=false

import hashlib
import hmac
import json
import os
import re
import unittest
from datetime import UTC, date, datetime, timedelta
from typing import Any, cast
from uuid import UUID, uuid4

from sqlalchemy import create_engine, text
from urllib.request import Request, urlopen


DATABASE_URL = os.getenv("TEST_DATABASE_URL", "")
BASE_URL = os.getenv("TEST_API_URL", "")


@unittest.skipUnless(DATABASE_URL and BASE_URL, "set TEST_DATABASE_URL and TEST_API_URL to run PostgreSQL RLS probes")
class RlsIntegrationTests(unittest.TestCase):
    @staticmethod
    def _register(label: str) -> tuple[UUID, UUID, str]:
        request = Request(
            f"{BASE_URL}/api/auth/register",
            data=json.dumps({"email": f"rls-{label}-{uuid4()}@example.com", "password": "correct-horse", "tenant_name": f"RLS {label}"}).encode(),
            headers={"Host": "api", "Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(request, timeout=10) as response:
            payload = json.loads(response.read())
            cookies = ", ".join(response.headers.get_all("Set-Cookie", []))
        match = re.search(r"session_token=([^;]+)", cookies)
        if match is None:
            raise AssertionError("registration did not issue a session")
        return UUID(payload["user_id"]), UUID(payload["tenant_id"]), match.group(1)

    @classmethod
    def setUpClass(cls) -> None:
        cls.engine = create_engine(DATABASE_URL, pool_size=1, max_overflow=0)
        cls.user_a, cls.tenant_a, session_a = cls._register("a")
        cls.user_b, cls.tenant_b, session_b = cls._register("b")
        cls.sessions = {cls.user_a: session_a, cls.user_b: session_b}

    @classmethod
    def _context(cls, connection, user_id, tenant_id) -> None:
        digest = hmac.new(os.environ["SESSION_SECRET"].encode(), cls.sessions[user_id].encode(), hashlib.sha256).hexdigest()
        connection.execute(
            text("SELECT set_config('app.session_proof', :proof, true), set_config('app.account_scope', 'tenant', true), set_config('app.user_id', :user, true), set_config('app.tenant_id', :tenant, true)"),
            {"proof": digest, "user": str(user_id), "tenant": str(tenant_id)},
        )

    def test_missing_and_cross_tenant_context_leave_victim_unchanged(self) -> None:
        with self.engine.connect() as connection:
            with connection.begin():
                self.assertEqual(connection.execute(text("SELECT count(*) FROM tenants")).scalar_one(), 0)
            with connection.begin():
                connection.execute(
                text("SELECT set_config('app.user_id', :user, true), set_config('app.tenant_id', :tenant, true)"),
                {"user": str(self.user_a), "tenant": str(self.tenant_a)},
                )
                self.assertEqual(connection.execute(text("SELECT count(*) FROM tenants")).scalar_one(), 0)
            with connection.begin():
                self._context(connection, self.user_a, self.tenant_a)
                self.assertEqual(connection.execute(text("SELECT count(*) FROM tenants")).scalar_one(), 1)
                self.assertEqual(connection.execute(text("SELECT count(*) FROM tenants WHERE id = :id"), {"id": self.tenant_b}).scalar_one(), 0)
                with self.assertRaises(Exception):
                    connection.execute(
                        text("INSERT INTO tenants (id, name) VALUES (:id, :name)"),
                        {"id": uuid4(), "name": "forged"},
                    )
        with self.engine.begin() as connection:
            self._context(connection, self.user_b, self.tenant_b)
            self.assertEqual(
                connection.execute(text("SELECT name FROM tenants WHERE id = :id"), {"id": self.tenant_b}).scalar_one(),
                "RLS b",
            )

    def test_experiment_status_history_is_tenant_isolated_and_append_only(self) -> None:
        experiment_id, transition_id = uuid4(), uuid4()
        with self.engine.begin() as connection:
            self._context(connection, self.user_a, self.tenant_a)
            connection.execute(
                text("INSERT INTO experiments (id, tenant_id, creator_id, name, status) VALUES (:id, :tenant, :actor, 'history', 'running')"),
                {"id": experiment_id, "tenant": self.tenant_a, "actor": self.user_a},
            )
            connection.execute(
                text("INSERT INTO experiment_status_transitions (id, tenant_id, experiment_id, previous_status, next_status, actor_id) VALUES (:id, :tenant, :experiment, 'draft', 'running', :actor)"),
                {"id": transition_id, "tenant": self.tenant_a, "experiment": experiment_id, "actor": self.user_a},
            )
        with self.engine.begin() as connection:
            self._context(connection, self.user_b, self.tenant_b)
            self.assertEqual(
                connection.execute(text("SELECT count(*) FROM experiment_status_transitions WHERE id=:id"), {"id": transition_id}).scalar_one(),
                0,
            )
        with self.assertRaises(Exception):
            with self.engine.begin() as connection:
                self._context(connection, self.user_a, self.tenant_a)
                connection.execute(
                    text("UPDATE experiment_status_transitions SET reason=:reason WHERE id=:id"),
                    {"id": transition_id, "reason": "rewritten"},
                )

    def test_archived_experiment_metadata_remains_tenant_isolated(self) -> None:
        experiment_id = uuid4()
        with self.engine.begin() as connection:
            self._context(connection, self.user_a, self.tenant_a)
            connection.execute(text("INSERT INTO experiments (id,tenant_id,creator_id,name,status,archived_at,archived_by) VALUES (:id,:tenant,:actor,'archived','completed',now(),:actor)"), {"id": experiment_id, "tenant": self.tenant_a, "actor": self.user_a})
        with self.engine.begin() as connection:
            self._context(connection, self.user_b, self.tenant_b)
            self.assertEqual(connection.execute(text("SELECT count(*) FROM experiments WHERE id=:id AND archived_at IS NOT NULL"), {"id": experiment_id}).scalar_one(), 0)
        with self.assertRaises(Exception):
            with self.engine.begin() as connection:
                self._context(connection, self.user_a, self.tenant_a)
                connection.execute(text("UPDATE experiments SET status='failed' WHERE id=:id"), {"id": experiment_id})

    def test_audit_definer_is_the_only_append_path_and_global_count_bypasses_force_rls(self) -> None:
        resource = f"recovery-{uuid4().hex}"
        with self.assertRaises(Exception):
            with self.engine.begin() as connection:
                self._context(connection, self.user_a, self.tenant_a)
                connection.execute(text("INSERT INTO audit_events (id,actor_id,tenant_id,action,outcome,metadata) VALUES (:id,:actor,:tenant,'auth.login','success','{}'::jsonb)"), {"id": uuid4(), "actor": self.user_a, "tenant": self.tenant_a})
        for statement in ("UPDATE audit_events SET outcome='failed' WHERE false", "DELETE FROM audit_events WHERE false", "UPDATE ingestion_runs SET status='failed' WHERE false", "DELETE FROM ingestion_runs WHERE false"):
            with self.subTest(statement=statement), self.assertRaises(Exception):
                with self.engine.begin() as connection:
                    self._context(connection, self.user_a, self.tenant_a)
                    connection.execute(text(statement))
        with self.engine.begin() as connection:
            self._context(connection, self.user_a, self.tenant_a)
            event_id = connection.execute(text("SELECT append_audit_event(:actor,:tenant,'auth.login','success','session',CAST(:metadata AS jsonb))"), {"actor": self.user_a, "tenant": self.tenant_a, "metadata": "{}"}).scalar_one()
            self.assertIsNotNone(event_id)
            self.assertEqual(connection.execute(text("SELECT count(*) FROM audit_events WHERE id=:id"), {"id": event_id}).scalar_one(), 1)
            self.assertEqual(connection.execute(text("SELECT recovery_request_count(:resource)"), {"resource": resource}).scalar_one(), 0)
            connection.execute(text("SELECT append_audit_event(NULL,NULL,'auth.recovery.request','success',:resource,CAST(:metadata AS jsonb))"), {"resource": resource, "metadata": "{}"})
            self.assertEqual(connection.execute(text("SELECT recovery_request_count(:resource)"), {"resource": resource}).scalar_one(), 1)
        for action, outcome, metadata in (("unknown.action", "success", "{}"), ("auth.login", "accepted", "{}"), ("auth.login", "success", '{"token":"secret"}')):
            with self.subTest(action=action, outcome=outcome, metadata=metadata), self.assertRaises(Exception):
                with self.engine.begin() as connection:
                    self._context(connection, self.user_a, self.tenant_a)
                    connection.execute(text("SELECT append_audit_event(:actor,:tenant,:action,:outcome,'resource',CAST(:metadata AS jsonb))"), {"actor": self.user_a, "tenant": self.tenant_a, "action": action, "outcome": outcome, "metadata": metadata})

    def test_audit_definer_rejects_forged_request_context_and_global_events(self) -> None:
        calls = (
            (self.user_b, self.tenant_a, "auth.login", "success"),
            (self.user_a, self.tenant_b, "auth.login", "success"),
            (None, None, "auth.login", "success"),
        )
        for actor, tenant, action, outcome in calls:
            with self.subTest(actor=actor, tenant=tenant, action=action), self.assertRaises(Exception):
                with self.engine.begin() as connection:
                    self._context(connection, self.user_a, self.tenant_a)
                    connection.execute(
                        text("SELECT append_audit_event(:actor,:tenant,:action,:outcome,'resource','{}'::jsonb)"),
                        {"actor": actor, "tenant": tenant, "action": action, "outcome": outcome},
                    )
        with self.engine.begin() as connection:
            self._context(connection, self.user_a, self.tenant_a)
            self.assertIsNotNone(connection.execute(
                text("SELECT append_audit_event(:actor,:tenant,'auth.login','success','resource','{}'::jsonb)"),
                {"actor": self.user_a, "tenant": self.tenant_a},
            ).scalar_one())
            self.assertIsNotNone(connection.execute(
                text("SELECT append_audit_event(NULL,NULL,'auth.recovery.request','rate_limited','resource','{}'::jsonb)")
            ).scalar_one())

    def test_dashboard_and_audit_repositories_use_inclusive_date_ranges(self) -> None:
            from app.api.audit import AuditQuery
            from app.repositories.audit import AuditRepository
            from app.repositories.dashboard import DashboardRepository

            selected_day = date(2026, 2, 3)
            start = datetime(2026, 2, 3, tzinfo=UTC)
            late_to = start + timedelta(days=1) - timedelta(microseconds=1)
            next_day = start + timedelta(days=1)
            dashboard_ids = (uuid4(), uuid4(), uuid4())
            audit_experiment_id = uuid4()
            audit_ids = (uuid4(), uuid4(), uuid4())

            with self.engine.connect() as connection:
                transaction = connection.begin()
                try:
                    self._context(connection, self.user_a, self.tenant_a)
                    for experiment_id, created_at in zip(dashboard_ids, (start, late_to, next_day), strict=True):
                        connection.execute(
                            text("INSERT INTO experiments (id, tenant_id, creator_id, name, status, created_at) VALUES (:id, :tenant, :actor, :name, 'running', :created_at)"),
                            {"id": experiment_id, "tenant": self.tenant_a, "actor": self.user_a, "name": f"dashboard-{experiment_id}", "created_at": created_at},
                        )
                    self._context(connection, self.user_b, self.tenant_b)
                    connection.execute(
                        text("INSERT INTO experiments (id, tenant_id, creator_id, name, status, created_at) VALUES (:id, :tenant, :actor, :name, 'running', :created_at)"),
                        {"id": uuid4(), "tenant": self.tenant_b, "actor": self.user_b, "name": "tenant-b-boundary", "created_at": start},
                    )

                    self._context(connection, self.user_a, self.tenant_a)
                    dashboard = DashboardRepository(cast(Any, connection)).overview(self.tenant_a, selected_day, selected_day, "", "", "created_at:asc", 1, 10)
                    dashboard_item_ids = {UUID(str(item["id"])) for item in dashboard["items"]}
                    self.assertEqual(dashboard["kpis"]["total"], 2)
                    self.assertEqual(dashboard["total"], 2)
                    self.assertEqual(dashboard_item_ids, set(dashboard_ids[:2]))
                    self.assertNotIn(dashboard_ids[2], dashboard_item_ids)

                    connection.execute(
                        text("INSERT INTO experiments (id, tenant_id, creator_id, name, status, created_at) VALUES (:id, :tenant, :actor, :name, 'running', :created_at)"),
                        {"id": audit_experiment_id, "tenant": self.tenant_a, "actor": self.user_a, "name": f"audit-{audit_experiment_id}", "created_at": start},
                    )
                    for transition_id, occurred_at in zip(audit_ids, (start, late_to, next_day), strict=True):
                        connection.execute(
                            text("INSERT INTO experiment_status_transitions (id, tenant_id, experiment_id, previous_status, next_status, actor_id, occurred_at) VALUES (:id, :tenant, :experiment, 'draft', 'running', :actor, :occurred_at)"),
                            {"id": transition_id, "tenant": self.tenant_a, "experiment": audit_experiment_id, "actor": self.user_a, "occurred_at": occurred_at},
                        )

                    date_bounds = AuditQuery(**cast(Any, {"from": selected_day.isoformat(), "to": selected_day.isoformat()}))
                    assert date_bounds.from_at is not None and date_bounds.to_at is not None
                    items, total = AuditRepository(cast(Any, connection)).list(
                        self.tenant_a, page=1, per_page=10, from_at=date_bounds.from_at, to_at=date_bounds.to_at,
                        actor_id=None, action="experiment.status_transition", outcome=None, search=str(audit_experiment_id),
                    )
                    self.assertEqual(total, 2)
                    self.assertEqual({UUID(item["id"]) for item in items}, set(audit_ids[:2]))
                    self.assertNotIn(audit_ids[2], {UUID(item["id"]) for item in items})

                    exact_bounds = AuditQuery(**cast(Any, {"from": start, "to": late_to}))
                    assert exact_bounds.from_at is not None and exact_bounds.to_at is not None
                    _, exact_total = AuditRepository(cast(Any, connection)).list(
                        self.tenant_a, page=1, per_page=10, from_at=exact_bounds.from_at, to_at=exact_bounds.to_at,
                        actor_id=None, action="experiment.status_transition", outcome=None, search=str(audit_experiment_id),
                    )
                    self.assertEqual(exact_total, 1)
                finally:
                    transaction.rollback()

    def test_pooled_connection_does_not_retain_context(self) -> None:
        with self.engine.begin() as connection:
            self._context(connection, self.user_a, self.tenant_a)
            self.assertEqual(connection.execute(text("SELECT count(*) FROM tenants")).scalar_one(), 1)
        with self.engine.begin() as connection:
            self.assertEqual(connection.execute(text("SELECT count(*) FROM tenants")).scalar_one(), 0)


if __name__ == "__main__":
    unittest.main()
