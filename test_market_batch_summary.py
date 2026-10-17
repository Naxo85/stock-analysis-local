from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from src.local_runner.run_batch import (
    _generation_provider_summary,
    _generation_retry_summary,
)


class MarketBatchSummaryTests(unittest.TestCase):
    def test_actual_providers_and_retries_are_summarized(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            metadata = {
                "AAA": {
                    "provider_requested": "chatgpt-browser",
                    "provider_used": "chatgpt-browser",
                    "attempts": [{}, {}],
                },
                "BBB": {
                    "provider_requested": "chatgpt-browser",
                    "provider_used": "codex",
                    "web_attempt_count": 3,
                    "web_retry_count": 2,
                },
            }
            for ticker, payload in metadata.items():
                output = root / "output" / ticker
                output.mkdir(parents=True)
                (output / "generation_metadata.json").write_text(
                    json.dumps(payload), encoding="utf-8"
                )
            results = [
                {
                    "ticker": "AAA",
                    "status": "ok",
                    "attempt": 1,
                    "pipeline_stages": {"analyze": {"status": "ok"}},
                },
                {
                    "ticker": "BBB",
                    "status": "ok",
                    "attempt": 2,
                    "pipeline_stages": {"analyze": {"status": "ok"}},
                },
                {
                    "ticker": "CCC",
                    "status": "failed",
                    "attempt": 1,
                    "pipeline_stages": {"prepare": {"status": "failed"}},
                },
            ]

            providers = _generation_provider_summary(root, results)
            retries = _generation_retry_summary(root, results)

        self.assertEqual(providers["chatgpt-browser"]["tickers"], ["AAA"])
        self.assertEqual(providers["codex"]["tickers"], ["BBB"])
        self.assertEqual(retries, {"batch": 1, "chatgpt_web": 3, "total": 4})


if __name__ == "__main__":
    unittest.main()
