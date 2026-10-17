from __future__ import annotations

from typing import Any

from stock_analysis.controller.global_sheet_sort import (
    build_global_sort_plan,
    global_sort_read_ranges,
)
from stock_analysis.controller.analysis_sheet import (
    SUPPORT_STRENGTH_BORDER_THRESHOLD,
)
from stock_analysis.controller.market_sheet import GoogleSheetsRestClient
from stock_analysis.controller.portfolio_sheet import load_positions
from stock_analysis.controller.sheet_layout import (
    column_to_index,
    desired_column_widths,
    index_to_column,
    load_market_sheet_layout,
)
from stock_analysis.controller.sheet_structure import desired_tables
from stock_analysis.controller.sheet_tickers import ticker_read_ranges


def _table_ranges(layout: dict[str, Any]) -> list[str]:
    sheet = layout["sheet"]["title"].replace("'", "''")
    return [
        (
            f"'{sheet}'!{block['start_column']}{block['header_row'] + 1}:"
            f"{block['end_column']}{block['header_row'] + len(block['tickers'])}"
        )
        for block in layout["blocks"]
    ]


def _score_ranges(layout: dict[str, Any]) -> list[str]:
    sheet = layout["sheet"]["title"].replace("'", "''")
    offset = layout["table_template"].get("analysis_start_column_offset", 9) + 3
    return [
        (
            f"'{sheet}'!{index_to_column(column_to_index(block['start_column']) + offset)}{block['header_row'] + 1}:"
            f"{index_to_column(column_to_index(block['start_column']) + offset)}{block['header_row'] + len(block['tickers'])}"
        )
        for block in layout["blocks"]
    ]


def _vol_dd6m_ranges(layout: dict[str, Any]) -> list[str]:
    sheet = layout["sheet"]["title"].replace("'", "''")
    headers = layout["table_template"]["headers"]
    vol_offset = headers.index("Vol")
    dd6m_offset = headers.index("DD6M")
    ranges = []
    for block in layout["blocks"]:
        vol_column = index_to_column(
            column_to_index(block["start_column"]) + vol_offset
        )
        dd6m_column = index_to_column(
            column_to_index(block["start_column"]) + dd6m_offset
        )
        ranges.append(
            f"'{sheet}'!{vol_column}{block['header_row']}:"
            f"{dd6m_column}{block['header_row'] + len(block['tickers'])}"
        )
    return ranges


def _score_links(payload: dict[str, Any]) -> list[str]:
    links = []
    for sheet in payload.get("sheets", []):
        for grid in sheet.get("data", []):
            for row in grid.get("rowData", []):
                values = row.get("values", [])
                if not values:
                    continue
                cell = values[0]
                runs = cell.get("textFormatRuns", [])
                if runs:
                    uri = runs[0].get("format", {}).get("link", {}).get("uri")
                    if uri:
                        links.append(uri)
                        continue
                for format_name in ("effectiveFormat", "userEnteredFormat"):
                    uri = (
                        cell.get(format_name, {})
                        .get("textFormat", {})
                        .get("link", {})
                        .get("uri")
                    )
                    if uri:
                        links.append(uri)
                        break
    return links


