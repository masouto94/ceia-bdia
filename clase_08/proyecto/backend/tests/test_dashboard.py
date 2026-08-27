# pyright: reportMissingImports=false
"""Dashboard contracts remain tenant-scoped and date-bounded."""

import unittest
from datetime import date
from pathlib import Path
from typing import Any, cast
from unittest.mock import patch
from uuid import uuid4

_ENVIRONMENT = {"RUNTIME_DATABASE_URL": "postgresql+psycopg://runtime:password@db/student_project",
        "AUTH_DATABASE_URL": "postgresql+psycopg://auth:password@db/student_project", "ASSISTANT_DATABASE_URL": "postgresql+psycopg://assistant:password@db/student_project", "MINIO_ACCESS_KEY": "local-user", "MINIO_SECRET_KEY": "local-password", "SMTP_FROM": "noreply@example.test", "SESSION_SECRET": "test-session-secret", "RECOVERY_TOKEN_SECRET": "test-recovery-secret"}


class DashboardContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.environment = patch.dict("os.environ", _ENVIRONMENT, clear=False)
        cls.environment.start()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.environment.stop()

    def test_query_rejects_invalid_or_excessive_ranges(self) -> None:
        from pydantic import ValidationError
        from app.api.dashboard_schemas import DashboardQuery

        self.assertEqual(DashboardQuery(from_date=date(2025, 1, 1), to_date=date(2025, 1, 31)).from_date.isoformat(), "2025-01-01")
        self.assertEqual(DashboardQuery(from_date=date(2024, 1, 1), to_date=date(2024, 12, 31)).to_date.isoformat(), "2024-12-31")
        for start, end in ((date(2025, 2, 1), date(2025, 1, 1)), (date(2024, 1, 1), date(2025, 1, 1))):
            with self.assertRaises(ValidationError):
                DashboardQuery(from_date=start, to_date=end)

    def test_repository_uses_tenant_marker_and_returns_aggregate_contract(self) -> None:
        from app.repositories.dashboard import DashboardRepository

        tenant = uuid4()
        captured: list[tuple[str, dict]] = []

        class Result:
            def mappings(self): return self
            def one(self): return {"total": 2, "running": 1, "completed": 1, "results": 3}
            def all(self): return []
            def scalar_one(self): return 2
        class SessionStub:
            def execute(self, statement: object, values: dict[str, object]) -> Result:
                captured.append((str(statement), values)); return Result()

        payload = DashboardRepository(cast(Any, SessionStub())).overview(tenant, date(2025, 1, 1), date(2025, 1, 31), "", "", "created_at:desc", 1, 10)
        self.assertEqual(payload["kpis"]["total"], 2)
        self.assertTrue(all(values["tenant"] == tenant for _, values in captured))
        self.assertTrue(any("tenant_id" in sql for sql, _ in captured))
        statements = "\n".join(sql for sql, _ in captured)
        self.assertNotIn(":to::date", statements)
        self.assertNotIn(":from::date", statements)
        self.assertIn("CAST(:to AS date)", statements)
        self.assertIn("count(DISTINCT e.id) FILTER (WHERE e.status='running')", statements)
        self.assertIn("ORDER BY m.recorded_at DESC", statements)

    def test_route_is_registered_as_a_read_only_dashboard_endpoint(self) -> None:
        route_source = Path("app/api/dashboard.py").read_text()
        main_source = Path("app/main.py").read_text()
        self.assertIn('@router.get("")', route_source)
        self.assertIn("app.include_router(dashboard_router)", main_source)


if __name__ == "__main__":
    unittest.main()
