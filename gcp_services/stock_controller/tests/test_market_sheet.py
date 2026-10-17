from __future__ import annotations

import unittest
from dataclasses import replace
from datetime import date, datetime, timezone

from stock_analysis.contracts.market import (
    BenchmarkMetrics,
    GeneralMarketOverview,
    MarketSnapshot,
    TickerMetrics,
)
from stock_analysis.controller.market_sheet import (
    benchmark_band_text,
    build_benchmark_value_requests,
    build_general_panel_requests,
    build_market_value_requests,
    general_panel_lines,
    metric_cells,
    risk_indicator_note,
    vxn_indicator_note,
)
from stock_analysis.controller.sheet_layout import load_market_sheet_layout
from stock_analysis.controller.sheet_tickers import configured_ticker_rows


def metric(ticker: str, price: float = 123.45) -> TickerMetrics:
    return TickerMetrics(
        ticker=ticker,
        price=price,
        day_change=0.012,
        strength=7.5,
        return_5d=0.03,
        return_20d=0.08,
        volatility=0.045,
        drawdown_6m=-0.22,
        distance_from_6m_low=0.10,
        drawdown_percentile=91,
        drawdown_samples=600,
        observed_at=datetime(2026, 9, 5, tzinfo=timezone.utc),
        source="fixture",
    )


def benchmark(ticker: str, percentile: int | None = 95) -> BenchmarkMetrics:
    return BenchmarkMetrics(
        ticker=ticker,
        day_change=0.0123,
        drawdown=-0.1304,
        return_20d=-0.0251,
        observed_at=datetime(2026, 9, 5, tzinfo=timezone.utc),
        source="fixture",
        drawdown_percentile=percentile,
        drawdown_samples=600,
    )


def overview() -> GeneralMarketOverview:
    return GeneralMarketOverview(
        risk_score=42,
        risk_label="Risk-off",
        vxn_value=20.04,
        vxn_change=0.006,
        vxn_label="normal",
        vxn_observed_at=datetime(2026, 9, 5, 1, 30, tzinfo=timezone.utc),
        vxn_source="Yahoo Finance ^VXN",
        qqq_day_change=-0.0034,
        qqq_drawdown_6m=-0.0404,
        qqq_return_20d=-0.0026,
        trading_date=date(2026, 9, 4),
        core_date=date(2026, 9, 3),
        sentiment_observed_at=datetime(2026, 9, 5, 0, 59, tzinfo=timezone.utc),
        sentiment_source="CNN",
        trading_note=(
            "Última actualización completa de Trading\n\n"
            "Ruta base\nLuna (2): AMD, MU"
        ),
        core_note="Última actualización completa de Core",
        observed_at=datetime(2026, 9, 6, tzinfo=timezone.utc),
        sources=("fixture",),
        failures={},
    )


