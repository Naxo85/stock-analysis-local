from __future__ import annotations

import sys
import unittest

from src.local_runner.command_worker import (
    ACTION_CORE,
    ACTION_TICKER,
    ACTION_TRADING,
    CORE_CONFIG_URI,
    CommandRequest,
    build_execution,
)


class CommandRequestTests(unittest.TestCase):
    def test_ticker_command_is_normalized(self) -> None:
        request = CommandRequest.from_payload(
            {
                "id": "cmd-001",
                "action": ACTION_TICKER,
                "ticker": "hood",
            }
        )

        self.assertEqual(request.ticker, "HOOD")
        self.assertEqual(request.max_parallel, 6)

    def test_rejects_arbitrary_action(self) -> None:
        with self.assertRaisesRegex(ValueError, "invalid_action"):
            CommandRequest.from_payload(
                {
                    "id": "cmd-002",
                    "action": "run_shell",
                }
            )

    def test_rejects_invalid_ticker(self) -> None:
        with self.assertRaisesRegex(ValueError, "invalid_ticker"):
            CommandRequest.from_payload(
                {
                    "id": "cmd-003",
                    "action": ACTION_TICKER,
                    "ticker": "HOOD; calc.exe",
                }
            )

    def test_rejects_parallelism_above_cap(self) -> None:
        with self.assertRaisesRegex(ValueError, "invalid_max_parallel"):
            CommandRequest.from_payload(
                {
                    "id": "cmd-004",
                    "action": ACTION_TRADING,
                    "max_parallel": 9,
                }
            )


class BuildExecutionTests(unittest.TestCase):
    def test_ticker_execution(self) -> None:
        request = CommandRequest.from_payload(
            {
                "id": "cmd-ticker",
                "action": ACTION_TICKER,
                "ticker": "RKLB",
            }
        )

        execution = build_execution(request)

        self.assertEqual(
            execution.argv,
            (
                sys.executable,
                "-m",
                "src.local_runner.run_one",
                "RKLB",
                "--run-full",
            ),
        )

    def test_trading_execution(self) -> None:
        request = CommandRequest.from_payload(
            {
                "id": "cmd-trading",
                "action": ACTION_TRADING,
                "max_parallel": 4,
            }
        )

        execution = build_execution(request)

        self.assertIn("--from-gcs", execution.argv)
        self.assertEqual(execution.argv[-1], "4")

    def test_core_execution(self) -> None:
        request = CommandRequest.from_payload(
            {
                "id": "cmd-core",
                "action": ACTION_CORE,
                "max_parallel": 6,
            }
        )

        execution = build_execution(request)

        self.assertIn("--config-gcs", execution.argv)
        self.assertIn(CORE_CONFIG_URI, execution.argv)


if __name__ == "__main__":
    unittest.main()
