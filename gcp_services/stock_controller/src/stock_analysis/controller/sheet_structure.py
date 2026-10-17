from __future__ import annotations

from typing import Any

from stock_analysis.controller.global_sheet_sort import (
    build_global_sort_control_requests,
)
from stock_analysis.controller.sheet_layout import (
    build_alignment_apply_requests,
    build_dimension_apply_requests,
    build_table_border_apply_requests,
    column_to_index,
)


def _rgb(hex_color: str) -> dict[str, float]:
    value = hex_color.removeprefix("#")
    return {
        "red": int(value[0:2], 16) / 255,
        "green": int(value[2:4], 16) / 255,
        "blue": int(value[4:6], 16) / 255,
    }


def _grid_range(block: dict[str, Any], sheet_id: int) -> dict[str, int]:
    start_column = column_to_index(block["start_column"])
    return {
        "sheetId": sheet_id,
        "startRowIndex": block["header_row"] - 1,
        "endRowIndex": block["header_row"] + len(block["tickers"]),
        "startColumnIndex": start_column,
        "endColumnIndex": column_to_index(block["end_column"]) + 1,
    }


def _merge_range(
    block: dict[str, Any], sheet_id: int, benchmark_offset: int
) -> dict[str, int]:
    start_column = column_to_index(block["start_column"])
    return {
        "sheetId": sheet_id,
        "startRowIndex": block["benchmark_row"] - 1,
        "endRowIndex": block["benchmark_row"],
        "startColumnIndex": start_column + benchmark_offset,
        "endColumnIndex": column_to_index(block["end_column"]) + 1,
    }


def _rows_properties(block: dict[str, Any]) -> dict[str, Any]:
    palette = block["palette"]
    return {
        "headerColorStyle": {"rgbColor": _rgb(palette["header"])},
        "firstBandColorStyle": {"rgbColor": _rgb(palette["first_row"])},
        "secondBandColorStyle": {"rgbColor": _rgb(palette["alternate_row"])},
    }


def _find_sheet(spreadsheet: dict[str, Any], sheet_id: int) -> dict[str, Any]:
    for sheet in spreadsheet.get("sheets", []):
        if sheet.get("properties", {}).get("sheetId") == sheet_id:
            return sheet
    raise ValueError(f"Sheet {sheet_id} is missing from spreadsheet state")


def _range_key(value: dict[str, Any]) -> tuple[int, int, int, int, int]:
    return (
        value["sheetId"],
        value["startRowIndex"],
        value["endRowIndex"],
        value["startColumnIndex"],
        value["endColumnIndex"],
    )


def _colors_match(left: dict[str, Any], right: dict[str, Any]) -> bool:
    for key in ("headerColorStyle", "firstBandColorStyle", "secondBandColorStyle"):
        left_rgb = left.get(key, {}).get("rgbColor", {})
        right_rgb = right.get(key, {}).get("rgbColor", {})
        for channel in ("red", "green", "blue"):
            if abs(float(left_rgb.get(channel, 0)) - float(right_rgb.get(channel, 0))) > 1e-6:
                return False
    return True


def desired_tables(layout: dict[str, Any]) -> dict[str, dict[str, Any]]:
    sheet_id = layout["sheet"]["sheet_id"]
    return {
        block["table_name"]: {
            "block_id": block["id"],
            "name": block["table_name"],
            "range": _grid_range(block, sheet_id),
            "rowsProperties": _rows_properties(block),
        }
        for block in layout["blocks"]
    }


