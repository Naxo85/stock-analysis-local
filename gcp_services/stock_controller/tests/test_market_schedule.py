from __future__ import annotations

import unittest
from datetime import date, datetime

from stock_analysis.market_worker.schedule import schedule_bucket
from stock_analysis.market_worker.session import (
    NEW_YORK,
    standard_us_market_holidays,
    us_market_session,
)


class MarketScheduleTest(unittest.TestCase):
    def test_interval_depends_on_new_york_session(self) -> None:
        cases = (
            (datetime(2026, 9, 8, 8, 0, tzinfo=NEW_YORK), "pre-market", 5),
            (datetime(2026, 9, 8, 10, 0, tzinfo=NEW_YORK), "regular", 1),
            (datetime(2026, 9, 8, 17, 0, tzinfo=NEW_YORK), "post-market", 5),
            (datetime(2026, 9, 8, 22, 0, tzinfo=NEW_YORK), "closed", 60),
            (datetime(2026, 9, 12, 10, 0, tzinfo=NEW_YORK), "closed", 60),
        )
        for now, expected_name, expected_interval in cases:
            session = us_market_session(now)
            self.assertEqual(session.name, expected_name)
            self.assertEqual(session.target_interval_minutes, expected_interval)

    def test_standard_market_holidays_are_closed(self) -> None:
        holidays = standard_us_market_holidays(2026)
        self.assertIn(date(2026, 1, 1), holidays)
        self.assertIn(date(2026, 4, 3), holidays)
        self.assertIn(date(2026, 11, 26), holidays)
        session = us_market_session(datetime(2026, 11, 26, 10, 0, tzinfo=NEW_YORK))
        self.assertEqual(session.name, "closed")
        self.assertEqual(session.target_interval_minutes, 60)

    def test_five_minute_bucket_is_stable_until_boundary(self) -> None:
        first = schedule_bucket(datetime(2026, 9, 8, 8, 2, tzinfo=NEW_YORK))
        second = schedule_bucket(datetime(2026, 9, 8, 8, 4, 59, tzinfo=NEW_YORK))
        third = schedule_bucket(datetime(2026, 9, 8, 8, 5, tzinfo=NEW_YORK))
        self.assertEqual(first.key, second.key)
        self.assertNotEqual(first.key, third.key)

    def test_regular_bucket_changes_every_minute(self) -> None:
        first = schedule_bucket(datetime(2026, 9, 8, 10, 0, tzinfo=NEW_YORK))
        second = schedule_bucket(datetime(2026, 9, 8, 10, 1, tzinfo=NEW_YORK))
        self.assertNotEqual(first.key, second.key)


if __name__ == "__main__":
    unittest.main()
