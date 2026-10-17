import json
import tempfile
import unittest
from pathlib import Path

from stock_analysis.controller.portfolio_sheet import (
    build_group_shot_strip_requests,
    build_group_summary_position_requests,
    build_portfolio_format_requests,
    load_held_tickers,
    load_positions,
    update_positions,
)
from stock_analysis.controller.sheet_layout import load_market_sheet_layout
from stock_analysis.controller.sheet_tickers import configured_ticker_rows


class PortfolioSheetTest(unittest.TestCase):
    def test_declared_portfolio_has_valid_shots_for_followed_tickers(self) -> None:
        positions = load_positions()
        followed = set(configured_ticker_rows(load_market_sheet_layout()))
        self.assertTrue(positions)
        self.assertLessEqual(set(positions), followed)
        self.assertTrue(all(shots in {1, 2} for shots in positions.values()))
        self.assertEqual(set(load_held_tickers()), set(positions))

    def test_update_adds_and_removes_tickers_atomically(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "portfolio.json"
            path.write_text(
                json.dumps({"positions": {"AAA": 1, "SPCX": 1}}), encoding="utf-8"
            )
            positions = update_positions(
                set_shots={"rklb": 1}, remove=["SPCX"], path=path
            )
            saved = json.loads(path.read_text(encoding="utf-8"))

        self.assertEqual(positions, {"AAA": 1, "RKLB": 1})
        self.assertEqual(saved["positions"], {"AAA": 1, "RKLB": 1})

    def test_reconciliation_marks_rklb_and_restores_spcx(self) -> None:
        layout = load_market_sheet_layout()
        rows = configured_ticker_rows(layout)
        requests = build_portfolio_format_requests(layout, ["RKLB"])
        by_cell = {}
        for request in requests:
            update = request["repeatCell"]
            key = (
                update["range"]["startRowIndex"],
                update["range"]["startColumnIndex"],
            )
            by_cell[key] = update["cell"]["userEnteredFormat"][
                "backgroundColorStyle"
            ]["rgbColor"]

        self.assertEqual(len(requests), len(rows))
        self.assertEqual(by_cell[(rows["RKLB"], 25)], {"red": 0.0, "green": 1.0, "blue": 1.0})
        self.assertEqual(by_cell[(rows["SPCX"], 25)], {"red": 1.0, "green": 1.0, "blue": 1.0})

    def test_shot_count_selects_single_or_double_color(self) -> None:
        layout = load_market_sheet_layout()
        rows = configured_ticker_rows(layout)
        requests = build_portfolio_format_requests(layout, {"RKLB": 1, "SPCX": 2})
        by_cell = {
            (
                request["repeatCell"]["range"]["startRowIndex"],
                request["repeatCell"]["range"]["startColumnIndex"],
            ): request["repeatCell"]["cell"]["userEnteredFormat"][
                "backgroundColorStyle"
            ]["rgbColor"]
            for request in requests
        }

        self.assertEqual(by_cell[(rows["RKLB"], 25)], {"red": 0.0, "green": 1.0, "blue": 1.0})
        self.assertEqual(
            by_cell[(rows["SPCX"], 25)],
            {"red": 0.0, "green": 184 / 255, "blue": 212 / 255},
        )

    def test_sorted_table_keeps_portfolio_color_with_ticker(self) -> None:
        layout = load_market_sheet_layout()
        rows = configured_ticker_rows(layout)
        rows["RKLB"], rows["SPCX"] = rows["SPCX"], rows["RKLB"]

        requests = build_portfolio_format_requests(
            layout, {"RKLB": 1}, ticker_rows=rows
        )
        by_cell = {
            (
                request["repeatCell"]["range"]["startRowIndex"],
                request["repeatCell"]["range"]["startColumnIndex"],
            ): request["repeatCell"]["cell"]["userEnteredFormat"][
                "backgroundColorStyle"
            ]["rgbColor"]
            for request in requests
        }

        self.assertEqual(by_cell[(rows["RKLB"], 25)], {"red": 0.0, "green": 1.0, "blue": 1.0})
        self.assertEqual(by_cell[(rows["SPCX"], 25)], {"red": 1.0, "green": 1.0, "blue": 1.0})

    def test_group_summary_counts_positions_and_shots_across_both_tables(self) -> None:
        layout = load_market_sheet_layout()
        requests = build_group_summary_position_requests(
            layout,
            {"AMD": 1, "TSM": 2, "MU": 1},
        )

        update = requests[0]["updateCells"]
        self.assertEqual(update["range"]["startColumnIndex"], 6)
        self.assertEqual(update["range"]["endColumnIndex"], 8)
        self.assertEqual(
            [cell["userEnteredValue"]["numberValue"] for cell in update["rows"][0]["values"]],
            [2, 3],
        )
        self.assertEqual(
            [cell["userEnteredValue"]["numberValue"] for cell in update["rows"][1]["values"]],
            [1, 1],
        )

    def test_group_shot_strip_repeats_subsector_exposure_and_tracks_sort(self) -> None:
        layout = load_market_sheet_layout()
        rows = configured_ticker_rows(layout)
        rows["AMD"], rows["TSM"] = rows["TSM"], rows["AMD"]

        requests = build_group_shot_strip_requests(
            layout,
            {"AMD": 2, "TSM": 1, "MU": 1},
            ticker_rows=rows,
        )

        self.assertEqual(len(requests), 2)
        left = requests[0]["updateCells"]
        self.assertEqual(left["range"]["startColumnIndex"], 9)
        values = [
            row["values"][0]["userEnteredValue"]["numberValue"]
            for row in left["rows"]
        ]
        ordered = sorted(layout["blocks"][0]["tickers"], key=rows.__getitem__)
        self.assertEqual(values[ordered.index("AMD")], 3)
        self.assertEqual(values[ordered.index("TSM")], 3)
        self.assertEqual(values[ordered.index("MU")], 1)

    def test_update_can_set_double_shot(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "portfolio.json"
            path.write_text(json.dumps({"positions": {"AAA": 1}}), encoding="utf-8")
            positions = update_positions(set_shots={"AAA": 2}, path=path)
        self.assertEqual(positions, {"AAA": 2})


if __name__ == "__main__":
    unittest.main()
