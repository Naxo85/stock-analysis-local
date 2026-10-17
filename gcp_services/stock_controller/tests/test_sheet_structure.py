from __future__ import annotations

import copy
import unittest

from stock_analysis.controller.sheet_layout import column_to_index, load_market_sheet_layout
from stock_analysis.controller.sheet_structure import (
    build_panel_font_apply_requests,
    build_structure_requests,
    build_table_font_apply_requests,
    desired_named_ranges,
    desired_tables,
    plan_structure_changes,
)


def title_merges(layout: dict) -> list[dict]:
    sheet_id = layout["sheet"]["sheet_id"]
    summary = layout["summary_table"]
    return [
        {
            "sheetId": sheet_id,
            "startRowIndex": summary["title_row"] - 1,
            "endRowIndex": summary["title_row"],
            "startColumnIndex": column_to_index(summary["start_column"]),
            "endColumnIndex": column_to_index(summary["title_end_column"]) + 1,
        }
    ]


def clean_state(layout: dict) -> dict:
    return {
        "namedRanges": [
            {"namedRangeId": str(index), "name": name, "range": copy.deepcopy(grid_range)}
            for index, (name, grid_range) in enumerate(desired_named_ranges(layout).items(), start=1)
        ],
        "sheets": [
            {
                "properties": {"sheetId": layout["sheet"]["sheet_id"], "title": "Mercado"},
                "tables": [
                    {
                        "tableId": f"table-{index}",
                        "name": name,
                        "range": copy.deepcopy(table["range"]),
                        "rowsProperties": copy.deepcopy(table["rowsProperties"]),
                    }
                    for index, (name, table) in enumerate(
                        desired_tables(layout).items(), start=1
                    )
                ],
                "merges": title_merges(layout),
            }
        ],
    }


