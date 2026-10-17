from __future__ import annotations

import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch

from src.local_runner.run_one import _run_preflight_updates


class IbkrNewsFailClosedTests(unittest.TestCase):
    @patch("src.local_runner.run_one.subprocess.run")
    def test_news_update_failure_aborts_preflight(self, run_mock) -> None:
        run_mock.side_effect = (
            subprocess.CompletedProcess([], 0, stdout="ok", stderr=""),
            subprocess.CompletedProcess([], 1, stdout="news failed", stderr=""),
        )

        with self.assertRaisesRegex(
            RuntimeError,
            "ibkr_news_update_failed_after_gateway_restart",
        ):
            _run_preflight_updates(Path("."), "HOOD")

    @patch("src.local_runner.run_one.subprocess.run")
    def test_analyst_failure_remains_non_blocking_when_news_succeeds(self, run_mock) -> None:
        run_mock.side_effect = (
            subprocess.CompletedProcess([], 1, stdout="analyst failed", stderr=""),
            subprocess.CompletedProcess([], 0, stdout="news ok", stderr=""),
        )

        self.assertEqual(_run_preflight_updates(Path("."), "HOOD"), 0)


if __name__ == "__main__":
    unittest.main()
