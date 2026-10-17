from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.local_runner.update_analysis_sources_pipeline import main


class SourcePipelineTests(unittest.TestCase):
    def test_resume_skips_completed_source_marker(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            progress = root / "progress"
            progress.mkdir()
            marker = {
                "ticker": "AAA",
                "status": "ok",
                "news": {"status": "ok"},
                "analysts": {"status": "ok"},
            }
            (progress / "AAA.json").write_text(
                json.dumps(marker), encoding="utf-8"
            )
            with (
                patch(
                    "src.local_runner.update_analysis_sources_pipeline._find_repo_root",
                    return_value=root,
                ),
                patch(
                    "src.local_runner.update_analysis_sources_pipeline.run_news_update"
                ) as news,
                patch(
                    "src.local_runner.update_analysis_sources_pipeline.run_analyst_update"
                ) as analyst,
            ):
                exit_code = main(
                    [
                        "--tickers",
                        "AAA",
                        "--progress-dir",
                        str(progress),
                        "--update-news",
                        "--update-analysts",
                    ]
                )

            self.assertEqual(exit_code, 0)
            news.assert_not_called()
            analyst.assert_not_called()

    def test_successful_news_releases_ticker_marker(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            progress = root / "progress"
            with (
                patch(
                    "src.local_runner.update_analysis_sources_pipeline._find_repo_root",
                    return_value=root,
                ),
                patch(
                    "src.local_runner.update_analysis_sources_pipeline._iter_earnings_contexts",
                    return_value=iter([("AAA", {"source_status": "live"})]),
                ),
                patch(
                    "src.local_runner.update_analysis_sources_pipeline.run_news_update",
                    return_value={"ticker": "AAA", "status": "ok"},
                ),
                patch(
                    "src.local_runner.update_analysis_sources_pipeline.run_analyst_update",
                    return_value={
                        "ticker": "AAA",
                        "status": "ok",
                        "earnings_context": {"source_status": "live"},
                    },
                ),
            ):
                exit_code = main(
                    [
                        "--tickers",
                        "AAA",
                        "--progress-dir",
                        str(progress),
                        "--update-news",
                        "--update-analysts",
                        "--sleep-seconds",
                        "0",
                    ]
                )

            marker = json.loads((progress / "AAA.json").read_text(encoding="utf-8"))
            self.assertEqual(exit_code, 0)
            self.assertEqual(marker["status"], "ok")

    def test_news_failure_stays_closed_after_gateway_retry(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            progress = root / "progress"
            failed = {"ticker": "AAA", "status": "failed", "error": "no news"}
            with (
                patch(
                    "src.local_runner.update_analysis_sources_pipeline._find_repo_root",
                    return_value=root,
                ),
                patch(
                    "src.local_runner.update_analysis_sources_pipeline.run_news_update",
                    side_effect=(failed, failed),
                ),
                patch(
                    "src.local_runner.update_analysis_sources_pipeline.restart_gateway"
                ),
                patch(
                    "src.local_runner.update_analysis_sources_pipeline.run_analyst_update"
                ) as analyst,
            ):
                exit_code = main(
                    [
                        "--tickers",
                        "AAA",
                        "--progress-dir",
                        str(progress),
                        "--update-news",
                        "--sleep-seconds",
                        "0",
                        "--deferred-retries",
                        "0",
                    ]
                )

            marker = json.loads((progress / "AAA.json").read_text(encoding="utf-8"))
            self.assertEqual(exit_code, 1)
            self.assertEqual(marker["status"], "failed")
            self.assertIn("ibkr_news_update_failed", marker["error"])
            analyst.assert_not_called()

    def test_failed_news_is_retried_after_the_initial_queue(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            progress = root / "progress"
            failed = {"ticker": "AAA", "status": "failed", "error": "timeout"}
            succeeded = {"ticker": "AAA", "status": "ok"}
            with (
                patch(
                    "src.local_runner.update_analysis_sources_pipeline._find_repo_root",
                    return_value=root,
                ),
                patch(
                    "src.local_runner.update_analysis_sources_pipeline.run_news_update",
                    side_effect=(failed, failed, succeeded),
                ) as news,
                patch(
                    "src.local_runner.update_analysis_sources_pipeline.restart_gateway"
                ),
            ):
                exit_code = main(
                    [
                        "--tickers",
                        "AAA",
                        "--progress-dir",
                        str(progress),
                        "--update-news",
                        "--sleep-seconds",
                        "0",
                        "--deferred-retries",
                        "1",
                        "--deferred-retry-delay",
                        "0",
                    ]
                )

            marker = json.loads((progress / "AAA.json").read_text(encoding="utf-8"))
            self.assertEqual(exit_code, 0)
            self.assertEqual(marker["status"], "ok")
            self.assertEqual(marker["deferred_retry_round"], 1)
            self.assertEqual(news.call_count, 3)


if __name__ == "__main__":
    unittest.main()
