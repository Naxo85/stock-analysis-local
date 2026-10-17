from __future__ import annotations

import tempfile
import threading
import unittest
from argparse import Namespace
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from src.local_runner.update_analyst_ratings_pipeline import (
    _iter_earnings_contexts,
    _write_progress,
)


class AnalystPipelineTests(unittest.TestCase):
    def test_earnings_prefetch_is_parallel_but_yields_ticker_order(self) -> None:
        fast_started = threading.Event()

        def fake_fetch(*, ticker, **unused):
            if ticker == "SLOW":
                self.assertTrue(fast_started.wait(timeout=2))
            else:
                fast_started.set()
            return {"source_status": "live", "ticker": ticker}

        args = Namespace(finnhub_max_parallel=2, finnhub_retries=0)
        with (
            tempfile.TemporaryDirectory() as temp_dir,
            patch(
                "src.local_runner.update_analyst_ratings_pipeline.get_local_env_value",
                return_value="key",
            ),
            patch(
                "src.local_runner.update_analyst_ratings_pipeline._fetch_earnings_context",
                side_effect=fake_fetch,
            ),
        ):
            contexts = _iter_earnings_contexts(
                repo_root=Path(temp_dir),
                tickers=["SLOW", "FAST"],
                args=args,
                now=datetime.now(timezone.utc),
            )
            yielded = [ticker for ticker, _ in contexts]

        self.assertEqual(yielded, ["SLOW", "FAST"])

    def test_progress_marker_is_complete_json(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "AAA.json"
            _write_progress(path, {"ticker": "AAA", "status": "ok"})
            self.assertEqual(
                path.read_text(encoding="utf-8"),
                '{\n  "ticker": "AAA",\n  "status": "ok"\n}\n',
            )
            self.assertFalse(path.with_suffix(".json.tmp").exists())


if __name__ == "__main__":
    unittest.main()
