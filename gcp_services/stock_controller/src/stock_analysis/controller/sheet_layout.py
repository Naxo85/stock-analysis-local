from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any


def _rgb(hex_color: str) -> dict[str, float]:
    value = hex_color.removeprefix("#")
    return {
        "red": int(value[0:2], 16) / 255,
        "green": int(value[2:4], 16) / 255,
        "blue": int(value[4:6], 16) / 255,
    }


DEFAULT_ROOT = Path(
    os.environ.get("STOCK_ANALYSIS_ROOT", Path(__file__).resolve().parents[3])
)
DEFAULT_LAYOUT_PATH = DEFAULT_ROOT / "config" / "market_sheet_layout.json"
DEFAULT_RUNTIME_LAYOUT_OBJECT = "runtime/config/market_sheet_layout.json"


def _load_layout_payload(path: Path | None) -> dict[str, Any]:
    if path is not None:
        with path.open(encoding="utf-8") as source:
            return json.load(source)

    bucket_name = os.environ.get("MARKET_LAYOUT_BUCKET") or os.environ.get(
        "MARKET_HISTORY_BUCKET"
    )
    runtime_enabled = os.environ.get("MARKET_RUNTIME_LAYOUT", "1") != "0"
    if bucket_name and runtime_enabled:
        from google.api_core.exceptions import NotFound
        from google.cloud import storage

        object_name = os.environ.get(
            "MARKET_LAYOUT_OBJECT", DEFAULT_RUNTIME_LAYOUT_OBJECT
        )
        try:
            payload = (
                storage.Client()
                .bucket(bucket_name)
                .blob(object_name)
                .download_as_bytes()
            )
        except NotFound:
            pass
        else:
            return json.loads(payload.decode("utf-8"))

    with DEFAULT_LAYOUT_PATH.open(encoding="utf-8") as source:
        return json.load(source)


def column_to_index(column: str) -> int:
    """Convert an A1 column label to a zero-based index."""
    normalized = column.strip().upper()
    if not normalized or not normalized.isalpha():
        raise ValueError(f"Invalid column label: {column!r}")

    value = 0
    for character in normalized:
        value = value * 26 + ord(character) - ord("A") + 1
    return value - 1


def index_to_column(index: int) -> str:
    """Convert a zero-based column index to an A1 column label."""
    if index < 0:
        raise ValueError(f"Column index must be non-negative: {index}")

    result = ""
    value = index + 1
    while value:
        value, remainder = divmod(value - 1, 26)
        result = chr(ord("A") + remainder) + result
    return result


def a1_row(cell: str) -> int:
    """Return the one-based row from a single-cell A1 reference."""
    match = re.fullmatch(r"[A-Za-z]+([1-9]\d*)", cell.strip())
    if not match:
        raise ValueError(f"Invalid A1 cell reference: {cell!r}")
    return int(match.group(1))


def load_market_sheet_layout(path: Path | None = None) -> dict[str, Any]:
    layout = _load_layout_payload(path)
    if layout.get("schema_version", 1) < 3:
        resolve_block_geometry(layout)
    else:
        resolve_balanced_table_geometry(layout)
    validate_market_sheet_layout(layout)
    return layout


def resolve_balanced_table_geometry(layout: dict[str, Any]) -> dict[str, Any]:
    """Derive balanced table membership and vertical geometry from the groups."""
    blocks = layout["blocks"]
    if len(blocks) != 2:
        raise ValueError("Mercado global sorting requires exactly two ticker tables")
    universe = [
        ticker for group in layout["groups"] for ticker in group["tickers"]
    ]
    base, remainder = divmod(len(universe), len(blocks))
    counts = [base + (1 if index < remainder else 0) for index in range(len(blocks))]
    cursor = 0
    for block, count in zip(blocks, counts, strict=True):
        block["tickers"] = universe[cursor : cursor + count]
        cursor += count

    last_body_row = max(
        block["header_row"] + len(block["tickers"])
        for block in blocks
    )
    summary = layout["summary_table"]
    placement = summary.get("placement")
    if placement:
        if placement.get("below") != "global_sort":
            raise ValueError("Summary placement currently supports only global_sort")
        gap_rows = int(placement.get("gap_rows", 0))
        summary["title_row"] = (
            a1_row(layout["global_sort"]["control_cell"]) + gap_rows + 1
        )
        layout["sheet"]["spacer_rows"] = []
    else:
        layout["sheet"]["spacer_rows"] = [last_body_row + 1, last_body_row + 2]
        summary["title_row"] = last_body_row + 3
    summary["header_row"] = summary["title_row"] + 1
    layout["sheet"]["row_count"] = max(
        last_body_row,
        summary["header_row"] + len(layout["groups"]),
    )
    return layout