def main() -> None:
    layout = load_market_sheet_layout()
    client = GoogleSheetsRestClient(
        service_account=layout["spreadsheet"].get("service_account")
    )
    spreadsheet_id = layout["spreadsheet"]["spreadsheet_id"]

    ticker_ranges = client.batch_get_values(spreadsheet_id, ticker_read_ranges(layout))
    tickers = [
        str(row[0]).strip().upper()
        for value_range in ticker_ranges
        for row in value_range.get("values", [])
        if row
    ]
    expected = [
        ticker for block in layout["blocks"] for ticker in block["tickers"]
    ]
    if len(tickers) != len(expected) or set(tickers) != set(expected):
        raise RuntimeError("Live ticker universe does not match the manifest")

    sort_grid = client.get_spreadsheet(
        spreadsheet_id,
        include_grid_data=True,
        ranges=global_sort_read_ranges(layout),
    )
    sort_plan = build_global_sort_plan(layout, sort_grid)
    if len(sort_plan.ticker_rows) != len(expected):
        raise RuntimeError("Global sort does not cover the complete ticker universe")
    expected_font_size = layout["table_template"]["font_size"]
    analysis_offset = layout["table_template"].get(
        "analysis_start_column_offset", 9
    )
    blocks_by_name = {
        block["table_name"]: block for block in layout["blocks"]
    }
    table_by_ticker = getattr(sort_plan.ticker_rows, "table_by_ticker", {})
    expected_strength_frames: set[tuple[int, int]] = set()
    for ticker, strengths in sort_plan.support_strengths.items():
        block = blocks_by_name.get(table_by_ticker.get(ticker))
        row = sort_plan.ticker_rows.get(ticker)
        if block is None or row is None:
            continue
        first_analysis_column = (
            column_to_index(block["start_column"]) + analysis_offset
        )
        for offset, strength in enumerate(strengths):
            if (
                strength is not None
                and strength >= SUPPORT_STRENGTH_BORDER_THRESHOLD
            ):
                expected_strength_frames.add(
                    (row, first_analysis_column + offset)
                )
    table_data = sort_grid.get("sheets", [{}])[0].get("data", [])[
        : len(layout["blocks"])
    ]
    for block, data in zip(layout["blocks"], table_data, strict=True):
        rows = data.get("rowData", [])
        for row_index, row in enumerate(rows):
            for column_offset, cell in enumerate(row.get("values", [])):
                text_format = cell.get("userEnteredFormat", {}).get("textFormat", {})
                if text_format.get("fontSize") != expected_font_size:
                    raise RuntimeError(
                        "A ticker table cell does not use the declared font size"
                    )
                borders = cell.get("userEnteredFormat", {}).get("borders", {})
                top = borders.get("top", {}).get("style")
                bottom = borders.get("bottom", {}).get("style")
                absolute_column = (
                    column_to_index(block["start_column"]) + column_offset
                )
                absolute_row = block["header_row"] + row_index
                is_strength_frame = (
                    absolute_row,
                    absolute_column,
                ) in expected_strength_frames
                if is_strength_frame:
                    if any(
                        borders.get(edge, {}).get("style") != "SOLID_THICK"
                        for edge in ("top", "bottom", "left", "right")
                    ):
                        raise RuntimeError(
                            "A strong support/resistance cell is missing its frame: "
                            f"cell={index_to_column(absolute_column)}{absolute_row + 1}"
                        )
                elif top or (bottom and row_index < len(rows) - 1):
                    column = index_to_column(absolute_column)
                    raise RuntimeError(
                        "A ticker table still has an internal horizontal border: "
                        f"table={block['table_name']} "
                        f"cell={column}{absolute_row + 1} "
                        f"top={top!r} bottom={bottom!r}"
                    )

    panel = layout["general_panel"]
    panel_end_row = panel["start_row"] + panel["row_count"] - 1
    sort_control = layout["global_sort"]
    panel_ranges = [
        (
            f"'{layout['sheet']['title']}'!{panel['column']}{panel['start_row']}:"
            f"{panel['column']}{panel_end_row}"
        ),
        (
            f"'{layout['sheet']['title']}'!{sort_control['label_cell']}:"
            f"{sort_control['control_cell']}"
        ),
    ]
    panel_grid = client.get_spreadsheet(
        spreadsheet_id, include_grid_data=True, ranges=panel_ranges
    )
    for data in panel_grid.get("sheets", [{}])[0].get("data", []):
        for row in data.get("rowData", []):
            for cell in row.get("values", []):
                font_size = (
                    cell.get("userEnteredFormat", {})
                    .get("textFormat", {})
                    .get("fontSize")
                )
                if font_size != panel["font_size"]:
                    raise RuntimeError(
                        "The market panel or global sort control does not use "
                        "the declared font size"
                    )

    last_column = index_to_column(layout["sheet"]["column_count"] - 1)
    width_grid = client.get_spreadsheet(
        spreadsheet_id,
        include_grid_data=True,
        ranges=[f"'{layout['sheet']['title']}'!A1:{last_column}1"],
    )
    width_data = width_grid.get("sheets", [{}])[0].get("data", [{}])[0]
    column_metadata = width_data.get("columnMetadata", [])
    expected_widths = list(desired_column_widths(layout).values())
    actual_widths = [item.get("pixelSize") for item in column_metadata]
    if actual_widths != expected_widths:
        raise RuntimeError(
            f"Column widths differ from the manifest: actual={actual_widths}"
        )

    tables = client.batch_get_values(
        spreadsheet_id, _table_ranges(layout), value_render_option="UNFORMATTED_VALUE"
    )
    table_rows = [value_range.get("values", []) for value_range in tables]
    metric_rows = [row for rows in table_rows for row in rows]
    if len(metric_rows) != len(expected):
        raise RuntimeError("Live ticker tables have missing rows")
    incomplete = [
        {
            "ticker": str(row[1]) if len(row) > 1 else "<missing>",
            "columns": len(row),
            "blank_metric_offsets": [
                index for index, value in enumerate(row[2:9], start=2) if value == ""
            ],
        }
        for row in metric_rows
        if len(row) < 9 or any(value == "" for value in row[2:9])
    ]
    if incomplete:
        raise RuntimeError(f"At least one live market row is incomplete: {incomplete}")

    positions = load_positions()
    group_by_ticker = {
        ticker: group
        for group in layout["groups"]
        for ticker in group["tickers"]
    }
    shots_by_group = {
        group["id"]: sum(positions.get(ticker, 0) for ticker in group["tickers"])
        for group in layout["groups"]
    }
    for row in metric_rows:
        ticker = str(row[1]).strip().upper()
        expected_shots = shots_by_group[group_by_ticker[ticker]["id"]]
        if row[0] != expected_shots:
            raise RuntimeError(
                f"Subsector shots are stale for {ticker}: "
                f"expected={expected_shots} actual={row[0]}"
            )

    summary = layout["summary_table"]
    summary_range = (
        f"'{layout['sheet']['title']}'!{summary['start_column']}{summary['header_row'] + 1}:"
        f"{summary['end_column']}{summary['header_row'] + len(layout['groups'])}"
    )
    summary_rows = client.batch_get_values(
        spreadsheet_id, [summary_range], value_render_option="UNFORMATTED_VALUE"
    )[0].get("values", [])
    if len(summary_rows) != len(layout["groups"]) or any(
        len(row) < 8 for row in summary_rows
    ):
        raise RuntimeError("Live group summary is incomplete")
    expected_groups = {
        f"{group['sector']} / {group['label']}": group
        for group in layout["groups"]
    }
    labels = [str(row[0]).strip() for row in summary_rows]
    if len(set(labels)) != len(expected_groups) or set(labels) != set(expected_groups):
        raise RuntimeError("Live group summary labels do not match the layout")
    day_values = []
    for row, label in zip(summary_rows, labels, strict=True):
        group = expected_groups[label]
        if str(row[2]).strip().upper() != group["benchmark"]:
            raise RuntimeError(f"Group benchmark is misaligned for {label}")
        held = sum(positions.get(ticker, 0) > 0 for ticker in group["tickers"])
        shots = sum(positions.get(ticker, 0) for ticker in group["tickers"])
        if row[6] != held or row[7] != shots:
            raise RuntimeError(f"Group portfolio counts are misaligned for {label}")
        day_values.append(float(row[3]) if isinstance(row[3], (int, float)) else None)
    if day_values != sorted(
        day_values, key=lambda value: (value is None, -(value or 0.0))
    ):
        raise RuntimeError("Live group summary is not sorted by numeric Día")

    grid = client.get_spreadsheet(
        spreadsheet_id, include_grid_data=True, ranges=_score_ranges(layout)
    )
    live_sheet = next(
        sheet
        for sheet in grid.get("sheets", [])
        if sheet.get("properties", {}).get("sheetId") == layout["sheet"]["sheet_id"]
    )
    live_tables = {table["name"]: table for table in live_sheet.get("tables", [])}
    for name, expected_table in desired_tables(layout).items():
        current = live_tables.get(name)
        if current is None or current.get("range") != expected_table["range"]:
            raise RuntimeError(f"Native table {name} is missing or has the wrong range")

    dd6m_grid = client.get_spreadsheet(
        spreadsheet_id, include_grid_data=True, ranges=_vol_dd6m_ranges(layout)
    )
    dd6m_data = dd6m_grid.get("sheets", [{}])[0].get("data", [])
    expected_note = layout["notes"]["drawdown_header"]
    if len(dd6m_data) != len(layout["blocks"]):
        raise RuntimeError("DD6M header ranges could not be verified")
    for data in dd6m_data:
        rows = data.get("rowData", [])
        header_values = rows[0].get("values", []) if rows else []
        vol_header = header_values[0] if header_values else {}
        header = header_values[1] if len(header_values) > 1 else {}
        if header.get("note") != expected_note:
            raise RuntimeError("DD6M header note is missing or stale")
        if (
            vol_header.get("userEnteredFormat", {})
            .get("borders", {})
            .get("right", {})
            .get("style")
            != "SOLID_MEDIUM"
        ):
            raise RuntimeError("The Vol/DD6M vertical separator is missing")
        if any(
            row.get("values", [{}, {}])[1].get("note")
            for row in rows[1:]
            if len(row.get("values", [])) > 1
        ):
            raise RuntimeError("A DD6M body cell still contains a repetitive note")
    links = _score_links(grid)
    if len(links) != len(expected) or any("format=html" not in link for link in links):
        sample_grid = grid.get("sheets", [{}])[0].get("data", [{}])[0]
        sample_rows = sample_grid.get("rowData", [])
        sample_cell = sample_rows[0].get("values", [{}])[0] if sample_rows else {}
        raise RuntimeError(
            "Score links do not all target the rendered HTML report: "
            f"count={len(links)} sample={links[:2]} cell_keys={sorted(sample_cell)}"
        )

    print(
        f"OK tickers={len(tickers)} market_rows={len(metric_rows)} "
        f"groups={len(summary_rows)} html_links={len(links)} "
        f"sort={sort_plan.selection!r} sorted={not sort_plan.changed}"
    )


if __name__ == "__main__":
    main()