class SheetStructureTest(unittest.TestCase):
    def setUp(self) -> None:
        self.layout = load_market_sheet_layout()

    def test_table_font_is_declared_as_legacy_ten_points(self) -> None:
        self.assertEqual(self.layout["table_template"]["font_size"], 10)
        requests = build_table_font_apply_requests(
            self.layout["sheet"]["sheet_id"], self.layout
        )
        self.assertEqual(len(requests), 3)
        self.assertTrue(
            all(
                request["repeatCell"]["cell"]["userEnteredFormat"]["textFormat"]
                == {"fontFamily": "Arial", "fontSize": 10}
                for request in requests
            )
        )
        panel_requests = build_panel_font_apply_requests(
            self.layout["sheet"]["sheet_id"], self.layout
        )
        self.assertEqual(
            panel_requests[0]["repeatCell"]["cell"]["userEnteredFormat"]["textFormat"],
            {"fontFamily": "Arial", "fontSize": 10},
        )

    def test_matching_native_tables_have_empty_plan(self) -> None:
        state = clean_state(self.layout)
        self.assertEqual(plan_structure_changes(self.layout, state), [])
        self.assertEqual(build_structure_requests(self.layout, []), [])

    def test_repositioned_native_tables_are_recreated_without_overlap(self) -> None:
        state = clean_state(self.layout)
        old_ranges = ((0, 12), (15, 27))
        for table, (start, end) in zip(
            state["sheets"][0]["tables"], old_ranges, strict=True
        ):
            table["range"]["startColumnIndex"] = start
            table["range"]["endColumnIndex"] = end

        changes = plan_structure_changes(self.layout, state)

        self.assertEqual(
            [item["action"] for item in changes].count("delete_table"), 2
        )
        self.assertEqual(
            [item["action"] for item in changes].count("create_table"), 2
        )
        self.assertNotIn("move_table", [item["action"] for item in changes])

    def test_legacy_tables_and_merges_trigger_full_rebuild(self) -> None:
        state = clean_state(self.layout)
        sheet = state["sheets"][0]
        sheet["tables"].append(
            {
                "tableId": "old",
                "name": "Cuantica",
                "range": {
                    "sheetId": self.layout["sheet"]["sheet_id"],
                    "startRowIndex": 10,
                    "endRowIndex": 12,
                    "startColumnIndex": 5,
                    "endColumnIndex": 14,
                },
            }
        )
        sheet["merges"].append(
            {
                "sheetId": self.layout["sheet"]["sheet_id"],
                "startRowIndex": 10,
                "endRowIndex": 11,
                "startColumnIndex": 5,
                "endColumnIndex": 14,
            }
        )

        changes = plan_structure_changes(self.layout, state)
        actions = {item["action"] for item in changes}
        self.assertIn("delete_table", actions)
        self.assertIn("unmerge", actions)

        requests = build_structure_requests(self.layout, changes)
        request_types = [next(iter(item)) for item in requests]
        self.assertIn("deleteTable", request_types)
        self.assertIn("unmergeCells", request_types)
        self.assertNotIn("addTable", request_types)
        self.assertEqual(request_types.count("mergeCells"), 0)

    def test_missing_native_tables_named_range_and_summary_title_are_built(self) -> None:
        state = clean_state(self.layout)
        state["namedRanges"] = []
        state["sheets"][0]["tables"] = []
        state["sheets"][0]["merges"] = []

        changes = plan_structure_changes(self.layout, state)
        self.assertEqual(
            sum(item["action"] == "add_named_range" for item in changes), 1
        )
        self.assertEqual(sum(item["action"] == "merge_title" for item in changes), 1)
        self.assertEqual(sum(item["action"] == "create_table" for item in changes), 2)

        requests = build_structure_requests(self.layout, changes)
        request_types = [next(iter(item)) for item in requests]
        self.assertEqual(request_types.count("addNamedRange"), 1)
        self.assertEqual(request_types.count("mergeCells"), 1)
        self.assertEqual(request_types.count("addTable"), 2)
        written_values = [
            cell.get("userEnteredValue", {})
            for request in requests
            if "updateCells" in request
            for row in request["updateCells"].get("rows", [])
            for cell in row.get("values", [])
        ]
        self.assertEqual(written_values.count({"stringValue": "Mercado"}), 0)
        self.assertIn({"stringValue": "Resumen de grupos"}, written_values)

        dd6m_headers = [
            cell
            for request in requests
            if "updateCells" in request
            for row in request["updateCells"].get("rows", [])
            for cell in row.get("values", [])
            if cell.get("userEnteredValue") == {"stringValue": "DD6M"}
        ]
        self.assertEqual(len(dd6m_headers), 3)
        self.assertTrue(
            all("Rojo oscuro" in cell.get("note", "") for cell in dd6m_headers)
        )

    def test_named_range_drift_is_repaired_without_native_table(self) -> None:
        state = clean_state(self.layout)
        state["namedRanges"][0]["range"]["endRowIndex"] -= 1

        changes = plan_structure_changes(self.layout, state)
        self.assertEqual(
            [item["action"] for item in changes], ["update_named_range"]
        )
        requests = build_structure_requests(self.layout, changes)
        self.assertTrue(any("updateNamedRange" in request for request in requests))
        self.assertFalse(any("addTable" in request for request in requests))

    def test_group_summary_combines_label_then_color_strip_and_etf(self) -> None:
        state = clean_state(self.layout)
        state["namedRanges"] = []
        requests = build_structure_requests(
            self.layout, plan_structure_changes(self.layout, state)
        )
        summary_rows = next(
            request["updateCells"]["rows"]
            for request in requests
            if "updateCells" in request
            and request["updateCells"].get("range", {}).get("startRowIndex") == 13
            and request["updateCells"].get("range", {}).get("startColumnIndex") == 0
            and len(request["updateCells"].get("rows", [])) == 14
        )
        first = summary_rows[0]["values"]
        self.assertEqual(first[0]["userEnteredValue"], {"stringValue": "Semis / Chips"})
        self.assertNotIn("userEnteredValue", first[1])
        self.assertIn("SOXX", first[2]["userEnteredValue"]["formulaValue"])

if __name__ == "__main__":
    unittest.main()
