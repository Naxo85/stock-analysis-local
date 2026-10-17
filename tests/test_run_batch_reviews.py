from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.local_runner.analysis_policy import RouteDecision
from src.local_runner.run_batch import (
    BatchConfig,
    _batch_model_usage,
    _is_transient_review_failure,
    _review_worker_count,
    _run_review_with_retries,
)


def _config(root: Path) -> BatchConfig:
    route = RouteDecision(
        ticker="TEST",
        action="run",
        analysis_kind="review",
        tier="priority",
        model="gpt-5.6-terra",
        reasoning_effort="medium",
        reviewer_model="gpt-5.6-sol",
        reason="test",
        owned=False,
    )
    return BatchConfig(
        repo_root=root,
        tickers=("TEST",),
        source="test",
        max_parallel=6,
        retry_failed=1,
        upload_real=True,
        log_dir=root / "logs",
        update_analysts=False,
        update_ibkr_news=False,
        analysis_profile="trading",
        routes=(route,),
        model=None,
        reasoning_effort="medium",
    )


class ReviewReliabilityTests(unittest.TestCase):
    def test_model_usage_includes_publishing_outcomes(self) -> None:
        usage = _batch_model_usage(
            [
                {
                    "ticker": "AAA",
                    "status": "ok",
                    "route": {"model": "gpt-5.6-terra"},
                },
                {
                    "ticker": "BBB",
                    "status": "ok",
                    "route": {"model": "gpt-5.6-terra"},
                    "analysis_workflow": {
                        "status": "reference_retained_low_confidence",
                        "effective_confidence": 55,
                        "material_change_reasons": ["thesis_narrative"],
                        "reference_generated_at": "2026-08-27T07:00:00+00:00",
                    },
                },
                {
                    "ticker": "CCC",
                    "status": "ok",
                    "route": {"model": "gpt-5.6-terra"},
                    "review": {"status": "ok", "model": "gpt-5.6-sol"},
                },
            ]
        )

        self.assertEqual(usage["published"], ["AAA"])
        self.assertEqual(usage["reference_retained"][0]["ticker"], "BBB")
        self.assertEqual(
            usage["reviewed_and_published"],
            [{"ticker": "CCC", "model": "Sol"}],
        )

    def test_review_parallelism_is_capped_at_two(self) -> None:
        self.assertEqual(_review_worker_count(6, 5), 2)
        self.assertEqual(_review_worker_count(1, 5), 1)
        self.assertEqual(_review_worker_count(6, 1), 1)

    def test_recognizes_transient_endpoint_failures(self) -> None:
        self.assertTrue(
            _is_transient_review_failure(
                {
                    "status": "failed",
                    "error_message": "HTTP 502: 503 Server Error: Service Unavailable",
                }
            )
        )
        self.assertFalse(
            _is_transient_review_failure(
                {"status": "failed", "error_message": "validation_error"}
            )
        )

    def test_retries_transient_review_then_returns_success(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config = _config(Path(temp_dir))
            route = config.routes[0]
            failed = {
                "ticker": "TEST",
                "status": "failed",
                "error_message": "HTTP 503 Service Unavailable",
            }
            succeeded = {"ticker": "TEST", "status": "ok"}
            with (
                patch(
                    "src.local_runner.run_batch._run_one_review",
                    side_effect=(failed, succeeded),
                ) as run_review,
                patch("src.local_runner.run_batch.time.sleep") as sleep,
            ):
                result = _run_review_with_retries(config, "TEST", route)

            self.assertEqual(result["status"], "ok")
            self.assertEqual(result["attempt"], 2)
            self.assertEqual(run_review.call_count, 2)
            sleep.assert_called_once_with(5.0)

    def test_does_not_retry_non_transient_review_failure(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config = _config(Path(temp_dir))
            route = config.routes[0]
            failed = {
                "ticker": "TEST",
                "status": "failed",
                "error_message": "report validation failed",
            }
            with patch(
                "src.local_runner.run_batch._run_one_review",
                return_value=failed,
            ) as run_review:
                result = _run_review_with_retries(config, "TEST", route)

            self.assertEqual(result["status"], "failed")
            self.assertEqual(result["attempt"], 1)
            run_review.assert_called_once()


if __name__ == "__main__":
    unittest.main()
