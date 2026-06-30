from __future__ import annotations

import unittest

from src.local_runner.ibkr_earnings_probe import (
    _parse_wsh_events,
    is_earnings_like_event,
)


class IbkrEarningsProbeTests(unittest.TestCase):
    def test_parse_wsh_events_accepts_list_payload(self):
        result = _parse_wsh_events('[{"eventName": "Earnings Date"}]')

        self.assertEqual(result, [{"eventName": "Earnings Date"}])

    def test_parse_wsh_events_accepts_events_key(self):
        result = _parse_wsh_events('{"events": [{"eventType": "Dividend"}]}')

        self.assertEqual(result, [{"eventType": "Dividend"}])

    def test_parse_wsh_events_treats_blank_as_no_events(self):
        self.assertEqual(_parse_wsh_events(""), [])

    def test_is_earnings_like_event_matches_common_names(self):
        self.assertTrue(
            is_earnings_like_event(
                {"eventName": "Q3 earnings release", "date": "2026-06-24"}
            )
        )
        self.assertTrue(is_earnings_like_event({"description": "Fiscal Q4 results"}))
        self.assertFalse(is_earnings_like_event({"eventName": "Dividend ex-date"}))


if __name__ == "__main__":
    unittest.main()