def _plan_legacy_structure_changes(
    layout: dict[str, Any], spreadsheet: dict[str, Any]
) -> list[dict[str, Any]]:
    """Compare native Sheets tables and benchmark merges with the manifest."""
    sheet_id = layout["sheet"]["sheet_id"]
    sheet = _find_sheet(spreadsheet, sheet_id)
    benchmark_offset = layout["table_template"]["benchmark_start_column_offset"]
    desired = desired_tables(layout)
    current = {table["name"]: table for table in sheet.get("tables", [])}
    lanes = {
        (
            column_to_index(block["start_column"]),
            column_to_index(block["end_column"]) + 1,
        )
        for block in layout["blocks"]
    }
    changes: list[dict[str, Any]] = []

    for name, table in current.items():
        table_range = table["range"]
        lane = (table_range["startColumnIndex"], table_range["endColumnIndex"])
        if name not in desired and lane in lanes:
            changes.append(
                {
                    "action": "delete_table",
                    "target": name,
                    "table_id": table["tableId"],
                    "before": {"range": table_range},
                    "after": None,
                }
            )

    for name, expected in desired.items():
        table = current.get(name)
        if table is None:
            changes.append(
                {
                    "action": "create_table",
                    "target": name,
                    "block_id": expected["block_id"],
                    "before": None,
                    "after": expected,
                }
            )
            continue
        if _range_key(table["range"]) != _range_key(expected["range"]):
            changes.append(
                {
                    "action": "move_table",
                    "target": name,
                    "block_id": expected["block_id"],
                    "table_id": table["tableId"],
                    "before": {"range": table["range"]},
                    "after": expected,
                }
            )
        if not _colors_match(table.get("rowsProperties", {}), expected["rowsProperties"]):
            changes.append(
                {
                    "action": "style_table",
                    "target": name,
                    "block_id": expected["block_id"],
                    "table_id": table["tableId"],
                    "before": {"rowsProperties": table.get("rowsProperties", {})},
                    "after": expected,
                }
            )

    desired_merges = {
        _range_key(_merge_range(block, sheet_id, benchmark_offset)): block["id"]
        for block in layout["blocks"]
    }
    current_merges = {
        _range_key(item): item for item in sheet.get("merges", [])
    }
    managed_merge_columns = {
        (
            column_to_index(block["start_column"]) + benchmark_offset,
            column_to_index(block["end_column"]) + 1,
        )
        for block in layout["blocks"]
    }
    forced_unmerge_keys = set()
    for change in changes:
        if change["action"] != "delete_table":
            continue
        table_range = change["before"]["range"]
        forced_unmerge_keys.add(
            (
                table_range["sheetId"],
                table_range["startRowIndex"] - 1,
                table_range["startRowIndex"],
                table_range["startColumnIndex"] + benchmark_offset,
                table_range["endColumnIndex"],
            )
        )

    unmerged_keys = set()
    for key, item in current_merges.items():
        columns = (item["startColumnIndex"], item["endColumnIndex"])
        if columns in managed_merge_columns and (
            key not in desired_merges or key in forced_unmerge_keys
        ):
            changes.append(
                {
                    "action": "unmerge_benchmark",
                    "target": f"row:{item['startRowIndex'] + 1}",
                    "before": item,
                    "after": None,
                }
            )
            unmerged_keys.add(key)
    for key, block_id in desired_merges.items():
        if key not in current_merges or key in unmerged_keys:
            item = {
                "sheetId": key[0],
                "startRowIndex": key[1],
                "endRowIndex": key[2],
                "startColumnIndex": key[3],
                "endColumnIndex": key[4],
            }
            changes.append(
                {
                    "action": "merge_benchmark",
                    "target": block_id,
                    "block_id": block_id,
                    "before": None,
                    "after": item,
                }
            )
    return changes


