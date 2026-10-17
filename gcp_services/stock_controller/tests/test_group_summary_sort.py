from __future__ import annotations

import unittest
from datetime import datetime, timezone

from stock_analysis.contracts.market import BenchmarkMetrics, MarketSnapshot
from stock_analysis.controller.group_summary_sort import (
    build_sorted_group_summary_requests,
    group_summary_order_from_values,
)
from stock_analysis.controller.portfolio_sheet import build_group_summary_position_requests
from stock_analysis.controller.sheet_layout import load_market_sheet_layout


class GroupSummarySortTest(unittest.TestCase):
    def test_sort_keeps_complete_rows_and_position_writer_uses_live_order(self) -> None:
        layout = load_market_sheet_layout()
        groups = layout["groups"]
        physical = list(reversed(groups))
        changes = {group["benchmark"]: (index - 6) / 100 for index, group in enumerate(groups)}
        changes[groups[0]["benchmark"]] = None
        changes[groups[1]["benchmark"]] = changes[groups[2]["benchmark"]]
        metrics = tuple(
            BenchmarkMetrics(
                ticker=group["benchmark"], day_change=changes[group["benchmark"]],
                drawdown=-0.1, return_20d=0.02,
                observed_at=datetime(2026, 9, 29, tzinfo=timezone.utc), source="fixture",
            )
            for group in groups
        )
        snapshot = MarketSnapshot(
            schema_version=3, generated_at=datetime(2026, 9, 29, tzinfo=timezone.utc),
            universe=(), metrics=(), failures={}, benchmarks=metrics,
        )
        original = []
        for index, group in enumerate(physical):
            label = f"{group['sector']} / {group['label']}"
            cells = [{"userEnteredValue": {"stringValue": label},
                      "effectiveValue": {"stringValue": label}}]
            cells.extend({"userEnteredValue": {"stringValue": f"{index}-{column}"},
                          "note": f"row-{index}"} for column in range(1, 8))
            original.append({"values": cells})
        spreadsheet = {"sheets": [{
            "properties": {"sheetId": layout["sheet"]["sheet_id"]},
            "data": [{"startRow": layout["summary_table"]["header_row"],
                      "rowData": original}],
        }]}

        request = build_sorted_group_summary_requests(layout, snapshot, spreadsheet)[0]
        rows = [row["values"] for row in request["updateCells"]["rows"]]
        labels = [row[0]["userEnteredValue"]["stringValue"] for row in rows]
        original_index = {f"{g['sector']} / {g['label']}": i for i, g in enumerate(physical)}
        expected = sorted(
            groups,
            key=lambda group: (
                changes[group["benchmark"]] is None,
                -(changes[group["benchmark"]] or 0),
                original_index[f"{group['sector']} / {group['label']}"],
            ),
        )
        self.assertEqual(labels, [f"{g['sector']} / {g['label']}" for g in expected])
        for row, label in zip(rows, labels, strict=True):
            index = original_index[label]
            self.assertEqual(row[2]["userEnteredValue"]["stringValue"], f"{index}-2")
            self.assertEqual(row[6]["userEnteredValue"]["stringValue"], f"{index}-6")
            self.assertEqual(row[7]["note"], f"row-{index}")

        live_order = group_summary_order_from_values(layout, [[label] for label in labels])
        positions = {groups[0]["tickers"][0]: 2}
        counts = build_group_summary_position_requests(layout, positions, live_order)[0]
        by_label = dict(zip(labels, counts["updateCells"]["rows"], strict=True))
        owned_label = f"{groups[0]['sector']} / {groups[0]['label']}"
        self.assertEqual(
            [cell["userEnteredValue"]["numberValue"] for cell in by_label[owned_label]["values"]],
            [1, 2],
        )


if __name__ == "__main__":
    unittest.main()
