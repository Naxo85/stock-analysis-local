from __future__ import annotations

import tempfile
import unittest
from datetime import date, datetime, timezone
from pathlib import Path

from stock_analysis.market_worker.providers import TradierMarketDataProvider


class FakeTradier:
    def __init__(self) -> None:
        self.quote_calls = 0
        self.history_calls = 0

    def __call__(self, url: str, **kwargs):
        if url.endswith("/quotes"):
            self.quote_calls += 1
            symbols = kwargs["params"]["symbols"].split(",")
            return {
                "quotes": {
                    "quote": [
                        {"symbol": symbol, "last": 100 + index}
                        for index, symbol in enumerate(symbols)
                    ]
                }
            }
        if url.endswith("/history"):
            self.history_calls += 1
            return {
                "history": {
                    "day": [
                        {
                            "date": f"2026-08-{day:02d}",
                            "high": 101 + day,
                            "low": 99 + day,
                            "close": 100 + day,
                            "volume": 1_000_000,
                        }
                        for day in range(1, 22)
                    ]
                }
            }
        raise AssertionError(url)


class TradierMarketDataProviderTest(unittest.TestCase):
    def test_missing_extended_quote_keeps_last_valid_sample_across_instances(self) -> None:
        fake = FakeTradier()
        observed = datetime(2026, 9, 8, 8, 46, tzinfo=timezone.utc)
        responses = [
            {"quotes": {"quote": {"symbol": "AAA", "bid": 120.0,
                                    "ask": 122.0,
                                    "bid_date": int(observed.timestamp() * 1000),
                                    "ask_date": int(observed.timestamp() * 1000)}}},
            {"quotes": {"quote": {"symbol": "AAA", "bid": 0,
                                    "ask": 0, "last": 0, "close": 121}}},
            {"quotes": {"quote": {"symbol": "AAA", "last": 0}}},
            {"quotes": {"quote": []}},
        ]

        def request(url: str, **kwargs):
            if url.endswith("/quotes"):
                return responses.pop(0)
            return fake(url, **kwargs)

        with tempfile.TemporaryDirectory() as directory:
            args = dict(cache_dir=Path(directory), http_json=request,
                        now=lambda: datetime(2026, 9, 8, 8, 50, tzinfo=timezone.utc))
            first, failures = TradierMarketDataProvider("token", **args).fetch_universe(
                ["AAA"], market_date=date(2026, 9, 8), prefer_extended=True
            )
            second, later_failures = TradierMarketDataProvider("token", **args).fetch_universe(
                ["AAA"], market_date=date(2026, 9, 8), prefer_extended=True
            )
            postmarket_args = dict(args)
            postmarket_args["now"] = lambda: datetime(2026, 9, 8, 21, tzinfo=timezone.utc)
            postmarket, postmarket_failures = TradierMarketDataProvider(
                "token", **postmarket_args
            ).fetch_universe(["AAA"], market_date=date(2026, 9, 8), prefer_extended=True)
            weekend, weekend_failures = TradierMarketDataProvider(
                "token", **postmarket_args
            ).fetch_universe(["AAA"], market_date=date(2026, 9, 12), prefer_extended=True)

        self.assertEqual(failures, {})
        self.assertEqual(later_failures, {})
        self.assertEqual(first["AAA"].quote.day_change, 0.0)
        self.assertEqual(second["AAA"].quote.price, 121.0)
        self.assertEqual(second["AAA"].quote.day_change, 0.0)
        self.assertEqual(second["AAA"].quote.observed_at, observed)
        self.assertEqual(second["AAA"].quote.source, "tradier_extended_mid")
        self.assertTrue(second["AAA"].quote.cached)
        self.assertEqual(postmarket_failures, {})
        self.assertEqual(weekend_failures, {})
        self.assertEqual(postmarket["AAA"].quote.day_change, 0.0)
        self.assertEqual(weekend["AAA"].quote.day_change, 0.0)
        self.assertEqual(weekend["AAA"].quote.observed_at, observed)

    def test_missing_quote_without_valid_sample_is_reported(self) -> None:
        fake = FakeTradier()

        def request(url: str, **kwargs):
            if url.endswith("/quotes"):
                return {"quotes": {"quote": {"symbol": "AAA", "bid": 0,
                                              "ask": 0, "last": 0, "close": 121}}}
            return fake(url, **kwargs)

        with tempfile.TemporaryDirectory() as directory:
            provider = TradierMarketDataProvider(
                "token", cache_dir=Path(directory), http_json=request
            )
            data, failures = provider.fetch_universe(
                ["AAA"], market_date=date(2026, 9, 8), prefer_extended=True
            )
        self.assertEqual(data, {})
        self.assertIn("AAA", failures)

    def test_quotes_are_batched_and_history_is_cached_per_day(self) -> None:
        fake = FakeTradier()
        with tempfile.TemporaryDirectory() as directory:
            provider = TradierMarketDataProvider(
                "fixture-token",
                cache_dir=Path(directory),
                http_json=fake,
                history_workers=2,
            )
            first, failures = provider.fetch_universe(
                ["AAA", "BBB"], market_date=date(2026, 9, 4)
            )
            second, second_failures = provider.fetch_universe(
                ["AAA", "BBB"], market_date=date(2026, 9, 4)
            )

        self.assertEqual(set(first), {"AAA", "BBB"})
        self.assertEqual(set(second), {"AAA", "BBB"})
        self.assertEqual(failures, {})
        self.assertEqual(second_failures, {})
        self.assertEqual(fake.quote_calls, 2)
        self.assertEqual(fake.history_calls, 2)

    def test_extended_session_uses_live_bid_ask_midpoint(self) -> None:
        fake = FakeTradier()
        original = fake.__call__

        def extended_quote(url: str, **kwargs):
            if url.endswith("/quotes"):
                fake.quote_calls += 1
                return {
                    "quotes": {
                        "quote": {
                            "symbol": "AAA",
                            "last": 100.0,
                            "bid": 104.0,
                            "ask": 106.0,
                            "bid_date": 1788857100000,
                            "ask_date": 1788857160000,
                        }
                    }
                }
            return original(url, **kwargs)

        with tempfile.TemporaryDirectory() as directory:
            provider = TradierMarketDataProvider(
                "fixture-token",
                cache_dir=Path(directory),
                http_json=extended_quote,
                history_workers=1,
                now=lambda: datetime(2026, 9, 8, 8, 50, tzinfo=timezone.utc),
            )
            data, failures = provider.fetch_universe(
                ["AAA"],
                market_date=date(2026, 9, 8),
                prefer_extended=True,
            )

        self.assertEqual(failures, {})
        self.assertEqual(data["AAA"].quote.price, 105.0)
        self.assertEqual(data["AAA"].quote.source, "tradier_extended_mid")
        self.assertEqual(
            data["AAA"].quote.observed_at.isoformat(),
            "2026-09-08T08:46:00+00:00",
        )

    def test_extended_session_rejects_a_wide_or_stale_market(self) -> None:
        fetched_at = datetime(2026, 9, 8, 9, 30, tzinfo=timezone.utc)
        provider = TradierMarketDataProvider(
            "fixture-token",
            http_json=lambda *_args, **_kwargs: {
                "quotes": {
                    "quote": {
                        "symbol": "QTUP",
                        "last": 16.08,
                        "bid": 15.28,
                        "ask": 22.48,
                        "bid_date": 1788854400000,
                        "ask_date": 1788854410000,
                        "trade_date": 1788566406211,
                    }
                }
            },
            now=lambda: fetched_at,
        )

        quote = provider._fetch_quotes(("QTUP",), prefer_extended=True)["QTUP"]

        self.assertEqual(quote.price, 16.08)
        self.assertEqual(quote.source, "tradier")
        self.assertNotEqual(quote.observed_at, fetched_at)

    def test_regular_session_keeps_last_trade(self) -> None:
        provider = TradierMarketDataProvider(
            "fixture-token",
            http_json=lambda *_args, **_kwargs: {
                "quotes": {
                    "quote": {
                        "symbol": "AAA",
                        "last": 100.0,
                        "bid": 104.0,
                        "ask": 106.0,
                    }
                }
            },
        )

        quote = provider._fetch_quotes(("AAA",))["AAA"]

        self.assertEqual(quote.price, 100.0)
        self.assertEqual(quote.source, "tradier")


if __name__ == "__main__":
    unittest.main()
