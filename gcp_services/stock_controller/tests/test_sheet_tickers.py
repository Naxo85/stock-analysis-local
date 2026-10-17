from __future__ import annotations

import unittest

from stock_analysis.controller.sheet_layout import load_market_sheet_layout
from stock_analysis.controller.sheet_tickers import (
    configured_ticker_rows,
    resolve_ticker_rows,
    ticker_read_ranges,
)


def value_ranges(layout: dict) -> list[dict]:
    return [
        {"values": [[ticker] for ticker in block["tickers"]]}
        for block in layout["blocks"]
    ]


class SheetTickersTest(unittest.TestCase):
    def setUp(self) -> None:
        self.layout = load_market_sheet_layout()

    def test_read_ranges_cover_only_the_two_ticker_columns(self) -> None:
        self.assertEqual(
            ticker_read_ranges(self.layout),
            [
                f"'Mercado'!K4:K{3 + len(self.layout['blocks'][0]['tickers'])}",
                f"'Mercado'!Z4:Z{3 + len(self.layout['blocks'][1]['tickers'])}",
            ],
        )

    def test_analysis_sort_changes_live_rows_without_changing_identity(self) -> None:
        ranges = value_ranges(self.layout)
        ranges[0]["values"][0:2] = [["MRVL"], ["AMD"]]

        rows = resolve_ticker_rows(self.layout, ranges)

        configured = configured_ticker_rows(self.layout)
        self.assertEqual(rows["MRVL"], configured["AMD"])
        self.assertEqual(rows["AMD"], configured["MRVL"])

    def test_duplicate_or_missing_ticker_aborts_resolution(self) -> None:
        ranges = value_ranges(self.layout)
        ranges[0]["values"][1] = [ranges[0]["values"][0][0]]

        with self.assertRaisesRegex(ValueError, "duplicates=.*AMD"):
            resolve_ticker_rows(self.layout, ranges)

    def test_ticker_can_move_between_the_two_native_tables(self) -> None:
        ranges = value_ranges(self.layout)
        left = ranges[0]["values"][0][0]
        right = ranges[1]["values"][0][0]
        ranges[0]["values"][0] = [right]
        ranges[1]["values"][0] = [left]

        rows = resolve_ticker_rows(self.layout, ranges)

        self.assertEqual(rows.table_by_ticker[right], "Izquierda")
        self.assertEqual(rows.table_by_ticker[left], "Derecha")
        self.assertEqual(rows[right], self.layout["blocks"][0]["header_row"])
        self.assertEqual(rows[left], self.layout["blocks"][1]["header_row"])


if __name__ == "__main__":
    unittest.main()
