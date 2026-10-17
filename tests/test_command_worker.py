from __future__ import annotations

import json
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

from src.local_runner.command_worker import (
    ACTION_BUY_SHOT,
    ACTION_CORE,
    ACTION_MARKET,
    ACTION_REMOVE_TICKER,
    ACTION_SELL_SHOT,
    ACTION_TICKER,
    ACTION_TRADING,
    CORE_CONFIG_URI,
    MARKET_CONFIG_URI,
    CommandRequest,
    _batch_completion_counts,
    _command_environment,
    build_execution,
    _resume_batch_execution_if_available,
)


class CommandRequestTests(unittest.TestCase):
    def test_market_command_resumes_matching_unfinished_checkpoint(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            run_dir = root / "logs" / "batch" / "2026-09-17" / "08-48-14"
            run_dir.mkdir(parents=True)
            state_path = run_dir / "pipeline_state.json"
            state_path.write_text("{}", encoding="utf-8")
            (run_dir / "sheet_progress.json").write_text(
                json.dumps(
                    {
                        "command_id": "cmd-resume",
                        "status": "running",
                    }
                ),
                encoding="utf-8",
            )
            request = CommandRequest.from_payload(
                {
                    "id": "cmd-resume",
                    "action": ACTION_MARKET,
                }
            )

            execution = _resume_batch_execution_if_available(
                request,
                build_execution(request),
                repo_root=root,
            )

            self.assertIn("--resume-pipeline-from", execution.argv)
            self.assertEqual(execution.argv[-1], str(state_path))

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


    def test_tracking_command_parses_menu_fields(self) -> None:
        request = CommandRequest.from_payload(
            {
                "id": "cmd-buy",
                "action": ACTION_BUY_SHOT,
                "ticker": "new",
                "group_id": "ai_platforms",
                "observed_shots": 1,
            }
        )

        self.assertEqual(request.ticker, "NEW")
        self.assertEqual(request.group_id, "ai_platforms")
        self.assertEqual(request.observed_shots, 1)


class BuildExecutionTests(unittest.TestCase):
    def test_tracking_executions(self) -> None:
        cases = (
            (ACTION_BUY_SHOT, "buy"),
            (ACTION_SELL_SHOT, "sell"),
            (ACTION_REMOVE_TICKER, "remove"),
        )
        for action, expected in cases:
            request = CommandRequest.from_payload(
                {
                    "id": f"cmd-{expected}",
                    "action": action,
                    "ticker": "RKLB",
                    "observed_shots": 1,
                }
            )
            execution = build_execution(request)
            self.assertIn("src.local_runner.manage_market_tracking", execution.argv)
            action_index = execution.argv.index("--action")
            self.assertEqual(execution.argv[action_index + 1], expected)

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

    def test_manual_trading_forces_daily_on_friday(self) -> None:
        request = CommandRequest.from_payload(
            {
                "id": "cmd-trading-friday",
                "action": ACTION_TRADING,
                "max_parallel": 4,
            }
        )

        execution = build_execution(request, on_date=date(2026, 9, 4))

        self.assertIn("--analysis-mode", execution.argv)
        mode_index = execution.argv.index("--analysis-mode")
        self.assertEqual(execution.argv[mode_index + 1], "daily")

    def test_manual_core_forces_daily_on_saturday(self) -> None:
        request = CommandRequest.from_payload(
            {
                "id": "cmd-core-saturday",
                "action": ACTION_CORE,
                "max_parallel": 6,
            }
        )

        execution = build_execution(request, on_date=date(2026, 9, 5))

        self.assertIn("--analysis-mode", execution.argv)
        mode_index = execution.argv.index("--analysis-mode")
        self.assertEqual(execution.argv[mode_index + 1], "daily")

    def test_manual_batch_keeps_calendar_routing_on_sunday(self) -> None:
        request = CommandRequest.from_payload(
            {
                "id": "cmd-trading-sunday",
                "action": ACTION_TRADING,
            }
        )

        execution = build_execution(request, on_date=date(2026, 9, 6))

        self.assertNotIn("--analysis-mode", execution.argv)

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

    def test_market_execution_uses_the_same_real_batch_pipeline(self) -> None:
        request = CommandRequest.from_payload(
            {
                "id": "cmd-market",
                "action": ACTION_MARKET,
                "max_parallel": 6,
            }
        )

        execution = build_execution(request, on_date=date(2026, 9, 7))

        self.assertEqual(execution.label, "MERCADO")
        self.assertIn(MARKET_CONFIG_URI, execution.argv)
        self.assertIn("--upload-real", execution.argv)
        self.assertIn("--update-analysts", execution.argv)
        self.assertIn("--update-ibkr-news", execution.argv)
        profile_index = execution.argv.index("--analysis-profile")
        self.assertEqual(execution.argv[profile_index + 1], "trading")


class BatchCompletionCountTests(unittest.TestCase):
    def test_batch_child_always_uses_utf8_console_output(self) -> None:
        request = CommandRequest.from_payload(
            {"id": "cmd-utf8", "action": ACTION_MARKET}
        )

        environment = _command_environment(request)

        self.assertEqual(environment["PYTHONIOENCODING"], "utf-8")
        self.assertEqual(environment["PYTHONUTF8"], "1")

    def test_extracts_partial_batch_counts(self) -> None:
        stdout = (
            "OK AUR\n"
            "OK: 32/38 análisis generados y subidos. "
            "Fallidos: TLN, NBIS.\n"
        )

        self.assertEqual(_batch_completion_counts(stdout), (32, 38))

    def test_uses_last_summary_and_rejects_missing_summary(self) -> None:
        self.assertEqual(
            _batch_completion_counts("OK: 1/2\nretry\nOK: 2/2"),
            (2, 2),
        )
        self.assertIsNone(_batch_completion_counts("gateway failed"))


if __name__ == "__main__":
    unittest.main()
