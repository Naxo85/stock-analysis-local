"""Keep every group-summary cell attached to its ETF while sorting by Día."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

from stock_analysis.contracts.market import MarketSnapshot
from stock_analysis.controller.global_sheet_sort import WRITABLE_CELL_FIELDS
from stock_analysis.controller.market_sheet import build_benchmark_value_requests
from stock_analysis.controller.sheet_layout import column_to_index


def group_summary_read_range(layout: Mapping[str, Any]) -> str:
    title = layout["sheet"]["title"].replace("'", "''")
    summary = layout["summary_table"]
    first = summary["header_row"] + 1
    last = summary["header_row"] + len(layout["groups"])
    return f"'{title}'!{summary['start_column']}{first}:{summary['end_column']}{last}"


def group_summary_order_from_values(
    layout: Mapping[str, Any], rows: list[list[Any]]
) -> list[str]:
    labels = [str(row[0]).strip() if row else "" for row in rows]
    expected = {f"{group['sector']} / {group['label']}" for group in layout["groups"]}
    if len(labels) != len(expected) or set(labels) != expected:
        raise ValueError("Live group summary does not match the configured groups")
    return labels


def build_sorted_group_summary_requests(
    layout: dict[str, Any],
    snapshot: MarketSnapshot,
    spreadsheet: Mapping[str, Any],
) -> list[dict[str, Any]]:
    """Rewrite A:H in numeric Día order, preserving each row's cells and styles."""
    metrics = {item.ticker: item for item in snapshot.benchmarks}
    groups = layout["groups"]
    summary = layout["summary_table"]
    width = column_to_index(summary["end_column"]) - column_to_index(summary["start_column"]) + 1
    benchmark_requests = build_benchmark_value_requests(layout, snapshot)
    if not benchmark_requests:
        raise ValueError("Cannot sort groups without every benchmark metric")
    metric_rows = benchmark_requests[0]["updateCells"]["rows"]
    sheet = next(
        item for item in spreadsheet.get("sheets", [])
        if item.get("properties", {}).get("sheetId") == layout["sheet"]["sheet_id"]
    )
    grid = next(
        item for item in sheet.get("data", [])
        if int(item.get("startRow", 0)) == summary["header_row"]
        and int(item.get("startColumn", 0)) == column_to_index(summary["start_column"])
    )
    raw_rows = list(grid.get("rowData", []))
    if len(raw_rows) < len(groups):
        raise ValueError("Live group summary has fewer rows than configured groups")

    by_label: dict[str, tuple[int, list[dict[str, Any]]]] = {}
    for index, raw in enumerate(raw_rows[: len(groups)]):
        values = list(raw.get("values", []))
        values.extend({} for _ in range(max(0, width - len(values))))
        label = str(
            values[0].get("effectiveValue", {}).get(
                "stringValue", values[0].get("userEnteredValue", {}).get("stringValue", "")
            )
        ).strip()
        if label in by_label:
            raise ValueError(f"Duplicate group summary row: {label}")
        by_label[label] = (
            index,
            [
                {field: deepcopy(cell[field]) for field in WRITABLE_CELL_FIELDS if field in cell}
                for cell in values[:width]
            ],
        )

    expected_labels = {f"{group['sector']} / {group['label']}" for group in groups}
    if set(by_label) != expected_labels:
        raise ValueError("Live group summary does not match the configured groups")

    ordered = []
    for group, metric_row in zip(groups, metric_rows, strict=True):
        label = f"{group['sector']} / {group['label']}"
        original_index, cells = by_label[label]
        for offset, update in enumerate(metric_row["values"], start=3):
            cell = cells[offset]
            if "userEnteredValue" in update:
                cell["userEnteredValue"] = update["userEnteredValue"]
            else:
                cell.pop("userEnteredValue", None)
            if "note" in update:
                cell["note"] = update["note"]
            current_format = cell.setdefault("userEnteredFormat", {})
            new_format = update["userEnteredFormat"]
            current_format["numberFormat"] = new_format["numberFormat"]
            current_format["backgroundColorStyle"] = new_format["backgroundColorStyle"]
            current_format.setdefault("textFormat", {})["foregroundColorStyle"] = (
                new_format["textFormat"]["foregroundColorStyle"]
            )
        day = metrics[group["benchmark"]].day_change
        ordered.append((day is None, -(day or 0.0), original_index, cells))
    ordered.sort(key=lambda item: item[:3])
    return [
        {
            "updateCells": {
                "range": {
                    "sheetId": layout["sheet"]["sheet_id"],
                    "startRowIndex": summary["header_row"],
                    "endRowIndex": summary["header_row"] + len(groups),
                    "startColumnIndex": column_to_index(summary["start_column"]),
                    "endColumnIndex": column_to_index(summary["end_column"]) + 1,
                },
                "rows": [{"values": item[3]} for item in ordered],
                "fields": ",".join(WRITABLE_CELL_FIELDS),
            }
        }
    ]
