"""Static contract for deterministic dashboard seed fixtures."""

import unittest
from pathlib import Path


class FixtureDashboardTests(unittest.TestCase):
    def test_fixture_seeds_both_tenants_across_dashboard_history_without_secret_output(self) -> None:
        source = Path(__file__).with_name("seed-security-fixtures.py").read_text()
        self.assertIn("DASHBOARD_DAYS", source)
        self.assertIn("timedelta", source)
        self.assertIn("tenant/{slug}/dashboard/experiment", source)
        self.assertNotIn("print(password)", source)
        self.assertIn("AdminToolSettings", source)
        self.assertIn("class FixedEmbeddingProvider", source)
        self.assertIn("insert as pg_insert", source)
        self.assertIn("embedder.embed(content, \"passage\")", source)
        self.assertNotIn("FIXTURE_EMBEDDING", source)


if __name__ == "__main__":
    unittest.main()
