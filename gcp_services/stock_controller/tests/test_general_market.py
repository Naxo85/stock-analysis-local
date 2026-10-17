from __future__ import annotations

import json
import unittest
from datetime import date, datetime, timezone

from stock_analysis.contracts.market import BenchmarkMetrics
from stock_analysis.market_worker import general_market
from stock_analysis.market_worker.general_market import (
    adjusted_risk_score,
    analysis_batch_note,
    build_general_market_overview,
    fetch_general_market_inputs,
    vxn_regime,
)


class FakeBlob:
    def __init__(self, value: dict) -> None:
        self.value = value

    def download_as_bytes(self) -> bytes:
        return json.dumps(self.value).encode("utf-8")


class FakeBucket:
    def blob(self, name: str) -> FakeBlob:
        profile = "trading" if "trading" in name else "core"
        finished = {
            "trading": "2026-09-04T15:08:04+00:00",
            "core": "2026-09-03T13:45:49+00:00",
        }[profile]
        return FakeBlob(
            {
                "finished_at": finished,
                "model_usage": {
                    "base": {"Luna": ["AMD", "MU"]},
                    "reviews": {"Sol": ["AMD"]},
                    "published": ["MU"],
                    "reference_retained": [],
                    "reviewed_and_published": [{"ticker": "AMD", "model": "Sol"}],
                    "failed": [],
                },
            }
        )


class FakeStorageClient:
    def bucket(self, _name: str) -> FakeBucket:
        return FakeBucket()


def fake_http(url: str, **_kwargs) -> dict:
    if "fear-greed" in url:
        return {
            "score": 41.9,
            "source": "CNN Fear & Greed",
            "source_timestamp": "2026-09-05T00:59:00+00:00",
        }
    if "finance/chart" in url:
        return {
            "chart": {
                "result": [
                    {
                        "meta": {
                            "regularMarketPrice": 20.04,
                            "chartPreviousClose": 19.92,
                            "regularMarketTime": 1788571800,
                        }
                    }
                ]
            }
        }
    raise AssertionError(url)


class GeneralMarketTest(unittest.TestCase):
    def setUp(self) -> None:
        general_market._CACHE.clear()

    def tearDown(self) -> None:
        general_market._CACHE.clear()

    def test_vxn_regime_keeps_legacy_thresholds(self) -> None:
        self.assertEqual(vxn_regime(19.99), ("tranquilo", 4))
        self.assertEqual(vxn_regime(20.0), ("normal", 0))
        self.assertEqual(vxn_regime(25.0), ("tension", -8))
        self.assertEqual(vxn_regime(30.0), ("risk-off", -15))
        self.assertEqual(vxn_regime(35.0), ("shock", -25))

    def test_adjusted_risk_score_keeps_level_and_velocity_adjustments(self) -> None:
        self.assertEqual(adjusted_risk_score(41.9, 20.04, 0.006), (42, "Risk-off", "normal"))
        self.assertEqual(adjusted_risk_score(50.0, 36.0, 0.21), (7, "Strong Risk-off", "shock"))
        self.assertEqual(adjusted_risk_score(50.0, 19.0, -0.11), (59, "Risk-on", "tranquilo"))

    def test_inputs_and_qqq_build_a_traceable_overview(self) -> None:
        inputs = fetch_general_market_inputs(
            "fixture-bucket",
            status_prefix="fixture/status",
            http_json=fake_http,
            storage_client=FakeStorageClient(),
            use_cache=False,
        )
        qqq = BenchmarkMetrics(
            ticker="QQQ",
            day_change=-0.003,
            drawdown=-0.04,
            return_20d=-0.002,
            observed_at=datetime(2026, 9, 4, tzinfo=timezone.utc),
            source="tradier",
        )

        result = build_general_market_overview(qqq, inputs)

        self.assertEqual(result.risk_score, 42)
        self.assertEqual(result.vxn_label, "normal")
        self.assertEqual(result.vxn_source, "Yahoo Finance ^VXN")
        self.assertEqual(
            result.vxn_observed_at,
            datetime.fromtimestamp(1788571800, tz=timezone.utc),
        )
        self.assertEqual(result.trading_date, date(2026, 9, 4))
        self.assertEqual(result.core_date, date(2026, 9, 3))
        self.assertEqual(result.sentiment_source, "CNN")
        self.assertEqual(
            result.sentiment_observed_at,
            datetime(2026, 9, 5, 0, 59, tzinfo=timezone.utc),
        )
        self.assertIn("Ruta base\nLuna (2): AMD, MU", result.trading_note)
        self.assertIn("Revisiones superiores\nSol (1): AMD", result.core_note)
        self.assertEqual(result.qqq_drawdown_6m, -0.04)
        self.assertEqual(
            result.sources,
            (
                "CNN Fear & Greed proxy",
                "Yahoo Finance ^VXN",
                "gs://fixture-bucket/fixture/status",
                "Tradier QQQ",
            ),
        )
        self.assertEqual(result.failures, {})

    def test_cnn_relies_on_proxy_cache_without_adding_another_ttl(self) -> None:
        cnn_calls = 0
        vxn_calls = 0

        def changing_http(url: str, **_kwargs) -> dict:
            nonlocal cnn_calls, vxn_calls
            if "fear-greed" in url:
                cnn_calls += 1
                return {
                    "score": 40 + cnn_calls,
                    "source": "CNN Fear & Greed",
                    "source_timestamp": f"2026-09-08T07:{34 + cnn_calls}:00+00:00",
                }
            if "finance/chart" in url:
                vxn_calls += 1
                return fake_http(url)
            raise AssertionError(url)

        first = fetch_general_market_inputs(
            "fixture-bucket",
            http_json=changing_http,
            storage_client=FakeStorageClient(),
        )
        second = fetch_general_market_inputs(
            "fixture-bucket",
            http_json=changing_http,
            storage_client=FakeStorageClient(),
        )

        self.assertEqual((first.cnn_score, second.cnn_score), (41.0, 42.0))
        self.assertEqual(cnn_calls, 2)
        self.assertEqual(vxn_calls, 1)

    def test_analysis_batch_note_keeps_legacy_sections(self) -> None:
        note = analysis_batch_note(
            "Trading",
            {
                "base": {"Sol": ["APP"], "Luna": ["MU", "SNDK"]},
                "reviews": {},
                "published": ["MU"],
                "reviewed_and_published": [{"ticker": "APP", "model": "Sol"}],
                "reference_retained": [
                    {
                        "ticker": "SNDK",
                        "confidence": 64.4,
                        "reasons": ["sin cambio"],
                    }
                ],
                "failed": ["WDC"],
            },
        )

        self.assertIn("Ruta base\nLuna (2): MU, SNDK\nSol (1): APP", note)
        self.assertIn("Publicados sin revisión (1): MU", note)
        self.assertIn("- APP: Sol", note)
        self.assertIn("- SNDK · 64% · sin cambio", note)
        self.assertIn("Fallidos (1): WDC", note)


if __name__ == "__main__":
    unittest.main()