def _content_requests(layout: dict[str, Any], block: dict[str, Any]) -> list[dict[str, Any]]:
    sheet_id = layout["sheet"]["sheet_id"]
    start_column = column_to_index(block["start_column"])
    end_column = column_to_index(block["end_column"]) + 1
    benchmark_column = start_column + layout["table_template"][
        "benchmark_start_column_offset"
    ]
    palette = block["palette"]
    benchmark_cell = {
        "userEnteredFormat": {
            "backgroundColorStyle": {"rgbColor": _rgb(palette["benchmark_background"])},
            "horizontalAlignment": "CENTER",
            "verticalAlignment": "MIDDLE",
            "wrapStrategy": "CLIP",
            "textFormat": {
                "foregroundColorStyle": {"rgbColor": _rgb(palette["benchmark_text"])},
                "fontFamily": "Arial",
                "fontSize": 10,
                "bold": True,
            },
        },
    }
    headers = [
        {"userEnteredValue": {"stringValue": header}}
        for header in layout["table_template"]["headers"]
    ]
    ticker_rows = [
        {
            "values": [
                {
                    "userEnteredValue": {
                        "formulaValue": (
                            f'=HYPERLINK("https://finance.yahoo.com/quote/{ticker}/";'
                            f'"{ticker}")'
                        )
                    }
                }
            ]
        }
        for ticker in block["tickers"]
    ]
    return [
        {
            "updateCells": {
                "start": {
                    "sheetId": sheet_id,
                    "rowIndex": block["benchmark_row"] - 1,
                    "columnIndex": benchmark_column,
                },
                "rows": [{"values": [benchmark_cell]}],
                "fields": "userEnteredFormat",
            }
        },
        {
            "updateCells": {
                "range": {
                    "sheetId": sheet_id,
                    "startRowIndex": block["header_row"] - 1,
                    "endRowIndex": block["header_row"],
                    "startColumnIndex": start_column,
                    "endColumnIndex": end_column,
                },
                "rows": [{"values": headers}],
                "fields": "userEnteredValue",
            }
        },
        {
            "updateCells": {
                "range": {
                    "sheetId": sheet_id,
                    "startRowIndex": block["header_row"],
                    "endRowIndex": block["header_row"] + len(block["tickers"]),
                    "startColumnIndex": start_column,
                    "endColumnIndex": start_column + 1,
                },
                "rows": ticker_rows,
                "fields": "userEnteredValue",
            }
        },
    ]