def resolve_block_geometry(layout: dict[str, Any]) -> dict[str, Any]:
    """Pack each table lane from top to bottom using declared lane order."""
    if "vertical_layout" not in layout:
        return layout
    vertical = layout["vertical_layout"]
    start_row = vertical["first_benchmark_row"]
    gap_rows = vertical["gap_rows"]
    benchmark_offset = layout["table_template"]["benchmark_start_column_offset"]
    lanes: dict[tuple[str, str], list[dict[str, Any]]] = {}

    for block in layout["blocks"]:
        lanes.setdefault(
            (block["start_column"], block["end_column"]), []
        ).append(block)

    for lane_blocks in lanes.values():
        ordered = sorted(lane_blocks, key=lambda item: item["lane_order"])
        expected_orders = list(range(1, len(ordered) + 1))
        actual_orders = [block["lane_order"] for block in ordered]
        if actual_orders != expected_orders:
            raise ValueError(
                f"Lane order must be contiguous: expected={expected_orders}, "
                f"actual={actual_orders}"
            )

        benchmark_row = start_row
        for block in ordered:
            block["benchmark_row"] = benchmark_row
            block["header_row"] = benchmark_row + 1
            benchmark_start = index_to_column(
                column_to_index(block["start_column"]) + benchmark_offset
            )
            block["benchmark"]["range"] = (
                f"{benchmark_start}{benchmark_row}:"
                f"{block['end_column']}{benchmark_row}"
            )
            benchmark_row = (
                block["header_row"] + len(block["tickers"]) + gap_rows + 1
            )

    return layout


def desired_column_widths(layout: dict[str, Any]) -> dict[str, int]:
    widths: dict[str, int] = {}

    for reserved in layout["reserved_columns"]:
        widths[reserved["column"]] = reserved["width_px"]

    panel = layout["general_panel"]
    widths[panel["column"]] = panel["width_px"]

    template_widths = layout["table_template"]["column_widths_px"]
    for block in layout["blocks"]:
        start = column_to_index(block["start_column"])
        end = column_to_index(block["end_column"])
        for offset, width in enumerate(template_widths):
            column_index = start + offset
            if column_index > end:
                raise ValueError(f"Block {block['id']} is narrower than the table template")
            widths[index_to_column(column_index)] = width

    for helper in layout.get("helper_columns", []):
        widths[helper["column"]] = helper["width_px"]

    for spacer in layout["spacer_columns"]:
        widths[spacer["column"]] = spacer["width_px"]

    return dict(sorted(widths.items(), key=lambda item: column_to_index(item[0])))


