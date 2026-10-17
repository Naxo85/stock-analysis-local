from __future__ import annotations

import unittest
from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timezone

from stock_analysis.contracts.analysis import AnalysisSheetRecord, PriceRange
from stock_analysis.controller.analysis_sheet import (
    analysis_read_ranges,
    build_analysis_value_requests,
    build_live_proximity_background_requests,
    build_strength_border_requests,
    build_strength_border_requests_for_values,
    resolve_ticker_rows_and_prices,
    resolve_visible_scores,
)
from stock_analysis.controller.sheet_tickers import TickerRows


LAYOUT = {
    "sheet": {"title": "Mercado", "sheet_id": 123},
    "table_template": {
        "ticker_column_offset": 1,
        "analysis_start_column_offset": 9,
    },
    "format_rules": {
        "entry_proximity": [
            {"state": "more_than_1_5_pct_below", "background": "#F4CCCC"},
            {"state": "inside_range", "background": "#00FF00"},
            {"state": "up_to_1_5_pct_below", "background": "#D9EAD3"},
        ],
        "resistance_proximity": [
            {"state": "inside_or_up_to_0_5_pct_below", "background": "#00B0F0"},
            {"state": "from_0_5_to_1_5_pct_below", "background": "#CFE2F3"},
        ],
    },
    "blocks": [
        {
            "table_name": "Demo",
            "start_column": "D",
            "end_column": "P",
            "header_row": 3,
            "tickers": ["AAA", "BBB"],
            "palette": {"body": "#FFFFFF"},
        }
    ],
}


def record(
    ticker: str,
    strength: int | None = None,
    resistance_strength: int | None = None,
) -> AnalysisSheetRecord:
    return AnalysisSheetRecord(
        ticker=ticker,
        score=8.2,
        entry=PriceRange(100.0, 102.0),
        washout=PriceRange(80.0, 82.0),
        entry_stop=95.0,
        washout_stop=75.0,
        resistance=PriceRange(120.0, 122.0),
        entry_strength=strength,
        washout_strength=None,
        resistance_strength=resistance_strength,
        generated_at=datetime(2026, 9, 5, tzinfo=timezone.utc),
        report_url=f"https://reports.example/?symbol={ticker}",
        score_background=None,
        score_note="",
        entry_strength_category=(
            "excepcional" if strength is not None and strength >= 95
            else "fuerte" if strength is not None and strength >= 85
            else "sólido" if strength is not None and strength >= 70
            else "moderado" if strength is not None and strength >= 40
            else "débil" if strength is not None
            else None
        ),
        entry_strength_factors=(
            "EMA20 ascendente; HVN confirmado" if strength is not None else None
        ),
        resistance_strength_category=(
            "excepcional"
            if resistance_strength is not None and resistance_strength >= 95
            else "fuerte"
            if resistance_strength is not None and resistance_strength >= 85
            else "sólido"
            if resistance_strength is not None and resistance_strength >= 70
            else "moderado"
            if resistance_strength is not None and resistance_strength >= 40
            else "débil"
            if resistance_strength is not None
            else None
        ),
        resistance_strength_factors=(
            "máximo semanal; call wall mensual"
            if resistance_strength is not None
            else None
        ),
        resistance_strength_breakdown=(
            {
                "estructura": 22,
                "volumen": 17,
                "opciones": 22,
                "confluencia": 14,
                "durabilidad": 13,
            }
            if resistance_strength is not None
            else None
        ),
    )


