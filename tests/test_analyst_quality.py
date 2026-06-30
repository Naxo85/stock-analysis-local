from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from src.local_runner.analyst_quality import (
    evaluate_analyst_consensus,
    load_analyst_quality_context,
)


NOW = datetime(2026, 6, 26, tzinfo=timezone.utc)


class AnalystQualityTests(unittest.TestCase):
    def test_scores_broad_recent_consensus_as_high_quality(self):
        result = evaluate_analyst_consensus(
            {
                "source": "test_provider",
                "as_of": "2026-06-20",
                "analyst_count": 12,
                "price_target": {
                    "target_low": 42,
                    "target_mean": 50,
                    "target_median": 49,
                    "target_high": 58,
                },
                "recommendations": {
                    "strong_buy": 3,
                    "buy": 6,
                    "hold": 3,
                    "sell": 0,
                    "strong_sell": 0,
                },
            },
            current_price=40,
            now=NOW,
        ).to_dict()

        self.assertEqual(result["status"], "usable")
        self.assertEqual(result["grade"], "high")
        self.assertGreaterEqual(result["score"], 80)
        self.assertEqual(result["price_target"]["upside_to_mean_pct"], 25.0)
        self.assertEqual(result["recommendations"]["buyish_pct"], 75.0)

    def test_marks_old_consensus_as_stale_even_with_good_coverage(self):
        result = evaluate_analyst_consensus(
            {
                "source": "test_provider",
                "as_of": "2025-12-01",
                "analyst_count": 15,
                "target_mean": 50,
                "target_low": 45,
                "target_high": 55,
                "buy": 10,
                "hold": 5,
            },
            current_price=40,
            now=NOW,
        ).to_dict()

        self.assertEqual(result["status"], "stale")
        self.assertEqual(result["grade"], "low")
        self.assertIn("stale_consensus", " ".join(result["warnings"]))

    def test_accepts_common_provider_aliases(self):
        result = evaluate_analyst_consensus(
            {
                "provider": "finnhub_like",
                "lastUpdated": "2026-06-24",
                "targetLow": 20,
                "targetMean": 28,
                "targetMedian": 27,
                "targetHigh": 34,
                "recommendations": [
                    {
                        "strongBuy": 2,
                        "buy": 4,
                        "hold": 3,
                        "sell": 1,
                        "strongSell": 0,
                    }
                ],
            },
            current_price=25,
            now=NOW,
        ).to_dict()

        self.assertEqual(result["analyst_count"], 10)
        self.assertEqual(result["price_target"]["target_mean"], 28.0)
        self.assertEqual(result["recommendations"]["strong_buy"], 2)

    def test_missing_data_is_unavailable(self):
        result = evaluate_analyst_consensus(
            None,
            current_price=40,
            now=NOW,
        ).to_dict()

        self.assertEqual(result["status"], "unavailable")
        self.assertEqual(result["score"], 0)
        self.assertIn("missing_consensus_data", result["warnings"])

    def test_loads_latest_local_consensus_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            consensus_dir = repo_root / "data" / "analyst_consensus" / "RKLB"
            consensus_dir.mkdir(parents=True)
            (consensus_dir / "latest.json").write_text(
                """
                {
                  "source": "test_provider",
                  "as_of": "2026-06-25",
                  "analyst_count": 5,
                  "target_mean": 35,
                  "target_low": 30,
                  "target_high": 40,
                  "buy": 3,
                  "hold": 2
                }
                """,
                encoding="utf-8",
            )

            result = load_analyst_quality_context(
                repo_root,
                "RKLB",
                current_price=28,
                now=NOW,
            )

        self.assertEqual(result["source"], "test_provider")
        self.assertIn(result["status"], {"usable", "usable_with_caution"})


if __name__ == "__main__":
    unittest.main()