def desired_sheet_state(layout: dict[str, Any]) -> dict[str, Any]:
    sheet = layout["sheet"]
    template = layout["table_template"]
    row_heights = {
        str(row): sheet["default_row_height_px"]
        for row in range(1, sheet["row_count"] + 1)
    }
    top_spacer = sheet["top_spacer"]
    row_heights[str(top_spacer["row"])] = top_spacer["height_px"]
    for row in sheet["spacer_rows"]:
        row_heights[str(row)] = template["vertical_spacer_height_px"]
    if layout.get("schema_version", 1) >= 3:
        for block in layout["blocks"]:
            row_heights[str(block["title_row"])] = template["title_row_height_px"]
            row_heights[str(block["header_row"])] = template["header_row_height_px"]
            for row in range(
                block["header_row"] + 1,
                block["header_row"] + 1 + len(block["tickers"]),
            ):
                row_heights[str(row)] = template["body_row_height_px"]
        summary = layout["summary_table"]
        row_heights[str(summary["title_row"])] = template["title_row_height_px"]
        row_heights[str(summary["header_row"])] = template["header_row_height_px"]
        for row in range(
            summary["header_row"] + 1,
            summary["header_row"] + 1 + len(layout["groups"]),
        ):
            row_heights[str(row)] = template["body_row_height_px"]
    else:
        for block in layout["blocks"]:
            row_heights[str(block["benchmark_row"])] = template["benchmark_row_height_px"]
            row_heights[str(block["header_row"])] = template["header_row_height_px"]
            for row in range(
                block["header_row"] + 1,
                block["header_row"] + 1 + len(block["tickers"]),
            ):
                row_heights[str(row)] = template["body_row_height_px"]
    return {
        "row_count": sheet["row_count"],
        "column_count": sheet["column_count"],
        "hide_gridlines": sheet["hide_gridlines"],
        "frozen_row_count": sheet["frozen_row_count"],
        "column_widths_px": desired_column_widths(layout),
        "row_heights_px": row_heights,
        "hidden_columns": {
            item["column"]: bool(item.get("hidden"))
            for item in layout.get("helper_columns", [])
        },
    }


def plan_layout_changes(
    current_state: dict[str, Any], layout: dict[str, Any]
) -> list[dict[str, Any]]:
    """Return Terraform-style drift entries without modifying the sheet."""
    desired = desired_sheet_state(layout)
    changes: list[dict[str, Any]] = []

    for key in ("row_count", "column_count", "hide_gridlines", "frozen_row_count"):
        if current_state.get(key) != desired[key]:
            changes.append(
                {"target": f"sheet.{key}", "before": current_state.get(key), "after": desired[key]}
            )

    for section in ("column_widths_px", "row_heights_px"):
        current_values = current_state.get(section, {})
        for key, desired_value in desired[section].items():
            if current_values.get(key) != desired_value:
                changes.append(
                    {
                        "target": f"{section}.{key}",
                        "before": current_values.get(key),
                        "after": desired_value,
                    }
                )

    current_hidden = current_state.get("hidden_columns", {})
    for column, desired_value in desired["hidden_columns"].items():
        if current_hidden.get(column) != desired_value:
            changes.append(
                {
                    "target": f"hidden_columns.{column}",
                    "before": current_hidden.get(column),
                    "after": desired_value,
                }
            )

    return changes


def build_dimension_apply_requests(
    sheet_id: int, layout: dict[str, Any]
) -> list[dict[str, Any]]:
    """Build idempotent Sheets batchUpdate requests for dimensions and grid properties."""
    desired = desired_sheet_state(layout)
    requests: list[dict[str, Any]] = [
        {
            "updateSheetProperties": {
                "properties": {
                    "sheetId": sheet_id,
                    "gridProperties": {
                        "rowCount": desired["row_count"],
                        "columnCount": desired["column_count"],
                        "frozenRowCount": desired["frozen_row_count"],
                        "hideGridlines": desired["hide_gridlines"],
                    },
                },
                "fields": (
                    "gridProperties(rowCount,columnCount,frozenRowCount,hideGridlines)"
                ),
            }
        }
    ]

    requests.extend(build_column_width_apply_requests(sheet_id, layout))

    for row, height in desired["row_heights_px"].items():
        index = int(row) - 1
        requests.append(
            {
                "updateDimensionProperties": {
                    "range": {
                        "sheetId": sheet_id,
                        "dimension": "ROWS",
                        "startIndex": index,
                        "endIndex": index + 1,
                    },
                    "properties": {"pixelSize": height},
                    "fields": "pixelSize",
                }
            }
        )

    return requests


