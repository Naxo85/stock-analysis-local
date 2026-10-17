from __future__ import annotations

import argparse
import json
import tempfile
import threading
import time
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

from src.local_runner.update_analyst_ratings_batch import (
    _prefetch_earnings_contexts,
)


class AnalystRatingsBatchEarningsTests(unittest.TestCase):
    def test_prefetches_live_earnings_with_bounded_parallelism(self) -> None:
        active = 0
        peak = 0
        lock = threading.Lock()

        def fake_fetch(**_kwargs):
            nonlocal active, peak
            with lock:
                active += 1
                peak = max(peak, active)
            time.sleep(0.02)
            with lock:
                active -= 1
            return [{"date": "2026-08-01"}, {"date": "2026-11-01"}]

        args = argparse.Namespace(finnhub_max_parallel=3, finnhub_retries=0)
        with tempfile.TemporaryDirectory() as tmp, mock.patch(
            "src.local_runner.update_analyst_ratings_batch.get_local_env_value",
            return_value="key",
        ), mock.patch(
            "src.local_runner.update_analyst_ratings_batch.fetch_earnings_calendar",
            side_effect=fake_fetch,
        ):
            contexts, summary = _prefetch_earnings_contexts(
                repo_root=Path(tmp),
                tickers=["AAA", "BBB", "CCC", "DDD"],
                args=args,
                now=datetime(2026, 9, 1, tzinfo=timezone.utc),
            )

        self.assertGreaterEqual(peak, 2)
        self.assertLessEqual(peak, 3)
        self.assertEqual(summary["counts"], {"live": 4})
        self.assertTrue(all(item["source_status"] == "live" for item in contexts.values()))

    def test_uses_explicit_cached_earnings_only_after_live_failure(self) -> None:
        args = argparse.Namespace(finnhub_max_parallel=2, finnhub_retries=0)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state_path = root / "data" / "analyst_ratings" / "AAA" / "current.json"
            state_path.parent.mkdir(parents=True)
            state_path.write_text(
                json.dumps(
                    {
                        "as_of": "2026-08-20T12:00:00+00:00",
                        "earnings": {
                            "previous_earnings_date": "2026-08-01",
                            "next_earnings_date": "2026-11-01",
                        },
                    }
                ),
                encoding="utf-8",
            )
            with mock.patch(
                "src.local_runner.update_analyst_ratings_batch.get_local_env_value",
                return_value="key",
            ), mock.patch(
                "src.local_runner.update_analyst_ratings_batch.fetch_earnings_calendar",
                side_effect=TimeoutError("provider timeout"),
            ):
                contexts, summary = _prefetch_earnings_contexts(
                    repo_root=root,
                    tickers=["AAA"],
                    args=args,
                    now=datetime(2026, 9, 1, tzinfo=timezone.utc),
                )

        context = contexts["AAA"]
        self.assertEqual(context["source_status"], "cached_fallback")
        self.assertEqual(context["next_earnings_date"], "2026-11-01")
        self.assertEqual(context["age_days"], 11)
        self.assertIn("TimeoutError", context["live_error"])
        self.assertEqual(summary["counts"], {"cached_fallback": 1})


if __name__ == "__main__":
    unittest.main()
