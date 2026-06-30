from __future__ import annotations

import unittest
from datetime import date, datetime, timezone

from src.local_runner.finnhub_earnings import (
    build_earnings_payload,
    extract_earnings_events,
    normalize_earnings_date,
)


class FinnhubEarningsTests(unittest.TestCase):
    def test_extract_earnings_events_accepts_finnhub_shape(self):
        result = extract_earnings_events(
            {
                "earningsCalendar": [
                    {"date": "2026-03-01"},
                    "bad",
                    {"reportDate": "2026-06-01"},
                ]
            }
        )

        self.assertEqual(result, [{"date": "2026-03-01"}, {"reportDate": "2026-06-01"}])

    def test_normalize_earnings_date_accepts_known_fields(self):
        self.assertEqual(normalize_earnings_date({"date": "2026-06-25"}), "2026-06-25")
        self.assertEqual(
            normalize_earnings_date({"actualReleaseDate": "2026-06-25T20:00:00Z"}),
            "2026-06-25",
        )
        self.assertIsNone(normalize_earnings_date({"date": "not-a-date"}))

    def test_build_earnings_payload_splits_past_and_future_dates(self):
        result = build_earnings_payload(
            symbol="MU",
            events=[
                {"date": "2026-01-10"},
                {"reportDate": "2026-06-25"},
                {"date": "2026-09-20"},
            ],
            start=date(2026, 1, 1),
            end=date(2026, 12, 31),
            today=date(2026, 6, 26),
            generated_at=datetime(2026, 6, 26, tzinfo=timezone.utc),
        )

        self.assertEqual(result["past_earnings_dates"], ["2026-01-10", "2026-06-25"])
        self.assertEqual(result["future_earnings_dates"], ["2026-09-20"])
        self.assertEqual(result["previous_earnings_date"], "2026-06-25")
        self.assertEqual(result["next_earnings_date"], "2026-09-20")


if __name__ == "__main__":
    unittest.main()