def build_column_width_apply_requests(
    sheet_id: int, layout: dict[str, Any]
) -> list[dict[str, Any]]:
    """Build the final width reconciliation for every Mercado column."""
    requests = []
    hidden = {
        item["column"]: bool(item.get("hidden"))
        for item in layout.get("helper_columns", [])
    }
    if not layout['table_template'].get('show_resistance', True):
        for block in layout['blocks']:
            retired = column_to_index(block['start_column']) + layout['table_template'].get('analysis_start_column_offset', 9) + 2
            hidden[index_to_column(retired)] = True
    for column, width in desired_column_widths(layout).items():
        index = column_to_index(column)
        properties = {"pixelSize": width}
        fields = "pixelSize"
        if column in hidden:
            properties["hiddenByUser"] = hidden[column]
            fields += ",hiddenByUser"
        requests.append(
            {
                "updateDimensionProperties": {
                    "range": {
                        "sheetId": sheet_id,
                        "dimension": "COLUMNS",
                        "startIndex": index,
                        "endIndex": index + 1,
                    },
                    "properties": properties,
                    "fields": fields,
                }
            }
        )
    return requests


def build_alignment_apply_requests(
    sheet_id: int, layout: dict[str, Any]
) -> list[dict[str, Any]]:
    """Center every visible cell in each market block."""
    requests = []
    alignment = layout["table_template"]["body_alignment"]["horizontal"]
    if layout.get("schema_version", 1) >= 3:
        ranges = [
            {
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
                "startRowIndex": summary["title_row"] - 1,
                "endRowIndex": summary["header_row"] + len(layout["groups"]),
                "startColumnIndex": column_to_index(summary["start_column"]),
                "endColumnIndex": column_to_index(summary["title_end_column"]) + 1,
            }
        )
        for grid_range in ranges:
            grid_range["sheetId"] = sheet_id
            requests.append(
                {
                    "repeatCell": {
                        "range": grid_range,
                        "cell": {
                            "userEnteredFormat": {
                                "horizontalAlignment": alignment,
                            }
                        },
                        "fields": "userEnteredFormat.horizontalAlignment",
                    }
                }
            )
        return requests
    for block in layout["blocks"]:
        requests.append(
            {
                "repeatCell": {
                    "range": {
                        "sheetId": sheet_id,
                        "startRowIndex": block["benchmark_row"] - 1,
                        "endRowIndex": block["header_row"] + len(block["tickers"]),
                        "startColumnIndex": column_to_index(block["start_column"]),
                        "endColumnIndex": column_to_index(block["end_column"]) + 1,
                    },
                    "cell": {
                        "userEnteredFormat": {
                            "horizontalAlignment": alignment,
                        }
                    },
                    "fields": "userEnteredFormat.horizontalAlignment",
                }
            }
        )
    return requests


def build_table_border_apply_requests(
    sheet_id: int, layout: dict[str, Any]
) -> list[dict[str, Any]]:
    """Restore table outlines and the visual separators between metric families."""
    if layout.get("schema_version", 1) < 3:
        return []

    line = {
        "style": "SOLID_MEDIUM",
        "colorStyle": {"rgbColor": _rgb("#5F6B73")},
    }
    requests: list[dict[str, Any]] = []
    divider_offsets = layout["table_template"].get("divider_after_offsets", [])
    for block in layout["blocks"]:
        start = column_to_index(block["start_column"])
        end = column_to_index(block["end_column"]) + 1
        grid_range = {
            "sheetId": sheet_id,
            "startRowIndex": block["header_row"] - 1,
            "endRowIndex": block["header_row"] + len(block["tickers"]),
            "startColumnIndex": start,
            "endColumnIndex": end,
        }
        requests.append(
            {
                "updateBorders": {
                    # Include the header row so a newly-created Sheets table
                    # cannot retain its automatic separator above the first
                    # ticker row. The following request restores only the
                    # declared outer outline and metric-family dividers.
                    "range": grid_range,
                    "innerHorizontal": {"style": "NONE"},
                    "innerVertical": {"style": "NONE"},
                }
            }
        )
        requests.append(
            {
                "updateBorders": {
                    "range": grid_range,
                    "top": line,
                    "bottom": line,
                    "left": line,
                    "right": line,
                }
            }
        )
        for offset in divider_offsets:
            requests.append(
                {
                    "updateBorders": {
                        "range": {
                            **grid_range,
                            "startColumnIndex": start + offset,
                            "endColumnIndex": start + offset + 1,
                        },
                        "right": line,
                    }
                }
            )

    summary = layout["summary_table"]
    requests.append(
        {
            "updateBorders": {
                "range": {
                    "sheetId": sheet_id,
                    "startRowIndex": summary["header_row"] - 1,
                    "endRowIndex": summary["header_row"] + len(layout["groups"]),
                    "startColumnIndex": column_to_index(summary["start_column"]),
                    "endColumnIndex": column_to_index(summary["end_column"]) + 1,
                },
                "top": line,
                "bottom": line,
                "left": line,
                "right": line,
            }
        }
    )
    return requests