class MarketSheetPublisherTest(unittest.TestCase):
    def test_cached_quote_note_shows_sample_age_and_source(self) -> None:
        layout = load_market_sheet_layout()
        cached = replace(metric("RKLB"), cached=True)
        cells = metric_cells(
            cached,
            base_background="#FFFFFF",
            format_rules=layout["format_rules"],
            as_of=datetime(2026, 9, 6, tzinfo=timezone.utc),
        )
        self.assertIn("antigüedad 1 día", cells[0]["note"])
        self.assertIn("Fuente original: fixture", cells[1]["note"])

    def test_near_six_month_low_is_light_red_below_historical_percentile_90(self) -> None:
        layout = load_market_sheet_layout()
        near_low = replace(
            metric("OKLO"),
            drawdown_6m=-0.5342,
            distance_from_6m_low=0.0068,
            drawdown_percentile=78,
        )
        cells = metric_cells(
            near_low,
            base_background="#FFFFFF",
            format_rules=layout["format_rules"],
        )
        self.assertEqual(
            cells[-1]["userEnteredFormat"]["backgroundColorStyle"]["rgbColor"],
            {"red": 244 / 255, "green": 204 / 255, "blue": 204 / 255},
        )

    def test_historical_extreme_stays_dark_red_when_also_near_six_month_low(self) -> None:
        layout = load_market_sheet_layout()
        extreme = replace(
            metric("RKLB"),
            distance_from_6m_low=0.0,
            drawdown_percentile=99,
        )
        cells = metric_cells(
            extreme,
            base_background="#FFFFFF",
            format_rules=layout["format_rules"],
        )
        self.assertEqual(
            cells[-1]["userEnteredFormat"]["backgroundColorStyle"]["rgbColor"],
            {"red": 224 / 255, "green": 102 / 255, "blue": 102 / 255},
        )

    def test_requests_write_only_seven_automatic_columns(self) -> None:
        layout = load_market_sheet_layout()
        tickers = tuple(
            ticker for block in layout["blocks"] for ticker in block["tickers"]
        )
        snapshot = MarketSnapshot(
            schema_version=1,
            generated_at=datetime(2026, 9, 5, tzinfo=timezone.utc),
            universe=tickers,
            metrics=tuple(metric(ticker) for ticker in tickers),
            failures={},
        )
        requests = build_market_value_requests(layout, snapshot)

        self.assertEqual(len(requests), len(layout["blocks"]))
        for request, block in zip(requests, layout["blocks"], strict=True):
            update = request["updateCells"]
            self.assertEqual(
                update["range"]["endColumnIndex"]
                - update["range"]["startColumnIndex"],
                7,
            )
            self.assertEqual(
                update["fields"],
                "userEnteredValue,note,userEnteredFormat.numberFormat,"
                "userEnteredFormat.backgroundColorStyle,"
                "userEnteredFormat.textFormat.foregroundColorStyle",
            )
            for offset, row in enumerate(update["rows"]):
                self.assertEqual(len(row["values"]), 7)
                self.assertEqual(row["values"][-1]["note"], "")
                self.assertEqual(
                    [
                        cell["userEnteredFormat"]["numberFormat"]["pattern"]
                        for cell in row["values"]
                    ],
                    ["0.00", "0.00%", "0.00", "0.00%", "0.00%", "0.00%", "0.00%"],
                )
                self.assertTrue(
                    all(
                        "backgroundColorStyle" in cell["userEnteredFormat"]
                        for cell in row["values"]
                    )
                )
                expected_background = block["palette"]["body"].removeprefix("#")
                expected_rgb = {
                    "red": int(expected_background[0:2], 16) / 255,
                    "green": int(expected_background[2:4], 16) / 255,
                    "blue": int(expected_background[4:6], 16) / 255,
                }
                self.assertEqual(
                    row["values"][5]["userEnteredFormat"]
                    ["backgroundColorStyle"]["rgbColor"],
                    expected_rgb,
                )

    def test_partial_block_is_not_shifted_or_published(self) -> None:
        layout = load_market_sheet_layout()
        snapshot = MarketSnapshot(
            schema_version=1,
            generated_at=datetime(2026, 9, 5, tzinfo=timezone.utc),
            universe=("AMD",),
            metrics=(metric("AMD"),),
            failures={"MRVL": "fixture failure"},
        )
        self.assertEqual(build_market_value_requests(layout, snapshot), [])

    def test_sorted_table_writes_metrics_in_live_ticker_order(self) -> None:
        layout = load_market_sheet_layout()
        tickers = tuple(
            ticker for block in layout["blocks"] for ticker in block["tickers"]
        )
        prices = {ticker: float(index) for index, ticker in enumerate(tickers, start=1)}
        snapshot = MarketSnapshot(
            schema_version=1,
            generated_at=datetime(2026, 9, 5, tzinfo=timezone.utc),
            universe=tickers,
            metrics=tuple(metric(ticker, prices[ticker]) for ticker in tickers),
            failures={},
        )
        rows = configured_ticker_rows(layout)
        rows["AMD"], rows["MRVL"] = rows["MRVL"], rows["AMD"]

        requests = build_market_value_requests(layout, snapshot, ticker_rows=rows)

        chips = next(
            request["updateCells"]
            for request in requests
            if request["updateCells"]["range"]["startColumnIndex"] == 11
            and len(request["updateCells"]["rows"])
            == len(layout["blocks"][0]["tickers"])
        )
        written_prices = [
            row["values"][0]["userEnteredValue"]["numberValue"]
            for row in chips["rows"]
        ]
        self.assertEqual(written_prices[0:2], [prices["MRVL"], prices["AMD"]])

    def test_benchmark_band_keeps_the_agreed_compact_text(self) -> None:
        self.assertEqual(
            benchmark_band_text(benchmark("SOXX")),
            "SOXX | Día 1,2% | DD6M -13,0% | 20d -2,5%",
        )

    def test_benchmark_requests_write_the_group_summary_metrics(self) -> None:
        layout = load_market_sheet_layout()
        snapshot = MarketSnapshot(
            schema_version=2,
            generated_at=datetime(2026, 9, 5, tzinfo=timezone.utc),
            universe=(),
            metrics=(),
            failures={},
            benchmarks=tuple(
                benchmark(group["benchmark"])
                for group in layout["groups"]
            ),
        )

        requests = build_benchmark_value_requests(layout, snapshot)

        self.assertEqual(len(requests), 1)
        update = requests[0]["updateCells"]
        self.assertEqual(update["range"]["startRowIndex"], 13)
        self.assertEqual(update["range"]["endRowIndex"], 27)
        self.assertEqual(update["range"]["startColumnIndex"], 3)
        self.assertEqual(update["range"]["endColumnIndex"], 6)
        self.assertEqual(len(update["rows"]), 14)
        self.assertEqual(len(update["rows"][0]["values"]), 3)
        self.assertEqual(
            update["rows"][0]["values"][2]["userEnteredFormat"][
                "backgroundColorStyle"
            ]["rgbColor"],
            {"red": 224 / 255, "green": 102 / 255, "blue": 102 / 255},
        )

    def test_general_panel_has_one_value_per_agreed_line(self) -> None:
        self.assertEqual(
            general_panel_lines(overview()),
            [
                "🟠 Risk-off 42/100",
                "VXN: normal",
                "",
                "QQQ Día: -0,3%",
                "QQQ 20d: -0,3%",
                "Nasdaq: -4,0% vs máx. 6m",
                "",
                "Mercado: 04/09/2026",
                "",
            ],
        )

    def test_market_refresh_writes_only_a2_a8(self) -> None:
        layout = load_market_sheet_layout()
        snapshot = MarketSnapshot(
            schema_version=3,
            generated_at=datetime(2026, 9, 6, tzinfo=timezone.utc),
            universe=(),
            metrics=(),
            failures={},
            general=overview(),
        )

        requests = build_general_panel_requests(layout, snapshot)

        self.assertEqual(len(requests), 1)
        update = requests[0]["updateCells"]
        self.assertEqual(
            update["range"],
            {
                "sheetId": layout["sheet"]["sheet_id"],
                "startRowIndex": 1,
                "endRowIndex": 8,
                "startColumnIndex": 0,
                "endColumnIndex": 1,
            },
        )
        self.assertEqual(len(update["rows"]), 7)
        self.assertIn(
            "Leyenda del indicador:", update["rows"][0]["values"][0]["note"]
        )
        self.assertIn(
            "Leyenda del VXN:", update["rows"][1]["values"][0]["note"]
        )

        self.assertEqual(
            update["fields"].split(",")[0:2], ["userEnteredValue", "note"]
        )
        bold = [
            row["values"][0]["userEnteredFormat"]["textFormat"]["bold"]
            for row in update["rows"]
        ]
        self.assertEqual(
            bold, [True, True, False, False, False, False, False]
        )


    def test_risk_note_keeps_legacy_legend_and_freshness(self) -> None:
        note = risk_indicator_note(overview())

        self.assertIn("Último dato válido: 05/09/2026 02:59", note)
        self.assertIn("Fuente del sentimiento: CNN", note)
        self.assertIn("🟠 25-44: Risk-off", note)
        self.assertNotIn("Leyenda del VXN", note)

    def test_vxn_note_has_its_own_source_freshness_and_legend(self) -> None:
        note = vxn_indicator_note(overview())

        self.assertIn("Último dato válido: 05/09/2026 03:30", note)
        self.assertIn("Fuente: Yahoo Finance ^VXN", note)
        self.assertIn("VXN: 20,04 (+0,6% diario)", note)
        self.assertIn("Leyenda del VXN:", note)
        self.assertNotIn("76-100", note)


if __name__ == "__main__":
    unittest.main()
