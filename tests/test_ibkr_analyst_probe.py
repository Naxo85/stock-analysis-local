from __future__ import annotations

import unittest
from dataclasses import dataclass
from dataclasses import replace
from datetime import datetime, timezone

from src.local_runner.ibkr_analyst_probe import (
    build_probe_payload,
    clean_ibkr_headline,
    serialize_news_headline,
)


@dataclass
class FakeContract:
    conId: int = 9939
    symbol: str = "MU"
    exchange: str = "SMART"
    currency: str = "USD"
    secType: str = "STK"


@dataclass
class FakeProvider:
    code: str
    name: str


@dataclass
class FakeHeadline:
    providerCode: str = "BRFUPDN"
    articleId: str = "BRFUPDN$abc"
    time: datetime = datetime(2026, 6, 26, 12, 30, tzinfo=timezone.utc)
    headline: str = "{A:800015:L:en}!Needham reiterated Micron (MU) coverage with Buy"


class IbkrAnalystProbeTests(unittest.TestCase):
    def test_clean_ibkr_headline_removes_metadata_prefix(self):
        self.assertEqual(
            clean_ibkr_headline("{A:800015:L:en}!Headline text"),
            "Headline text",
        )

    def test_serialize_news_headline_keeps_raw_and_clean(self):
        result = serialize_news_headline(
            symbol="MU",
            con_id=9939,
            item=FakeHeadline(),
        )

        self.assertEqual(result["providerCode"], "BRFUPDN")
        self.assertEqual(result["articleId"], "BRFUPDN$abc")
        self.assertIn("{A:800015:L:en}", result["headline_raw"])
        self.assertEqual(
            result["headline_clean"],
            "Needham reiterated Micron (MU) coverage with Buy",
        )
        self.assertEqual(result["analyst_action"]["parse_status"], "parsed")
        self.assertEqual(result["analyst_action"]["firm"], "Needham")
        self.assertEqual(result["analyst_action"]["rating"], "Buy")
        self.assertFalse(result["article"]["fetched"])

    def test_build_probe_payload_has_expected_shape(self):
        generated_at = datetime(2026, 6, 26, 13, 0, tzinfo=timezone.utc)
        start = datetime(2026, 6, 12, 13, 0, tzinfo=timezone.utc)
        result = build_probe_payload(
            symbol="MU",
            contract=FakeContract(),
            provider="BRFUPDN",
            providers=[
                FakeProvider("BRFUPDN", "Briefing.com Analyst Actions"),
                FakeProvider("DJ-N", "Dow Jones Global Equity Trader"),
            ],
            headlines=[FakeHeadline()],
            start=start,
            generated_at=generated_at,
            host="127.0.0.1",
            port=7497,
            window_basis="finnhub_previous_earnings",
            earnings_context={"previous_earnings_date": "2026-06-24"},
        )

        self.assertEqual(result["kind"], "analyst_actions_probe")
        self.assertEqual(result["contract"]["conId"], 9939)
        self.assertEqual(result["providerCode"], "BRFUPDN")
        self.assertEqual(result["headline_count"], 1)
        self.assertEqual(result["raw_headline_count"], 1)
        self.assertEqual(result["available_providers"][0]["code"], "BRFUPDN")
        self.assertEqual(result["window"]["start"], start.isoformat())
        self.assertEqual(result["window"]["basis"], "finnhub_previous_earnings")
        self.assertEqual(
            result["earnings_context"]["previous_earnings_date"],
            "2026-06-24",
        )

    def test_build_probe_payload_filters_headlines_outside_window(self):
        generated_at = datetime(2026, 6, 26, 13, 0, tzinfo=timezone.utc)
        start = datetime(2026, 6, 12, 13, 0, tzinfo=timezone.utc)
        old_headline = replace(
            FakeHeadline(),
            time=datetime(2026, 5, 1, 13, 0, tzinfo=timezone.utc),
        )

        result = build_probe_payload(
            symbol="MU",
            contract=FakeContract(),
            provider="BRFUPDN",
            providers=[],
            headlines=[FakeHeadline(), old_headline],
            start=start,
            generated_at=generated_at,
            host="127.0.0.1",
            port=7497,
        )

        self.assertEqual(result["raw_headline_count"], 2)
        self.assertEqual(result["headline_count"], 1)
        self.assertEqual(result["filtered_before_start_count"], 1)


if __name__ == "__main__":
    unittest.main()
