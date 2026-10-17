from __future__ import annotations

import json
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from stock_analysis.contracts.market import DailyBar, Quote, TickerMarketData
from stock_analysis.market_worker.metrics import (
    benchmark_session_return,
    calculate_benchmark_metrics,
    calculate_universe_metrics,
    drawdown_from_intraday_high,
    day_change,
    distance_from_6m_low,
    global_strength,
    relative_drawdown_6m,
    robust_atr_percent,
    session_return,
)


ROOT = Path(__file__).resolve().parents[1]


def bars_from_closes(closes: list[float], start: date = date(2026, 1, 1)) -> list[DailyBar]:
    return [
        DailyBar(start + timedelta(days=index), close + 1, close - 1, close)
        for index, close in enumerate(closes)
    ]


class MarketMetricsTest(unittest.TestCase):
    def test_intraday_high_drawdown_keeps_legacy_nasdaq_definition(self) -> None:
        bars = (
            DailyBar(date(2026, 9, 3), 105.0, 98.0, 100.0),
            DailyBar(date(2026, 9, 4), 110.0, 100.0, 108.0),
        )

        self.assertAlmostEqual(drawdown_from_intraday_high(104.0, bars), -6.0 / 110.0)

    @classmethod
    def setUpClass(cls) -> None:
        cls.market_fixture = json.loads(
            (ROOT / "tests/characterization/fixtures/market_metrics.json").read_text(
                encoding="utf-8"
            )
        )
        cls.sheet_fixture = json.loads(
            (ROOT / "tests/characterization/fixtures/sheet_metrics.json").read_text(
                encoding="utf-8"
            )
        )

    def test_day_change_characterization_cases(self) -> None:
        for case in self.market_fixture["day_change_cases"]:
            bars = [
                DailyBar(date.fromisoformat(day), close, close, close)
                for day, close in case["daily_closes"]
            ]
            actual = day_change(
                case["latest_price"], bars, date.fromisoformat(case["market_date"])
            )
            expected = case["expected_pct"]
            if expected is None:
                self.assertIsNone(actual, case["name"])
            else:
                self.assertAlmostEqual(actual * 100, expected, places=10, msg=case["name"])

    def test_return_characterization_cases(self) -> None:
        for name, sessions in (("return_5d", 5), ("return_20d", 20)):
            case = self.sheet_fixture["cases"][name]
            bars = bars_from_closes(case["closed_closes_oldest_to_newest"])
            market_date = bars[-1].session_date + timedelta(days=1)
            self.assertAlmostEqual(
                session_return(case["spot"], bars, sessions, market_date),
                case["expected"],
            )

    def test_atr_characterization_case(self) -> None:
        case = self.sheet_fixture["cases"]["volatility"]
        bars = [DailyBar(date(2026, 1, 1), 120, 120, 120)]
        for index, true_range in enumerate(case["true_ranges"], start=1):
            bars.append(
                DailyBar(
                    date(2026, 1, 1) + timedelta(days=index),
                    120 + true_range / 2,
                    120 - true_range / 2,
                    120,
                )
            )
        self.assertEqual(robust_atr_percent(bars), case["expected"])

    def test_strength_uses_one_global_universe(self) -> None:
        case = self.sheet_fixture["cases"]["strength"]
        rows = {
            row["ticker"]: (row["return_5d"], row["return_20d"], row["volatility"])
            for row in case["rows"]
        }
        actual = global_strength(rows)
        for row in case["rows"]:
            self.assertEqual(actual[row["ticker"]], row["expected"])

    def test_drawdown_characterization_cases(self) -> None:
        for case in self.market_fixture["drawdown_cases"]:
            bars = bars_from_closes(case["closes"])
            drawdown, percentile, samples = relative_drawdown_6m(
                case["latest_price"],
                bars,
                lookback=case["lookback"],
                history_sessions=case["history_sessions"],
            )
            expected = case["expected"]
            self.assertAlmostEqual(drawdown * 100, expected["pct_from_high"], msg=case["name"])
            if expected["percentile"] is None:
                self.assertIsNone(percentile, case["name"])
            else:
                self.assertAlmostEqual(percentile, round(expected["percentile"]), msg=case["name"])
            self.assertEqual(samples, expected["samples"], case["name"])

    def test_distance_from_six_month_low_uses_current_price(self) -> None:
        bars = bars_from_closes([120.0, 100.0, 105.0])
        self.assertAlmostEqual(distance_from_6m_low(100.5, bars), 0.005)

    def test_weekend_preserves_last_session_change(self) -> None:
        bars = tuple(bars_from_closes([100, 110], start=date(2026, 9, 3)))
        data = {
            "TEST": TickerMarketData(
                quote=Quote(
                    "TEST", 110, datetime(2026, 9, 5, tzinfo=timezone.utc), "fixture"
                ),
                daily_bars=bars,
            )
        }
        metric = calculate_universe_metrics(data, market_date=date(2026, 9, 5))[0]
        self.assertAlmostEqual(metric.day_change, 0.10)

    def test_market_holiday_preserves_last_session_change(self) -> None:
        bars = tuple(bars_from_closes([100, 110], start=date(2026, 9, 3)))
        data = {
            "TEST": TickerMarketData(
                quote=Quote(
                    "TEST", 110, datetime(2026, 9, 7, tzinfo=timezone.utc), "fixture"
                ),
                daily_bars=bars,
            )
        }
        metric = calculate_universe_metrics(data, market_date=date(2026, 9, 7))[0]
        self.assertAlmostEqual(metric.day_change, 0.10)

    def test_weekend_returns_include_friday_as_completed(self) -> None:
        bars = tuple(
            bars_from_closes([100, 101, 102, 103, 104, 110], start=date(2026, 8, 28))
        )
        data = {
            "TEST": TickerMarketData(
                quote=Quote(
                    "TEST", 110, datetime(2026, 9, 5, tzinfo=timezone.utc), "fixture"
                ),
                daily_bars=bars,
            )
        }
        metric = calculate_universe_metrics(data, market_date=date(2026, 9, 5))[0]
        self.assertAlmostEqual(metric.return_5d, 0.10)

    def test_benchmark_return_counts_twenty_sessions_including_current(self) -> None:
        bars = bars_from_closes([100.0 + index for index in range(21)])
        market_date = bars[-1].session_date + timedelta(days=1)
        self.assertEqual(
            benchmark_session_return(120.0, bars, 20, market_date),
            round(120.0 / 102.0 - 1.0, 4),
        )

    def test_benchmark_return_includes_latest_bar_on_weekend(self) -> None:
        bars = bars_from_closes(
            [100.0 + index for index in range(20)], start=date(2026, 8, 17)
        )
        market_date = date(2026, 9, 5)
        self.assertEqual(
            benchmark_session_return(119.0, bars, 20, market_date),
            round(119.0 / 100.0 - 1.0, 4),
        )

    def test_benchmark_return_includes_latest_bar_on_market_holiday(self) -> None:
        bars = bars_from_closes(
            [100.0 + index for index in range(20)], start=date(2026, 8, 17)
        )
        self.assertEqual(
            benchmark_session_return(119.0, bars, 20, date(2026, 9, 7)),
            round(119.0 / 100.0 - 1.0, 4),
        )

    def test_benchmark_metrics_use_the_same_dd6m_formula_as_tickers(self) -> None:
        observed_at = datetime(2026, 9, 5, tzinfo=timezone.utc)
        bars = tuple(
            bars_from_closes([100.0 + index % 30 for index in range(130)])
        )
        data = {
            ticker: TickerMarketData(
                quote=Quote(ticker, price, observed_at, "fixture"),
                daily_bars=bars,
            )
            for ticker, price in (("SOXX", 130.0), ("QTUP", 120.0))
        }
        metrics = calculate_benchmark_metrics(
            data,
            tickers=("SOXX", "QTUP"),
            market_date=bars[-1].session_date + timedelta(days=1),
        )

        self.assertEqual([item.ticker for item in metrics], ["SOXX", "QTUP"])
        self.assertEqual(metrics[0].drawdown, 0.0)
        self.assertAlmostEqual(metrics[1].drawdown, 120.0 / 129.0 - 1.0)
        self.assertIsNotNone(metrics[0].drawdown_percentile)
        self.assertGreater(metrics[0].drawdown_samples, 0)


if __name__ == "__main__":
    unittest.main()