def drawdown_presentation(
    percentile: int, layout: dict[str, Any]
) -> dict[str, str | None]:
    background = None
    for rule in layout["format_rules"]["drawdown_percentile"]:
        if rule["operator"] != ">=":
            raise ValueError("Drawdown percentile rules currently support only >=")
        if percentile >= rule["value"]:
            background = rule["background"]
            break

    return {"background": background, "note": ""}


def _validate_v3_layout(layout: dict[str, Any]) -> None:
    sheet = layout["sheet"]
    template = layout["table_template"]
    if len(template["headers"]) != len(template["column_widths_px"]):
        raise ValueError("Every ticker header must have exactly one configured width")
    expected_width = 38 if "Setup" in template["headers"] else 36
    if sheet["column_count"] != expected_width:
        raise ValueError(f"Mercado must have {expected_width} columns")
    if sheet["top_spacer"]["row"] != 1:
        raise ValueError("Mercado must keep row 1 as its top spacer")
    panel = layout["general_panel"]
    if panel["column"] != "A" or panel["row_count"] != len(panel["lines"]):
        raise ValueError("The general market panel must occupy declared A lines")
    global_sort = layout["global_sort"]
    option_fields = [option["field"] for option in global_sort["options"]]
    expected_fields = ["score", "setup_score", "group", "strength"] if "Setup" in template["headers"] else ["score", "group", "strength"]
    if option_fields != expected_fields:
        raise ValueError("Global sort must expose score, group and strength")
    if global_sort["default"] not in {
        option["label"] for option in global_sort["options"]
    }:
        raise ValueError("Global sort default must be one of its options")

    ticker_membership: list[str] = []
    for block in layout["blocks"]:
        width = (
            column_to_index(block["end_column"])
            - column_to_index(block["start_column"])
            + 1
        )
        if width != len(template["headers"]):
            raise ValueError(f"Block {block['id']} does not match the ticker template")
        if block["header_row"] + len(block["tickers"]) > sheet["row_count"]:
            raise ValueError(f"Block {block['id']} exceeds the configured sheet height")
        ticker_membership.extend(block["tickers"])
    if len(ticker_membership) != len(set(ticker_membership)):
        raise ValueError("A ticker cannot appear in both market tables")
    table_sizes = [len(block["tickers"]) for block in layout["blocks"]]
    if max(table_sizes) - min(table_sizes) > 1 or table_sizes[0] < table_sizes[1]:
        raise ValueError("Market tables must be balanced, with any extra ticker on the left")

    grouped = [ticker for group in layout["groups"] for ticker in group["tickers"]]
    if len(grouped) != len(set(grouped)):
        raise ValueError("Every ticker must belong to exactly one group")
    if set(grouped) != set(ticker_membership):
        raise ValueError("Ticker tables and group universe must match exactly")

    summary = layout["summary_table"]
    summary_start = column_to_index(summary["start_column"])
    summary_end = column_to_index(summary["end_column"])
    for cell_name in (global_sort["label_cell"], global_sort["control_cell"]):
        match = re.fullmatch(r"([A-Za-z]+)[1-9]\d*", cell_name.strip())
        if not match:
            raise ValueError(f"Invalid global sort cell: {cell_name!r}")
        cell_column = column_to_index(match.group(1))
        if not summary_start <= cell_column <= summary_end:
            raise ValueError("The global sort control must remain in the left panel")
    summary_width = (
        column_to_index(summary["end_column"])
        - column_to_index(summary["start_column"])
        + 1
    )
    if summary_width != len(summary["headers"]):
        raise ValueError("Summary headers must match its visible width")
    for block in layout["blocks"]:
        block_start = column_to_index(block["start_column"])
        block_end = column_to_index(block["end_column"])
        shares_columns = not (summary_end < block_start or summary_start > block_end)
        block_end_row = block["header_row"] + len(block["tickers"])
        if shares_columns and summary["title_row"] - block_end_row < 3:
            raise ValueError(
                "Overlapping table lanes need two blank rows before the summary"
            )

    expected_columns = {
        index_to_column(index) for index in range(sheet["column_count"])
    }
    actual_columns = set(desired_column_widths(layout))
    if actual_columns != expected_columns:
        missing = sorted(expected_columns - actual_columns, key=column_to_index)
        extra = sorted(actual_columns - expected_columns, key=column_to_index)
        raise ValueError(
            f"Column layout must cover the declared width exactly; missing={missing}, extra={extra}"
        )


