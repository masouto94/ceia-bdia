"""RED route inventory for mutually exclusive platform and tenant surfaces."""

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MAIN = ROOT / "app/main.py"
AUTH = ROOT / "app/api/auth.py"
PLATFORM = ROOT / "app/api/platform.py"


class PlatformRouteInventoryTests(unittest.TestCase):
    def test_platform_router_is_registered_without_aggregate_endpoints(self) -> None:
        main = MAIN.read_text(encoding="utf-8")
        source = PLATFORM.read_text(encoding="utf-8")
        self.assertIn("platform_router", main)
        self.assertIn("app.include_router(platform_router)", main)
        self.assertIn('"/login"', source)
        self.assertIn('"/logout"', source)
        for forbidden in ("dashboard", "tenants", "aggregate", "audit-events"):
            self.assertNotIn(f'"/{forbidden}"', source)

    def test_tenant_surface_rejects_platform_scope_before_content_access(self) -> None:
        auth = AUTH.read_text(encoding="utf-8")
        tenant_context = auth[auth.index("def _tenant_context"):auth.index("def _issue_session")]
        self.assertIn("account_scope", tenant_context)
        self.assertIn("'tenant'", tenant_context)
        self.assertLess(tenant_context.index("account_scope"), tenant_context.index("tenant_id"))

    def test_platform_surface_rejects_tenant_scope_before_platform_seams(self) -> None:
        source = PLATFORM.read_text(encoding="utf-8")
        guard = source[source.index("def _platform_session"):source.index("@router.post(\"/login\"")]
        self.assertIn("account_scope", guard)
        self.assertIn("'platform'", guard)
        self.assertIn("HTTPException", guard)


if __name__ == "__main__":
    unittest.main()
