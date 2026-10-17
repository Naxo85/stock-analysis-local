from copy import deepcopy
import unittest

from stock_analysis.controller.global_sheet_sort import build_global_sort_plan
from stock_analysis.controller.sheet_layout import load_market_sheet_layout
from test_global_sheet_sort import spreadsheet


class TickerLinkRepairTest(unittest.TestCase):
    def setUp(self):
        self.layout = load_market_sheet_layout()
        self.order = [ticker for group in self.layout["groups"] for ticker in group["tickers"]]
        self.state = spreadsheet(self.layout, "Sector", order=self.order, held_tickers={"CLS"})

    def ticker_cell(self, ticker="CLS"):
        for data in self.state["sheets"][0]["data"][:2]:
            for row in data["rowData"]:
                cell = row["values"][1]
                if cell["effectiveValue"]["stringValue"] == ticker:
                    return cell

    def break_cls(self):
        cell = self.ticker_cell()
        cell["userEnteredValue"] = {"stringValue": "CLS"}
        cell["userEnteredFormat"]["textFormat"] = {"underline": False, "bold": True}
        cell["note"] = "existing ticker note"
        cell["textFormatRuns"] = [{"startIndex": 0, "format": {"link": {"uri": "https://wrong.example/"}}}]
        return cell

    def test_stable_sector_order_repairs_only_the_missing_link(self):
        self.break_cls()
        original = deepcopy(self.state)
        plan = build_global_sort_plan(self.layout, self.state)
        self.assertFalse(plan.changed)
        self.assertEqual(len(plan.requests), 1)
        update = plan.requests[0]["updateCells"]
        self.assertEqual(update["range"]["endRowIndex"] - update["range"]["startRowIndex"], 1)
        self.assertEqual(update["range"]["endColumnIndex"] - update["range"]["startColumnIndex"], 1)
        repaired = update["rows"][0]["values"][0]
        self.assertEqual(repaired["userEnteredValue"], {"formulaValue": '=HYPERLINK("https://finance.yahoo.com/quote/CLS/";"CLS")'})
        self.assertTrue(repaired["userEnteredFormat"]["textFormat"]["underline"])
        self.assertEqual(repaired["userEnteredFormat"]["textFormat"]["link"]["uri"], "https://finance.yahoo.com/quote/CLS/")
        self.assertNotIn("textFormatRuns", repaired)
        self.assertNotIn("backgroundColorStyle", update["fields"])
        self.assertNotIn("note", update["fields"])
        self.assertEqual(self.state, original)
        self.assertIn("CLS", plan.held_tickers)

    def test_reorder_repairs_link_in_its_destination_and_preserves_position(self):
        original = deepcopy(self.break_cls())
        self.state["sheets"][0]["data"][-1]["rowData"][0]["values"][0]["userEnteredValue"] = {"stringValue": "Fuerza"}
        self.state["sheets"][0]["data"][-1]["rowData"][0]["values"][0]["effectiveValue"] = {"stringValue": "Fuerza"}
        plan = build_global_sort_plan(self.layout, self.state)
        self.assertTrue(plan.changed)
        repaired = [cell for request in plan.requests for row in request["updateCells"]["rows"] for cell in row["values"] if cell.get("userEnteredValue", {}).get("formulaValue") == '=HYPERLINK("https://finance.yahoo.com/quote/CLS/";"CLS")']
        self.assertEqual(len(repaired), 1)
        self.assertEqual(repaired[0]["userEnteredFormat"]["backgroundColorStyle"], original["userEnteredFormat"]["backgroundColorStyle"])
        self.assertTrue(repaired[0]["userEnteredFormat"]["textFormat"]["bold"])
        self.assertEqual(repaired[0]["note"], original["note"])
        self.assertIn("CLS", plan.held_tickers)

    def test_valid_links_are_not_rewritten_and_repair_is_idempotent(self):
        self.assertEqual(build_global_sort_plan(self.layout, self.state).requests, [])
        self.break_cls()
        plan = build_global_sort_plan(self.layout, self.state)
        self.ticker_cell().update(plan.requests[0]["updateCells"]["rows"][0]["values"][0])
        self.assertEqual(build_global_sort_plan(self.layout, self.state).requests, [])

    def test_wrong_destination_is_repaired_but_comma_separator_is_valid(self):
        cell = self.ticker_cell()
        cell["userEnteredValue"] = {"formulaValue": '=HYPERLINK("https://wrong.example/";"CLS")'}
        self.assertEqual(len(build_global_sort_plan(self.layout, self.state).requests), 1)
        cell["userEnteredValue"] = {"formulaValue": '=HYPERLINK("https://finance.yahoo.com/quote/CLS/","CLS")'}
        self.assertEqual(build_global_sort_plan(self.layout, self.state).requests, [])


if __name__ == "__main__":
    unittest.main()
