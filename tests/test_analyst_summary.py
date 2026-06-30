from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from src.local_runner.analyst_summary import (
    compact_analyst_summary,
    format_analyst_summary_for_sheet,
    load_compact_analyst_summary,
)


CURRENT = {
    "source": "IBKR_ANALYST_RATINGS",
    "ticker": "MU",
    "as_of": "2026-06-26T22:00:00+00:00",
    "earnings": {
        "previous_earnings_date": "2026-06-24",
        "next_earnings_date": "2026-09-21",
    },
    "summary_active": {
        "basis": "post_earnings_only",
        "quality": "high",
        "active_firm_count": 18,
        "stale_or_excluded_count": 19,
        "rating_counts": {"buy": 17, "hold": 1, "sell": 0, "unknown": 0},
        "target_count": 18,
        "target_low": 1100,
        "target_high": 2000,
        "target_mean": 1552.78,
        "target_median": 1512.5,
    },
}


class AnalystSummaryTests(unittest.TestCase):
    def test_compact_summary_keeps_sheet_fields(self):
        result = compact_analyst_summary(CURRENT)

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["basis"], "post_earnings_only")
        self.assertEqual(result["quality"], "high")
        self.assertEqual(result["target_median"], 1512.5)
        self.assertEqual(result["rating_counts"]["buy"], 17)

    def test_format_for_sheet(self):
        result = format_analyst_summary_for_sheet(compact_analyst_summary(CURRENT))

        self.assertEqual(result, "1512.5 | 17-1-0")

    def test_load_missing_summary_is_unavailable(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = load_compact_analyst_summary(Path(tmp), "MU")

        self.assertEqual(result["status"], "unavailable")


if __name__ == "__main__":
    unittest.main()