def validate_market_sheet_layout(layout: dict[str, Any]) -> None:
    if layout.get("schema_version", 1) >= 3:
        _validate_v3_layout(layout)
        return
    sheet = layout["sheet"]
    template = layout["table_template"]
    headers = template["headers"]
    widths = template["column_widths_px"]

    if len(headers) != len(widths):
        raise ValueError("Every table header must have exactly one configured width")
    if sheet["column_count"] != 39:
        raise ValueError("Mercado must end at AM (39 columns)")
    if sheet["top_spacer"]["row"] != 1:
        raise ValueError("Mercado must keep row 1 as its top spacer")
    panel = layout["general_panel"]
    if panel["column"] != "B":
        raise ValueError("The general market panel must remain in reserved column B")
    if panel["start_row"] != 2 or panel["row_count"] != len(panel["lines"]):
        raise ValueError("The general market panel must declare every B2:B9 line")
    if panel["start_row"] + panel["row_count"] - 1 > sheet["row_count"]:
        raise ValueError("The general market panel exceeds the configured sheet height")
    for section in ("benchmark_alignment", "header_alignment", "body_alignment"):
        if template[section]["horizontal"] != "CENTER":
            raise ValueError(f"{section} must keep Mercado horizontally centered")

    lanes: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for block in layout["blocks"]:
        block_width = (
            column_to_index(block["end_column"])
            - column_to_index(block["start_column"])
            + 1
        )
        if block_width != len(headers):
            raise ValueError(f"Block {block['id']} does not match the table template width")
        last_data_row = block["header_row"] + len(block["tickers"])
        if last_data_row > sheet["row_count"]:
            raise ValueError(f"Block {block['id']} exceeds the configured sheet height")
        lanes.setdefault(
            (block["start_column"], block["end_column"]), []
        ).append(block)

    for lane_blocks in lanes.values():
        ordered = sorted(lane_blocks, key=lambda item: item["benchmark_row"])
        for previous, following in zip(ordered, ordered[1:]):
            previous_last_row = previous["header_row"] + len(previous["tickers"])
            if following["benchmark_row"] <= previous_last_row + 1:
                raise ValueError(
                    f"Blocks {previous['id']} and {following['id']} need a blank row"
                )

    expected_columns = {index_to_column(index) for index in range(sheet["column_count"])}
    actual_columns = set(desired_column_widths(layout))
    if actual_columns != expected_columns:
        missing = sorted(expected_columns - actual_columns, key=column_to_index)
        duplicated_or_extra = sorted(actual_columns - expected_columns, key=column_to_index)
        raise ValueError(
            f"Column layout must cover A:AM exactly; missing={missing}, extra={duplicated_or_extra}"
        )
