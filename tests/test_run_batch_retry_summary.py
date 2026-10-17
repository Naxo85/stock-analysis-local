from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from src.local_runner.run_batch import (
    _generation_provider_summary,
    _generation_retry_summary,
)


class GenerationRetrySummaryTests(unittest.TestCase):
    def test_counts_web_retries_from_every_pipeline_attempt(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            state_path = root / "pipeline_state.json"
            state_path.write_text(
                json.dumps(
                    {
                        "tickers": {
                            "AMD": {
                                "attempts": {
                                    "1": {
                                        "stages": {
                                            "analyze": {"web_retry_count": 2}
                                        }
                                    },
                                    "2": {
                                        "stages": {
                                            "analyze": {"web_retry_count": 1}
                                        }
                                    },
                                }
                            },
                            "NVDA": {
                                "attempts": {
                                    "1": {
                                        "stages": {
                                            "analyze": {"web_retry_count": 1}
                                        }
                                    }
                                }
                            },
                        }
                    }
                ),
                encoding="utf-8",
            )

            summary = _generation_retry_summary(
                root,
                [{"ticker": "AMD", "attempt": 2}],
                pipeline_state_path=state_path,
            )

        self.assertEqual(
            summary,
            {"batch": 1, "chatgpt_web": 4, "total": 5},
        )

    def test_provider_summary_excludes_failed_tickers_with_stale_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            providers = (
                ("WEB", "chatgpt-browser"),
                ("CODEX", "codex"),
                ("FAILED", "chatgpt-browser"),
            )
            for ticker, provider in providers:
                output = root / "output" / ticker
                output.mkdir(parents=True)
                (output / "generation_metadata.json").write_text(
                    json.dumps({"provider_used": provider}),
                    encoding="utf-8",
                )

            summary = _generation_provider_summary(
                root,
                [
                    {"ticker": "WEB", "status": "ok"},
                    {"ticker": "CODEX", "status": "ok"},
                    {"ticker": "FAILED", "status": "failed"},
                ],
            )

        self.assertEqual(
            summary,
            {
                "chatgpt-browser": {"count": 1, "tickers": ["WEB"]},
                "codex": {"count": 1, "tickers": ["CODEX"]},
            },
        )


if __name__ == "__main__":
    unittest.main()
