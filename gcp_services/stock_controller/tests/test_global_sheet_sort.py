from __future__ import annotations

import unittest

from stock_analysis.controller.global_sheet_sort import (
    build_global_sort_control_requests,
    build_global_sort_plan,
    global_sort_read_ranges,
)
from stock_analysis.controller.sheet_layout import (
    column_to_index,
    load_market_sheet_layout,
)


def cell(value: str | float, *, formula: bool = False) -> dict:
    if isinstance(value, float):
        return {
            "userEnteredValue": {"numberValue": value},
            "effectiveValue": {"numberValue": value},
        }
    entered = {"formulaValue": value} if formula else {"stringValue": value}
    return {
        "userEnteredValue": entered,
        "effectiveValue": {"stringValue": value.split('"')[-2] if formula else value},
    }


def spreadsheet(
    layout: dict,
    selection: str,
    *,
    order: list[str] | None = None,
    held_tickers: set[str] | None = None,
) -> dict:
    tickers = order or [
        ticker for block in layout["blocks"] for ticker in block["tickers"]
    ]
    strengths = {ticker: float(index) for index, ticker in enumerate(tickers, start=1)}
    scores = {ticker: float(index) / 10 for index, ticker in enumerate(tickers, start=1)}
    data = []
    cursor = 0
    for block in layout["blocks"]:
        count = len(block["tickers"])
        rows = []
        for ticker in tickers[cursor : cursor + count]:
            ticker_cell = cell(f'=HYPERLINK("{layout["links"]["ticker"].format(ticker=ticker)}";"{ticker}")', formula=True)
            if ticker in (held_tickers or set()):
                ticker_cell["userEnteredFormat"] = {
                    "backgroundColorStyle": {
                        "rgbColor": {"green": 1.0, "blue": 1.0}
                    }
                }
            values = [cell(0.0), ticker_cell]
            values.extend(cell(0.0) for _ in range(2))
            values.append(cell(strengths[ticker]))
            values.extend(cell(0.0) for _ in range(6))
            values[9] = cell("100,0-102,0")
            values[10] = cell("80,0-82,0")
            if ticker == "QBTS":
                values[9]["note"] = "Stop: 12,0\nFortaleza: 89/100 (fuerte)"
                values[10]["note"] = "Fortaleza: 87/100 (fuerte)"
            resistance = cell("120,0-122,0")
            if ticker == "QBTS":
                resistance["note"] = "Fortaleza: 91/100 (fuerte)"
            values.append(resistance)
            score = cell(f"{scores[ticker]:.1f}".replace(".", ","))
            score["note"] = f"report:{ticker}"
            score["userEnteredFormat"] = {
                "borders": {"bottom": {"style": "SOLID_MEDIUM"}}
            }
            values.append(score)
            values.append(cell(10.0 - scores[ticker]))
            rows.append({"values": values})
        cursor += count
        data.append(
            {
                "startRow": block["header_row"],
                "startColumn": column_to_index(block["start_column"]),
                "rowData": rows,
            }
        )
    data.append(
        {
            "startRow": 9,
            "startColumn": 2,
            "rowData": [{"values": [cell(selection)]}],
        }
    )
    return {
        "sheets": [
            {
                "properties": {"sheetId": layout["sheet"]["sheet_id"]},
                "data": data,
            }
        ]
    }


class GlobalSheetSortTest(unittest.TestCase):
    def setUp(self) -> None:
        self.layout = load_market_sheet_layout()
        self.tickers = [
            ticker
            for block in self.layout["blocks"]
            for ticker in block["tickers"]
        ]

    def test_reads_both_complete_tables_and_the_control(self) -> None:
        self.assertEqual(
            global_sort_read_ranges(self.layout),
            [f"'Mercado'!J4:W{3 + len(self.layout['blocks'][0]['tickers'])}", f"'Mercado'!Y4:AL{3 + len(self.layout['blocks'][1]['tickers'])}", "'Mercado'!C10"],
        )

    def test_note_sort_is_global_and_rebalances_both_tables(self) -> None:
        plan = build_global_sort_plan(
            self.layout, spreadsheet(self.layout, "Nota")
        )

        self.assertTrue(plan.changed)
        self.assertEqual(plan.ticker_rows[self.tickers[-1]], 3)
        self.assertEqual(
            plan.ticker_rows.table_by_ticker[self.tickers[-1]], "Izquierda"
        )
        self.assertEqual(plan.ticker_rows[self.tickers[0]], 25)
        self.assertEqual(
            plan.ticker_rows.table_by_ticker[self.tickers[0]], "Derecha"
        )
        first_score = plan.requests[0]["updateCells"]["rows"][0]["values"][-2]
        self.assertEqual(first_score["note"], f"report:{self.tickers[-1]}")
        self.assertNotIn("borders", first_score["userEnteredFormat"])
        self.assertEqual(plan.support_strengths["QBTS"], (89, 87, 91))
        self.assertEqual(
            plan.analysis_levels["QBTS"],
            ("100,0-102,0", "80,0-82,0", "120,0-122,0"),
        )

    def test_fresh_strength_values_drive_the_global_order(self) -> None:
        plan = build_global_sort_plan(
            self.layout,
            spreadsheet(self.layout, "Fuerza"),
            sort_values={"strength": {"RKLB": 999.0}},
        )

        self.assertEqual(plan.ticker_rows["RKLB"], 3)
        self.assertEqual(plan.ticker_rows.table_by_ticker["RKLB"], "Izquierda")

    def test_detects_held_tickers_from_their_portfolio_background(self) -> None:
        plan = build_global_sort_plan(
            self.layout,
            spreadsheet(self.layout, "Nota", held_tickers={"AMD", "RKLB"}),
        )

        self.assertEqual(plan.held_tickers, frozenset({"AMD", "RKLB"}))

    def test_sector_sort_uses_the_declared_color_group_order(self) -> None:
        plan = build_global_sort_plan(
            self.layout,
            spreadsheet(self.layout, "Sector", order=list(reversed(self.tickers))),
        )

        first_group = set(self.layout["groups"][0]["tickers"])
        first_eight = {
            ticker for ticker, row in plan.ticker_rows.items()
            if plan.ticker_rows.table_by_ticker[ticker] == "Izquierda" and row < 11
        }
        self.assertEqual(first_eight, first_group)

    def test_control_is_a_three_option_dropdown(self) -> None:
        requests = build_global_sort_control_requests(self.layout, "Nota")

        dropdown = requests[1]["updateCells"]["rows"][0]["values"][0]
        self.assertEqual(dropdown["userEnteredValue"], {"stringValue": "Tesis"})
        self.assertEqual(
            dropdown["userEnteredFormat"]["textFormat"]["fontSize"], 10
        )
        self.assertEqual(
            [
                item["userEnteredValue"]
                for item in dropdown["dataValidation"]["condition"]["values"]
            ],
            ["Tesis", "Setup", "Sector", "Fuerza"],
        )


if __name__ == "__main__":
    unittest.main()
