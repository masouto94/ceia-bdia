"""Behavioral contracts for the platform admin CLI's env-sourced email fallback.

Educational convenience: PLATFORM_ADMIN_EMAIL/PLATFORM_ADMIN_PASSWORD in .env let
`admin-tools` seed the single platform administrator without any argv, matching
how the six tenant fixture identities are already sourced from .env. --email
still overrides the environment when both are present.
"""

import argparse
import os
import unittest
from unittest import mock

from app.cli.seed_platform_admin import _email


class SeedPlatformAdminEmailFallbackTests(unittest.TestCase):
    def test_explicit_flag_wins_over_environment(self) -> None:
        args = argparse.Namespace(email="Flag@Equipo.edu")
        with mock.patch.dict(os.environ, {"PLATFORM_ADMIN_EMAIL": "env@equipo.edu"}):
            self.assertEqual(_email(args), "flag@equipo.edu")

    def test_falls_back_to_platform_admin_email_when_flag_is_absent(self) -> None:
        args = argparse.Namespace(email=None)
        with mock.patch.dict(os.environ, {"PLATFORM_ADMIN_EMAIL": "Env@Equipo.edu"}):
            self.assertEqual(_email(args), "env@equipo.edu")

    def test_raises_a_clear_actionable_error_without_flag_or_environment(self) -> None:
        args = argparse.Namespace(email=None)
        with mock.patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(SystemExit) as ctx:
                _email(args)
        self.assertIn("--email", str(ctx.exception))
        self.assertIn("PLATFORM_ADMIN_EMAIL", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