class AnalysisSheetTest(unittest.TestCase):
    def test_reads_ticker_and_live_value_together(self):
        self.assertEqual(analysis_read_ranges(LAYOUT), ["'Mercado'!E4:P5"])
        rows, prices = resolve_ticker_rows_and_prices(
            LAYOUT,
            [{"values": [["BBB", "64.39"], ["AAA", "101,0"]]}],
        )
        self.assertEqual(rows, {"BBB": 3, "AAA": 4})
        self.assertEqual(prices, {"BBB": 64.39, "AAA": 101.0})

    def test_reads_visible_scores_before_overwriting_them(self):
        values = [["BBB", "64.39", "", "", "", "", "", "", "", "", "", "5,4"]]
        self.assertEqual(resolve_visible_scores(LAYOUT, [{"values": values}]), {"BBB": 5.4})

    def test_writes_entry_washout_resistance_and_score_in_live_order(self):
        requests = build_analysis_value_requests(
            LAYOUT,
            {
                "AAA": record("AAA", 86, 88),
                "BBB": record("BBB", 72, 88),
            },
            ticker_rows={"BBB": 3, "AAA": 4},
            prices={"BBB": 110.0, "AAA": 101.0},
        )

        update = requests[0]["updateCells"]
        self.assertEqual(update["range"]["startColumnIndex"], 12)
        self.assertEqual(update["range"]["endColumnIndex"], 16)
        first = update["rows"][0]["values"]
        second = update["rows"][1]["values"]
        self.assertEqual(first[0]["userEnteredValue"]["stringValue"], "100,0-102,0")
        self.assertIn("Stop: 95,0 (-5,9%)", first[0]["note"])
        self.assertNotIn("Resistencia", first[0]["note"])
        self.assertIn("Fortaleza: 72/100 (sólido)", first[0]["note"])
        self.assertIn("Fortaleza: 86/100", second[0]["note"])
        self.assertIn("(fuerte)", second[0]["note"])
        self.assertIn("Factores: EMA20", second[0]["note"])
        self.assertEqual(
            second[2]["userEnteredValue"]["stringValue"],
            "120,0-122,0",
        )
        self.assertIn("Fortaleza: 88/100 (fuerte)", second[2]["note"])
        self.assertIn("Desglose: estructura 22/25", second[2]["note"])
        self.assertEqual(
            second[0]["userEnteredFormat"]["backgroundColorStyle"]["rgbColor"],
            {"red": 0.0, "green": 1.0, "blue": 0.0},
        )
        self.assertEqual(
            first[3]["textFormatRuns"][0]["format"]["link"]["uri"],
            "https://reports.example/?symbol=BBB",
        )

    def test_shows_supports_from_65_regardless_of_category_without_a_frame(self):
        weak = replace(
            record("AAA", 64),
            washout_strength=65,
            washout_strength_category="moderado",
            washout_strength_factors="SMA200",
        )
        requests = build_analysis_value_requests(
            LAYOUT,
            {"AAA": weak, "BBB": record("BBB", 65)},
            ticker_rows={"AAA": 3, "BBB": 4},
            prices={"AAA": 101.0, "BBB": 101.0},
            allow_missing=True,
        )

        entry, washout, resistance, _ = requests[0]["updateCells"]["rows"][0]["values"]
        self.assertEqual(entry["userEnteredValue"], {"stringValue": ""})
        self.assertEqual(entry["note"], "")
        self.assertEqual(
            washout["userEnteredValue"], {"stringValue": "80,0-82,0"}
        )
        self.assertIn("Fortaleza: 65/100 (moderado)", washout["note"])
        entry_65 = requests[0]["updateCells"]["rows"][1]["values"][0]
        self.assertEqual(entry_65["userEnteredValue"], {"stringValue": "100,0-102,0"})
        self.assertIn("Fortaleza: 65/100 (moderado)", entry_65["note"])
        self.assertEqual(resistance["userEnteredValue"], {"stringValue": ""})
        self.assertEqual(
            build_strength_border_requests(
                LAYOUT,
                {"AAA": weak, "BBB": record("BBB", 65)},
                ticker_rows={"AAA": 3, "BBB": 4},
            ),
            [],
        )

    def test_hides_resistance_below_solid_and_shows_solid(self):
        requests = build_analysis_value_requests(
            LAYOUT,
            {
                "AAA": record("AAA", 70, 69),
                "BBB": record("BBB", 70, 70),
            },
            ticker_rows={"AAA": 3, "BBB": 4},
            prices={"AAA": 110.0, "BBB": 110.0},
        )

        first, second = requests[0]["updateCells"]["rows"]
        hidden = first["values"][2]
        visible = second["values"][2]
        self.assertEqual(hidden["userEnteredValue"], {"stringValue": ""})
        self.assertEqual(hidden["note"], "")
        self.assertEqual(
            visible["userEnteredValue"], {"stringValue": "120,0-122,0"}
        )
        self.assertIn("Fortaleza: 70/100 (sólido)", visible["note"])

    def test_live_prices_refresh_both_support_backgrounds(self):
        requests = build_live_proximity_background_requests(
            LAYOUT,
            {
                "AAA": ("62,3-62,7", "61,2-61,6", "70,0-72,0"),
                "BBB": ("100,0-102,0", "80,0-82,0", "120,0-122,0"),
            },
            ticker_rows={"AAA": 3, "BBB": 4},
            prices={"AAA": 63.86, "BBB": 81.0},
        )

        rows = requests[0]["updateCells"]["rows"]
        aaa_colors = [
            cell["userEnteredFormat"]["backgroundColorStyle"]["rgbColor"]
            for cell in rows[0]["values"]
        ]
        self.assertEqual(aaa_colors, [{"red": 1.0, "green": 1.0, "blue": 1.0}] * 3)
        self.assertEqual(
            rows[1]["values"][1]["userEnteredFormat"]["backgroundColorStyle"]["rgbColor"],
            {"red": 0.0, "green": 1.0, "blue": 0.0},
        )

    def test_supports_use_bright_green_only_inside_and_no_color_above(self):
        requests = build_live_proximity_background_requests(
            LAYOUT,
            {
                "AAA": ("100,0-102,0", "80,0-82,0", ""),
                "BBB": ("100,0-102,0", "80,0-82,0", ""),
            },
            ticker_rows={"AAA": 3, "BBB": 4},
            prices={"AAA": 102.0, "BBB": 102.1},
        )

        rows = requests[0]["updateCells"]["rows"]
        inside = rows[0]["values"][0]["userEnteredFormat"][
            "backgroundColorStyle"
        ]["rgbColor"]
        above = rows[1]["values"][0]["userEnteredFormat"][
            "backgroundColorStyle"
        ]["rgbColor"]
        self.assertEqual(inside, {"red": 0.0, "green": 1.0, "blue": 0.0})
        self.assertEqual(above, {"red": 1.0, "green": 1.0, "blue": 1.0})

    def test_supports_below_without_assessed_extent_keep_normal_background(self):
        requests = build_live_proximity_background_requests(
            LAYOUT,
            {
                "AAA": ("100,0-102,0", "80,0-82,0", ""),
                "BBB": ("100,0-102,0", "80,0-82,0", ""),
            },
            ticker_rows={"AAA": 3, "BBB": 4},
            prices={"AAA": 98.5, "BBB": 98.4},
        )

        rows = requests[0]["updateCells"]["rows"]
        just_below = rows[0]["values"][0]["userEnteredFormat"][
            "backgroundColorStyle"
        ]["rgbColor"]
        broken = rows[1]["values"][0]["userEnteredFormat"][
            "backgroundColorStyle"
        ]["rgbColor"]
        self.assertEqual(
            just_below,
            {"red": 1.0, "green": 1.0, "blue": 1.0},
        )
        self.assertEqual(
            broken,
            {"red": 1.0, "green": 1.0, "blue": 1.0},
        )

    def test_entry_stays_normal_and_washout_inside_turns_green(self):
        requests = build_live_proximity_background_requests(
            LAYOUT,
            {
                "AAA": ("100,0-102,0", "80,0-82,0", ""),
                "BBB": ("100,0-102,0", "80,0-82,0", ""),
            },
            ticker_rows={"AAA": 3, "BBB": 4},
            prices={"AAA": 90.0, "BBB": 81.0},
        )

        rows = requests[0]["updateCells"]["rows"]
        entry_before_washout = rows[0]["values"][0]["userEnteredFormat"][
            "backgroundColorStyle"
        ]["rgbColor"]
        entry_at_washout = rows[1]["values"][0]["userEnteredFormat"][
            "backgroundColorStyle"
        ]["rgbColor"]
        washout_inside = rows[1]["values"][1]["userEnteredFormat"][
            "backgroundColorStyle"
        ]["rgbColor"]
        self.assertEqual(
            entry_before_washout,
            {"red": 1.0, "green": 1.0, "blue": 1.0},
        )
        self.assertEqual(
            entry_at_washout,
            {"red": 1.0, "green": 1.0, "blue": 1.0},
        )
        self.assertEqual(
            washout_inside,
            {"red": 0.0, "green": 1.0, "blue": 0.0},
        )

    def test_stop_distance_uses_the_midpoint_of_the_displayed_support(self):
        precise = replace(
            record("AAA", 70),
            entry=PriceRange(16.125, 16.275),
            entry_stop=15.75,
        )
        requests = build_analysis_value_requests(
            LAYOUT,
            {"AAA": precise},
            ticker_rows={"AAA": 3, "BBB": 4},
            prices={"AAA": 17.0},
            allow_missing=True,
        )

        entry = requests[0]["updateCells"]["rows"][0]["values"][0]
        self.assertEqual(entry["userEnteredValue"]["stringValue"], "16,1-16,3")
        self.assertIn("Stop: 15,8 (-2,5%)", entry["note"])

    def test_marks_strong_and_exceptional_supports_with_distinct_blue_frames(self):
        requests = build_strength_border_requests(
            LAYOUT,
            {"AAA": record("AAA", 85), "BBB": record("BBB", 95)},
            ticker_rows={"AAA": 3, "BBB": 4},
        )

        self.assertEqual(len(requests), 2)
        expected = (
            (3, {"red": 31 / 255, "green": 78 / 255, "blue": 120 / 255}),
            (4, {"red": 0.0, "green": 162 / 255, "blue": 1.0}),
        )
        for request, (row, color) in zip(requests, expected, strict=True):
            update = request["updateBorders"]
            self.assertEqual(update["range"]["startRowIndex"], row)
            self.assertEqual(update["range"]["startColumnIndex"], 12)
            self.assertTrue(
                all(
                    update[edge]["style"] == "SOLID_THICK"
                    for edge in ("top", "bottom", "left", "right")
                )
            )
            self.assertTrue(
                all(
                    update[edge]["colorStyle"]["rgbColor"] == color
                    for edge in ("top", "bottom", "left", "right")
                )
            )

        below_threshold = build_strength_border_requests(
            LAYOUT,
            {"AAA": record("AAA", 84)},
            ticker_rows={"AAA": 3, "BBB": 4},
        )
        self.assertEqual(below_threshold, [])

    def test_reapplies_frames_from_persisted_note_strengths(self):
        requests = build_strength_border_requests_for_values(
            LAYOUT,
            {"AAA": (89, 87, 91), "BBB": (79, None, None)},
            ticker_rows={"AAA": 4, "BBB": 3},
        )

        self.assertEqual(len(requests), 3)
        self.assertEqual(
            [request["updateBorders"]["range"]["startColumnIndex"] for request in requests],
            [12, 13, 14],
        )
        self.assertTrue(
            all(
                request["updateBorders"]["range"]["startRowIndex"] == 4
                for request in requests
            )
        )

    def test_frame_uses_current_table_after_global_sort_moves_ticker(self):
        layout = deepcopy(LAYOUT)
        layout["blocks"] = [
            {**LAYOUT["blocks"][0], "tickers": ["AAA"]},
            {
                **LAYOUT["blocks"][0],
                "table_name": "Other",
                "start_column": "Q",
                "end_column": "AB",
                "tickers": ["BBB"],
            },
        ]
        rows = TickerRows(
            {"AAA": 4, "BBB": 3},
            table_by_ticker={"AAA": "Other", "BBB": "Demo"},
        )

        requests = build_strength_border_requests_for_values(
            layout,
            {"AAA": (87, None, None)},
            ticker_rows=rows,
        )

        border_range = requests[0]["updateBorders"]["range"]
        self.assertEqual(border_range["startRowIndex"], 4)
        self.assertEqual(border_range["startColumnIndex"], 25)

    def test_resistance_uses_blue_proximity_without_reappearing_in_support_notes(self):
        requests = build_analysis_value_requests(
            LAYOUT,
            {"AAA": record("AAA", 70, 88), "BBB": record("BBB", 70, 88)},
            ticker_rows={"AAA": 3, "BBB": 4},
            prices={"AAA": 120.5, "BBB": 118.8},
        )

        entry, _, inside, _ = requests[0]["updateCells"]["rows"][0]["values"]
        self.assertNotIn("Resistencia", entry["note"])
        self.assertEqual(
            inside["userEnteredFormat"]["backgroundColorStyle"]["rgbColor"],
            {"red": 0.0, "green": 176 / 255, "blue": 240 / 255},
        )
        near = requests[0]["updateCells"]["rows"][1]["values"][2]
        self.assertEqual(
            near["userEnteredFormat"]["backgroundColorStyle"]["rgbColor"],
            {"red": 207 / 255, "green": 226 / 255, "blue": 243 / 255},
        )

    def test_resistance_blue_is_limited_to_held_tickers(self):
        records = {"AAA": record("AAA", 70, 88), "BBB": record("BBB", 70, 88)}
        requests = build_analysis_value_requests(
            LAYOUT,
            records,
            ticker_rows={"AAA": 3, "BBB": 4},
            prices={"AAA": 120.5, "BBB": 120.5},
            held_tickers={"AAA"},
        )

        rows = requests[0]["updateCells"]["rows"]
        held = rows[0]["values"][2]["userEnteredFormat"][
            "backgroundColorStyle"
        ]["rgbColor"]
        tracking = rows[1]["values"][2]["userEnteredFormat"][
            "backgroundColorStyle"
        ]["rgbColor"]
        self.assertEqual(
            held,
            {"red": 0.0, "green": 176 / 255, "blue": 240 / 255},
        )
        self.assertEqual(tracking, {"red": 1.0, "green": 1.0, "blue": 1.0})

        live = build_live_proximity_background_requests(
            LAYOUT,
            {
                "AAA": ("100,0-102,0", "80,0-82,0", "120,0-122,0"),
                "BBB": ("100,0-102,0", "80,0-82,0", "120,0-122,0"),
            },
            ticker_rows={"AAA": 3, "BBB": 4},
            prices={"AAA": 120.5, "BBB": 120.5},
            held_tickers={"AAA"},
        )
        live_rows = live[0]["updateCells"]["rows"]
        self.assertEqual(
            live_rows[0]["values"][2]["userEnteredFormat"][
                "backgroundColorStyle"
            ]["rgbColor"],
            held,
        )
        self.assertEqual(
            live_rows[1]["values"][2]["userEnteredFormat"][
                "backgroundColorStyle"
            ]["rgbColor"],
            tracking,
        )

    def test_partial_publish_blanks_only_the_missing_ticker(self):
        requests = build_analysis_value_requests(
            LAYOUT,
            {"AAA": record("AAA")},
            ticker_rows={"AAA": 3, "BBB": 4},
            prices={"AAA": 101.0, "BBB": 50.0},
            allow_missing=True,
        )

        rows = requests[0]["updateCells"]["rows"]
        self.assertEqual(rows[0]["values"][3]["userEnteredValue"], {"stringValue": "8,2"})
        self.assertTrue(
            all(
                cell["userEnteredValue"] == {"stringValue": ""}
                and cell["textFormatRuns"] == []
                for cell in rows[1]["values"]
            )
        )

if __name__ == "__main__":
    unittest.main()