def _build_legacy_structure_requests(
    layout: dict[str, Any], changes: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Translate a structure plan into ordered, idempotent Sheets requests."""
    if not changes:
        return []
    sheet_id = layout["sheet"]["sheet_id"]
    blocks = {block["id"]: block for block in layout["blocks"]}
    requests: list[dict[str, Any]] = []

    for change in changes:
        if change["action"] == "unmerge_benchmark":
            requests.append({"unmergeCells": {"range": change["before"]}})

    deleted = [item for item in changes if item["action"] == "delete_table"]
    for change in deleted:
        requests.append({"deleteTable": {"tableId": change["table_id"]}})
        table_range = change["before"]["range"]
        clear_range = dict(table_range)
        clear_range["startRowIndex"] -= 1
        requests.append(
            {
                "updateCells": {
                    "range": clear_range,
                    "fields": "userEnteredValue,note,dataValidation,userEnteredFormat",
                }
            }
        )

    moves = [item for item in changes if item["action"] == "move_table"]
    upward = sorted(
        (
            item
            for item in moves
            if item["after"]["range"]["startRowIndex"]
            < item["before"]["range"]["startRowIndex"]
        ),
        key=lambda item: item["before"]["range"]["startRowIndex"],
    )
    downward = sorted(
        (item for item in moves if item not in upward),
        key=lambda item: item["before"]["range"]["startRowIndex"],
        reverse=True,
    )
    for change in [*upward, *downward]:
        before = change["before"]["range"]
        after = change["after"]["range"]
        source = dict(before)
        source["startRowIndex"] -= 1
        requests.append(
            {
                "cutPaste": {
                    "source": source,
                    "destination": {
                        "sheetId": sheet_id,
                        "rowIndex": after["startRowIndex"] - 1,
                        "columnIndex": after["startColumnIndex"],
                    },
                    "pasteType": "PASTE_NORMAL",
                }
            }
        )
        requests.append(
            {
                "updateTable": {
                    "table": {"tableId": change["table_id"], "range": after},
                    "fields": "range",
                }
            }
        )

    changed_blocks = {
        item["block_id"]
        for item in changes
        if item["action"] in {"create_table", "move_table"}
    }
    for block in layout["blocks"]:
        if block["id"] in changed_blocks:
            requests.extend(_content_requests(layout, block))

    for change in changes:
        if change["action"] == "create_table":
            requests.append(
                {
                    "addTable": {
                        "table": {
                            "name": change["target"],
                            "range": change["after"]["range"],
                            "rowsProperties": change["after"]["rowsProperties"],
                        }
                    }
                }
            )
        elif change["action"] == "style_table":
            requests.append(
                {
                    "updateTable": {
                        "table": {
                            "tableId": change["table_id"],
                            "rowsProperties": change["after"]["rowsProperties"],
                        },
                        "fields": "rowsProperties",
                    }
                }
            )

    for change in changes:
        if change["action"] == "merge_benchmark":
            requests.append(
                {"mergeCells": {"range": change["after"], "mergeType": "MERGE_ALL"}}
            )

    requests.extend(build_dimension_apply_requests(sheet_id, layout))
    requests.extend(build_alignment_apply_requests(sheet_id, layout))
    requests.extend(build_table_border_apply_requests(sheet_id, layout))
    return requests


def _v3_named_ranges(layout: dict[str, Any]) -> dict[str, dict[str, Any]]:
    sheet_id = layout["sheet"]["sheet_id"]
    summary = layout["summary_table"]
    return {
        "Mercado_ResumenGrupos": {
            "sheetId": sheet_id,
            "startRowIndex": summary["title_row"] - 1,
            "endRowIndex": summary["header_row"] + len(layout["groups"]),
            "startColumnIndex": column_to_index(summary["start_column"]),
            "endColumnIndex": column_to_index(summary["title_end_column"]) + 1,
        }
    }


def desired_named_ranges(layout: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Return the invisible structural anchor for the group summary."""
    if layout.get("schema_version", 1) < 3:
        return {}
    return _v3_named_ranges(layout)


def _v3_title_merges(layout: dict[str, Any]) -> list[dict[str, int]]:
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


def _managed_merge(merge: dict[str, Any], layout: dict[str, Any]) -> bool:
    summary = layout["summary_table"]
    managed_start = min(
        column_to_index(summary["start_column"]),
        *(column_to_index(block["start_column"]) for block in layout["blocks"]),
    )
    managed_end = max(
        column_to_index(summary["title_end_column"]) + 1,
        *(column_to_index(block["end_column"]) + 1 for block in layout["blocks"]),
    )
    return (
        merge.get("sheetId") == layout["sheet"]["sheet_id"]
        and merge.get("startRowIndex", 0) < layout["sheet"]["row_count"]
        and merge.get("endRowIndex", 0) > 1
        and merge.get("startColumnIndex", 0) < managed_end
        and merge.get("endColumnIndex", 0) > managed_start
    )


def _plan_v3_structure_changes(
    layout: dict[str, Any], spreadsheet: dict[str, Any]
) -> list[dict[str, Any]]:
    sheet = _find_sheet(spreadsheet, layout["sheet"]["sheet_id"])
    changes: list[dict[str, Any]] = []

    desired = desired_tables(layout)
    current = {table["name"]: table for table in sheet.get("tables", [])}
    for name, table in current.items():
        if name not in desired:
            changes.append(
                {
                    "action": "delete_table",
                    "target": name,
                    "table_id": table["tableId"],
                }
            )
    for name, expected in desired.items():
        table = current.get(name)
        if table is None:
            changes.append(
                {
                    "action": "create_table",
                    "target": name,
                    "block_id": expected["block_id"],
                    "after": expected,
                }
            )
            continue
        if _range_key(table["range"]) != _range_key(expected["range"]):
            changes.append(
                {
                    "action": "delete_table",
                    "target": name,
                    "block_id": expected["block_id"],
                    "table_id": table["tableId"],
                }
            )
            changes.append(
                {
                    "action": "create_table",
                    "target": name,
                    "block_id": expected["block_id"],
                    "after": expected,
                }
            )
            continue
        if not _colors_match(table.get("rowsProperties", {}), expected["rowsProperties"]):
            changes.append(
                {
                    "action": "style_table",
                    "target": name,
                    "block_id": expected["block_id"],
                    "table_id": table["tableId"],
                    "after": expected,
                }
            )

    desired_merges = {_range_key(item): item for item in _v3_title_merges(layout)}
    current_merges = {
        _range_key(item): item
        for item in sheet.get("merges", [])
        if _managed_merge(item, layout)
    }
    for key, merge in current_merges.items():
        if key not in desired_merges:
            changes.append(
                {"action": "unmerge", "target": f"row:{key[1] + 1}", "range": merge}
            )
    for key, merge in desired_merges.items():
        if key not in current_merges:
            changes.append(
                {"action": "merge_title", "target": f"row:{key[1] + 1}", "range": merge}
            )

    desired_named = _v3_named_ranges(layout)
    current_named = {
        item["name"]: item
        for item in spreadsheet.get("namedRanges", [])
        if item.get("name", "").startswith("Mercado_")
    }
    for name, item in current_named.items():
        if name not in desired_named:
            changes.append(
                {
                    "action": "delete_named_range",
                    "target": name,
                    "named_range_id": item["namedRangeId"],
                }
            )
    for name, expected in desired_named.items():
        current = current_named.get(name)
        if current is None:
            changes.append(
                {"action": "add_named_range", "target": name, "range": expected}
            )
        elif _range_key(current["range"]) != _range_key(expected):
            changes.append(
                {
                    "action": "update_named_range",
                    "target": name,
                    "named_range_id": current["namedRangeId"],
                    "range": expected,
                }
            )
    return changes


def _group_lookup(layout: dict[str, Any]) -> dict[str, tuple[int, dict[str, Any]]]:
    return {
        ticker: (index, group)
        for index, group in enumerate(layout["groups"], start=1)
        for ticker in group["tickers"]
    }


def _ticker_formula(layout: dict[str, Any], ticker: str) -> dict[str, Any]:
    url = layout["links"]["ticker"].format(ticker=ticker)
    template = layout["table_template"]
    return {
        "userEnteredValue": {
            "formulaValue": f'=HYPERLINK("{url}";"{ticker}")'
        },
        "userEnteredFormat": {
            "textFormat": {
                "fontFamily": template["font_family"],
                "fontSize": template["font_size"],
                "foregroundColorStyle": {"rgbColor": _rgb("#0B6E75")},
                "underline": True,
            }
        },
    }


def _title_and_header_requests(
    *,
    layout: dict[str, Any],
    title: str,
    title_row: int,
    header_row: int,
    start_column: str,
    end_column: str,
    headers: list[str],
    palette: dict[str, str],
) -> list[dict[str, Any]]:
    sheet_id = layout["sheet"]["sheet_id"]
    template = layout["table_template"]
    start = column_to_index(start_column)
    end = column_to_index(end_column) + 1
    title_format = {
        "backgroundColorStyle": {"rgbColor": _rgb(palette["title_background"])},
        "horizontalAlignment": "CENTER",
        "verticalAlignment": "MIDDLE",
        "textFormat": {
            "fontFamily": template["font_family"],
            "fontSize": template["font_size"],
            "bold": True,
            "foregroundColorStyle": {"rgbColor": _rgb(palette["title_text"])},
        },
    }
    header_format = {
        "backgroundColorStyle": {"rgbColor": _rgb(palette["header"])},
        "horizontalAlignment": "CENTER",
        "verticalAlignment": "MIDDLE",
        "wrapStrategy": "CLIP",
        "textFormat": {
            "fontFamily": template["font_family"],
            "fontSize": template["font_size"],
            "bold": True,
            "foregroundColorStyle": {"rgbColor": _rgb("#FFFFFF")},
        },
    }
    return [
        {
            "updateCells": {
                "start": {
                    "sheetId": sheet_id,
                    "rowIndex": title_row - 1,
                    "columnIndex": start,
                },
                "rows": [
                    {
                        "values": [
                            {
                                "userEnteredValue": {"stringValue": title},
                                "userEnteredFormat": title_format,
                            }
                        ]
                    }
                ],
                "fields": "userEnteredValue,userEnteredFormat",
            }
        },
        {
            "updateCells": {
                "range": {
                    "sheetId": sheet_id,
                    "startRowIndex": header_row - 1,
                    "endRowIndex": header_row,
                    "startColumnIndex": start,
                    "endColumnIndex": start + len(headers),
                },
                "rows": [
                    {
                        "values": [
                            {
                                "userEnteredValue": {"stringValue": header},
                                "userEnteredFormat": header_format,
                                **(
                                    {"note": layout["notes"]["drawdown_header"]}
                                    if header == "DD6M"
                                    else {}
                                ),
                            }
                            for header in headers
                        ]
                    }
                ],
                "fields": "userEnteredValue,note,userEnteredFormat",
            }
        },
        {
            "repeatCell": {
                "range": {
                    "sheetId": sheet_id,
                    "startRowIndex": header_row,
                    "endRowIndex": header_row + 1,
                    "startColumnIndex": start,
                    "endColumnIndex": end,
                },
                "cell": {
                    "userEnteredFormat": {
                        "backgroundColorStyle": {"rgbColor": _rgb("#FFFFFF")},
                        "horizontalAlignment": "CENTER",
                        "verticalAlignment": "MIDDLE",
                        "textFormat": {
                            "fontFamily": template["font_family"],
                            "fontSize": template["font_size"],
                        },
                    }
                },
                "fields": "userEnteredFormat",
            }
        },
    ]


def build_table_font_apply_requests(
    sheet_id: int, layout: dict[str, Any]
) -> list[dict[str, Any]]:
    template = layout["table_template"]
    ranges = [
        {
            "sheetId": sheet_id,
            "startRowIndex": block["title_row"] - 1,
            "endRowIndex": block["header_row"] + len(block["tickers"]),
            "startColumnIndex": column_to_index(block["start_column"]),
            "endColumnIndex": column_to_index(block["end_column"]) + 1,
        }
        for block in layout["blocks"]
    ]
    summary = layout["summary_table"]
    ranges.append(
        {
            "sheetId": sheet_id,
            "startRowIndex": summary["title_row"] - 1,
            "endRowIndex": summary["header_row"] + len(layout["groups"]),
            "startColumnIndex": column_to_index(summary["start_column"]),
            "endColumnIndex": column_to_index(summary["end_column"]) + 1,
        }
    )
    return [
        {
            "repeatCell": {
                "range": grid_range,
                "cell": {
                    "userEnteredFormat": {
                        "textFormat": {
                            "fontFamily": template["font_family"],
                            "fontSize": template["font_size"],
                        }
                    }
                },
                "fields": (
                    "userEnteredFormat.textFormat.fontFamily,"
                    "userEnteredFormat.textFormat.fontSize"
                ),
            }
        }
        for grid_range in ranges
    ]


def build_panel_font_apply_requests(
    sheet_id: int, layout: dict[str, Any]
) -> list[dict[str, Any]]:
    panel = layout["general_panel"]
    control_row = int(
        "".join(
            character
            for character in layout["global_sort"]["control_cell"]
            if character.isdigit()
        )
    )
    column = column_to_index(panel["column"])
    return [
        {
            "repeatCell": {
                "range": {
                    "sheetId": sheet_id,
                    "startRowIndex": panel["start_row"] - 1,
                    "endRowIndex": control_row,
                    "startColumnIndex": column,
                    "endColumnIndex": column + 1,
                },
                "cell": {
                    "userEnteredFormat": {
                        "textFormat": {
                            "fontFamily": panel["font_family"],
                            "fontSize": panel["font_size"],
                        }
                    }
                },
                "fields": (
                    "userEnteredFormat.textFormat.fontFamily,"
                    "userEnteredFormat.textFormat.fontSize"
                ),
            }
        }
    ]


def _ticker_table_content_requests(
    layout: dict[str, Any],
    block: dict[str, Any],
    *,
    tickers: list[str] | None = None,
) -> list[dict[str, Any]]:
    sheet_id = layout["sheet"]["sheet_id"]
    start = column_to_index(block["start_column"])
    end = column_to_index(block["end_column"]) + 1
    first_row = block["header_row"]
    lookup = _group_lookup(layout)
    requests = _title_and_header_requests(
        layout=layout,
        title=block["title"],
        title_row=block["title_row"],
        header_row=block["header_row"],
        start_column=block["start_column"],
        end_column=block["end_column"],
        headers=layout["table_template"]["headers"],
        palette=block["palette"],
    )
    if layout.get("native_tables"):
        requests = requests[1:]
    requests[-1]["repeatCell"]["range"]["endRowIndex"] = first_row + len(block["tickers"])

    rows = []
    for ticker in tickers or block["tickers"]:
        _, group = lookup[ticker]
        group_cell = {
            "userEnteredValue": {"numberValue": 0},
            "userEnteredFormat": {
                "backgroundColorStyle": {"rgbColor": _rgb(group["background"])},
            },
        }
        rows.append({"values": [group_cell, _ticker_formula(layout, ticker)]})
    requests.append(
        {
            "updateCells": {
                "range": {
                    "sheetId": sheet_id,
                    "startRowIndex": first_row,
                    "endRowIndex": first_row + len(rows),
                    "startColumnIndex": start,
                    "endColumnIndex": start + 2,
                },
                "rows": rows,
                "fields": "userEnteredValue,userEnteredFormat",
            }
        }
    )
    return requests


def _summary_content_requests(layout: dict[str, Any]) -> list[dict[str, Any]]:
    summary = layout["summary_table"]
    sheet_id = layout["sheet"]["sheet_id"]
    start = column_to_index(summary["start_column"])
    requests = _title_and_header_requests(
        layout=layout,
        title=summary["title"],
        title_row=summary["title_row"],
        header_row=summary["header_row"],
        start_column=summary["start_column"],
        end_column=summary["title_end_column"],
        headers=summary["headers"],
        palette=summary["palette"],
    )
    requests[-1]["repeatCell"]["range"]["endRowIndex"] = (
        summary["header_row"] + len(layout["groups"])
    )
    rows = []
    for group in layout["groups"]:
        etf = group["benchmark"]
        url = layout["links"]["ticker"].format(ticker=etf)
        group_format = {
            "backgroundColorStyle": {"rgbColor": _rgb(group["background"])},
            "textFormat": {
                "foregroundColorStyle": {"rgbColor": _rgb(group["text"])},
                "bold": True,
            },
        }
        rows.append(
            {
                "values": [
                    {
                        "userEnteredValue": {
                            "stringValue": f"{group['sector']} / {group['label']}"
                        },
                    },
                    {
                        "userEnteredFormat": group_format,
                    },
                    {
                        "userEnteredValue": {
                            "formulaValue": f'=HYPERLINK("{url}";"{etf}")'
                        }
                    },
                ]
            }
        )
    requests.append(
        {
            "updateCells": {
                "range": {
                    "sheetId": sheet_id,
                    "startRowIndex": summary["header_row"],
                    "endRowIndex": summary["header_row"] + len(rows),
                    "startColumnIndex": start,
                    "endColumnIndex": start + 3,
                },
                "rows": rows,
                "fields": "userEnteredValue,userEnteredFormat",
            }
        }
    )
    return requests


def plan_structure_changes(
    layout: dict[str, Any], spreadsheet: dict[str, Any]
) -> list[dict[str, Any]]:
    if layout.get("schema_version", 1) >= 3:
        return _plan_v3_structure_changes(layout, spreadsheet)
    return _plan_legacy_structure_changes(layout, spreadsheet)


def build_structure_requests(
    layout: dict[str, Any], changes: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    if layout.get("schema_version", 1) < 3:
        return _build_legacy_structure_requests(layout, changes)
    if not changes:
        return []

    sheet_id = layout["sheet"]["sheet_id"]
    requests: list[dict[str, Any]] = [
        {
            "updateSheetProperties": {
                "properties": {
                    "sheetId": sheet_id,
                    "gridProperties": {
                        "rowCount": layout["sheet"]["row_count"],
                        "columnCount": max(layout["sheet"]["column_count"], 39),
                    },
                },
                "fields": "gridProperties(rowCount,columnCount)",
            }
        }
    ]
    requests.extend(
        {"unmergeCells": {"range": change["range"]}}
        for change in changes
        if change["action"] == "unmerge"
    )
    requests.extend(
        {"deleteTable": {"tableId": change["table_id"]}}
        for change in changes
        if change["action"] == "delete_table"
    )
    requests.append(
        {
            "updateCells": {
                "range": {
                    "sheetId": sheet_id,
                    "startRowIndex": 1,
                    "endRowIndex": layout["sheet"]["row_count"],
                    "startColumnIndex": min(
                        column_to_index(layout["general_panel"]["column"]),
                        column_to_index(layout["summary_table"]["start_column"]),
                        *(column_to_index(block["start_column"]) for block in layout["blocks"]),
                    ),
                    "endColumnIndex": max(layout["sheet"]["column_count"], 39),
                },
                "fields": "userEnteredValue,note,textFormatRuns,dataValidation,userEnteredFormat",
            }
        }
    )
    for change in changes:
        if change["action"] == "delete_named_range":
            requests.append(
                {"deleteNamedRange": {"namedRangeId": change["named_range_id"]}}
            )
        elif change["action"] == "update_named_range":
            requests.append(
                {
                    "updateNamedRange": {
                        "namedRange": {
                            "namedRangeId": change["named_range_id"],
                            "name": change["target"],
                            "range": change["range"],
                        },
                        "fields": "name,range",
                    }
                }
            )
        elif change["action"] == "add_named_range":
            requests.append(
                {
                    "addNamedRange": {
                        "namedRange": {"name": change["target"], "range": change["range"]}
                    }
                }
            )
    requests.extend(
        {
            "mergeCells": {
                "range": change["range"],
                "mergeType": "MERGE_ALL",
            }
        }
        for change in changes
        if change["action"] == "merge_title"
    )
    for block in layout["blocks"]:
        requests.extend(_ticker_table_content_requests(layout, block))
    requests.extend(_summary_content_requests(layout))
    for change in changes:
        if change["action"] == "create_table":
            requests.append(
                {
                    "addTable": {
                        "table": {
                            "name": change["target"],
                            "range": change["after"]["range"],
                            "rowsProperties": change["after"]["rowsProperties"],
                        }
                    }
                }
            )
        elif change["action"] == "move_table":
            requests.append(
                {
                    "updateTable": {
                        "table": {
                            "tableId": change["table_id"],
                            "range": change["after"]["range"],
                        },
                        "fields": "range",
                    }
                }
            )
        elif change["action"] == "style_table":
            requests.append(
                {
                    "updateTable": {
                        "table": {
                            "tableId": change["table_id"],
                            "rowsProperties": change["after"]["rowsProperties"],
                        },
                        "fields": "rowsProperties",
                    }
                }
            )
    requests.extend(build_dimension_apply_requests(sheet_id, layout))
    requests.extend(build_alignment_apply_requests(sheet_id, layout))
    requests.extend(build_table_border_apply_requests(sheet_id, layout))
    requests.extend(build_table_font_apply_requests(sheet_id, layout))
    requests.extend(build_panel_font_apply_requests(sheet_id, layout))
    requests.extend(
        build_global_sort_control_requests(
            layout, layout["global_sort"]["default"]
        )
    )
    return requests
