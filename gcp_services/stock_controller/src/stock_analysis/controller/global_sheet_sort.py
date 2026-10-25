from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import re
from typing import Any, Mapping

from stock_analysis.controller.sheet_layout import column_to_index
from stock_analysis.controller.sheet_tickers import TickerRows


WRITABLE_CELL_FIELDS = (
    "userEnteredValue",
    "userEnteredFormat",
    "note",
    "textFormatRuns",
    "dataValidation",
)


@dataclass(frozen=True)
class GlobalSortPlan:
    selection: str
    ticker_rows: TickerRows
    requests: list[dict[str, Any]]
    changed: bool
    support_strengths: dict[
        str,
        tuple[int | None, int | None, int | None],
    ]
    analysis_levels: dict[str, tuple[str, str, str]]
    held_tickers: frozenset[str]


def global_sort_read_ranges(layout: dict[str, Any]) -> list[str]:
    sheet = layout["sheet"]["title"].replace("'", "''")
    ranges = []
    for block in layout["blocks"]:
        first_row = block["header_row"] + 1
        last_row = block["header_row"] + len(block["tickers"])
        ranges.append(
            f"'{sheet}'!{block['start_column']}{first_row}:"
            f"{block['end_column']}{last_row}"
        )
    ranges.append(f"'{sheet}'!{layout['global_sort']['control_cell']}")
    return ranges


def build_global_sort_plan(
    layout: dict[str, Any],
    spreadsheet: Mapping[str, Any],
    *,
    sort_values: Mapping[str, Mapping[str, float | None]] | None = None,
) -> GlobalSortPlan:
    """Sort the two physical tables as one logical ticker sequence."""
    sheet = _sheet(spreadsheet, layout["sheet"]["sheet_id"])
    rows_by_ticker: dict[str, list[dict[str, Any]]] = {}
    repaired_links: set[str] = set()
    current_order: list[str] = []
    current_values: dict[str, dict[str, float | None]] = {
        "score": {},
        "setup_score": {},
        "strength": {},
    }
    headers = layout["table_template"]["headers"]
    ticker_offset = layout["table_template"]["ticker_column_offset"]
    score_offset = headers.index("Tesis" if "Tesis" in headers else "Nota")
    strength_offset = headers.index("Fuerza")
    analysis_offset = layout["table_template"].get(
        "analysis_start_column_offset", 9
    )
    support_strengths: dict[
        str,
        tuple[int | None, int | None, int | None],
    ] = {}
    analysis_levels: dict[str, tuple[str, str, str]] = {}
    held_tickers: set[str] = set()

    for block in layout["blocks"]:
        start_row = block["header_row"]
        start_column = column_to_index(block["start_column"])
        width = column_to_index(block["end_column"]) - start_column + 1
        data = _grid_data(sheet, start_row, start_column)
        raw_rows = list(data.get("rowData", []))
        for offset in range(len(block["tickers"])):
            source = raw_rows[offset] if offset < len(raw_rows) else {}
            values = list(source.get("values", []))
            values.extend({} for _ in range(width - len(values)))
            ticker = _cell_text(values[ticker_offset]).strip().upper()
            if not ticker:
                raise ValueError(
                    f"Blank ticker in {block['table_name']} row {start_row + offset + 1}"
                )
            if ticker in rows_by_ticker:
                raise ValueError(f"Ticker appears in both market tables: {ticker}")
            rows_by_ticker[ticker] = [_writable_cell(cell) for cell in values[:width]]
            if _repair_ticker_link(rows_by_ticker[ticker][ticker_offset], ticker, layout):
                repaired_links.add(ticker)
            current_values["score"][ticker] = _cell_number(values[score_offset])
            if "Setup" in headers:
                current_values["setup_score"][ticker] = _cell_number(values[headers.index("Setup")])
            current_values["strength"][ticker] = _cell_number(values[strength_offset])
            support_strengths[ticker] = (
                _support_strength(values[analysis_offset]),
                _support_strength(values[analysis_offset + 1]),
                _support_strength(values[analysis_offset + 2]),
            )
            analysis_levels[ticker] = (
                _cell_text(values[analysis_offset]),
                _cell_text(values[analysis_offset + 1]),
                _cell_text(values[analysis_offset + 2]),
            )
            if _ticker_is_held(values[ticker_offset], layout):
                held_tickers.add(ticker)
            current_order.append(ticker)

    expected = {
        ticker for block in layout["blocks"] for ticker in block["tickers"]
    }
    actual = set(rows_by_ticker)
    if actual != expected:
        raise ValueError(
            f"Global sort universe mismatch: missing={sorted(expected - actual)} "
            f"unexpected={sorted(actual - expected)}"
        )

    selection = _selected_option(layout, sheet)
    options = {
        option["label"]: option for option in layout["global_sort"]["options"]
    }
    option = options[selection]
    supplied = sort_values or {}
    if option["field"] == "group":
        group_rank = {
            ticker: index
            for index, group in enumerate(layout["groups"])
            for ticker in group["tickers"]
        }
        ordered = sorted(current_order, key=group_rank.__getitem__)
    else:
        field = option["field"]
        values = dict(current_values[field])
        values.update(supplied.get(field, {}))
        reverse = option["direction"] == "desc"
        ordered = sorted(
            current_order,
            key=lambda ticker: _metric_sort_key(values.get(ticker), ticker, reverse),
        )

    ticker_rows: dict[str, int] = {}
    table_by_ticker: dict[str, str] = {}
    requests: list[dict[str, Any]] = []
    cursor = 0
    for block in layout["blocks"]:
        count = len(block["tickers"])
        block_tickers = ordered[cursor : cursor + count]
        cursor += count
        for offset, ticker in enumerate(block_tickers):
            ticker_rows[ticker] = block["header_row"] + offset
            table_by_ticker[ticker] = block["table_name"]
        if block_tickers == current_order[cursor - count : cursor]:
            # A stable order must still repair links overwritten as plain text.
            for offset, ticker in enumerate(block_tickers):
                if ticker not in repaired_links:
                    continue
                row = block["header_row"] + offset
                column = column_to_index(block["start_column"]) + ticker_offset
                requests.append({
                    "updateCells": {
                        "range": {
                            "sheetId": layout["sheet"]["sheet_id"],
                            "startRowIndex": row,
                            "endRowIndex": row + 1,
                            "startColumnIndex": column,
                            "endColumnIndex": column + 1,
                        },
                        "rows": [{"values": [rows_by_ticker[ticker][ticker_offset]]}],
                        "fields": (
                            "userEnteredValue,textFormatRuns,"
                            "userEnteredFormat.textFormat.link,"
                            "userEnteredFormat.textFormat.underline,"
                            "userEnteredFormat.textFormat.foregroundColor,"
                            "userEnteredFormat.textFormat.foregroundColorStyle"
                        ),
                    }
                })
            continue
        start_column = column_to_index(block["start_column"])
        end_column = column_to_index(block["end_column"]) + 1
        requests.append(
            {
                "updateCells": {
                    "range": {
                        "sheetId": layout["sheet"]["sheet_id"],
                        "startRowIndex": block["header_row"],
                        "endRowIndex": block["header_row"] + count,
                        "startColumnIndex": start_column,
                        "endColumnIndex": end_column,
                    },
                    "rows": [
                        {"values": rows_by_ticker[ticker]}
                        for ticker in block_tickers
                    ],
                    "fields": ",".join(WRITABLE_CELL_FIELDS),
                }
            }
        )

    return GlobalSortPlan(
        selection=selection,
        ticker_rows=TickerRows(
            ticker_rows, table_by_ticker=table_by_ticker
        ),
        requests=requests,
        changed=ordered != current_order,
        support_strengths=support_strengths,
        analysis_levels=analysis_levels,
        held_tickers=frozenset(held_tickers),
    )


def build_global_sort_control_requests(
    layout: dict[str, Any], selection: str
) -> list[dict[str, Any]]:
    control = layout["global_sort"]
    labels = [option["label"] for option in control["options"]]
    if selection not in labels:
        selection = control["default"]
    label_row, label_column = _cell_coordinates(control["label_cell"])
    value_row, value_column = _cell_coordinates(control["control_cell"])
    panel = layout["general_panel"]
    cell_format = {
        "backgroundColorStyle": {"rgbColor": _rgb(control["background"])},
        "horizontalAlignment": "CENTER",
        "verticalAlignment": "MIDDLE",
        "textFormat": {
            "fontFamily": panel["font_family"],
            "fontSize": panel["font_size"],
            "foregroundColorStyle": {"rgbColor": _rgb(control["text_color"])},
        },
    }
    label_format = deepcopy(cell_format)
    label_format["textFormat"]["bold"] = True
    table_sizes = [len(block["tickers"]) for block in layout["blocks"]]
    distribution = "/".join(str(size) for size in table_sizes)
    return [
        {
            "updateCells": {
                "start": {
                    "sheetId": layout["sheet"]["sheet_id"],
                    "rowIndex": label_row,
                    "columnIndex": label_column,
                },
                "rows": [
                    {
                        "values": [
                            {
                                "userEnteredValue": {"stringValue": control["label"]},
                                "userEnteredFormat": label_format,
                            }
                        ]
                    }
                ],
                "fields": "userEnteredValue,userEnteredFormat",
            }
        },
        {
            "updateCells": {
                "start": {
                    "sheetId": layout["sheet"]["sheet_id"],
                    "rowIndex": value_row,
                    "columnIndex": value_column,
                },
                "rows": [
                    {
                        "values": [
                            {
                                "userEnteredValue": {"stringValue": selection},
                                "note": (
                                    f"Ordena los {sum(table_sizes)} tickers como una "
                                    f"sola lista y los reparte {distribution} entre "
                                    "ambas tablas en el siguiente refresco."
                                ),
                                "dataValidation": {
                                    "condition": {
                                        "type": "ONE_OF_LIST",
                                        "values": [
                                            {"userEnteredValue": label}
                                            for label in labels
                                        ],
                                    },
                                    "strict": True,
                                    "showCustomUi": True,
                                },
                                "userEnteredFormat": cell_format,
                            }
                        ]
                    }
                ],
                "fields": (
                    "userEnteredValue,note,dataValidation,userEnteredFormat"
                ),
            }
        },
    ]


def _selected_option(layout: dict[str, Any], sheet: Mapping[str, Any]) -> str:
    row, column = _cell_coordinates(layout["global_sort"]["control_cell"])
    data = _grid_data(sheet, row, column)
    rows = data.get("rowData", [])
    cells = rows[0].get("values", []) if rows else []
    selected = _cell_text(cells[0]) if cells else ""
    labels = {option["label"] for option in layout["global_sort"]["options"]}
    return selected if selected in labels else layout["global_sort"]["default"]


def _sheet(spreadsheet: Mapping[str, Any], sheet_id: int) -> Mapping[str, Any]:
    return next(
        sheet
        for sheet in spreadsheet.get("sheets", [])
        if sheet.get("properties", {}).get("sheetId") == sheet_id
    )


def _grid_data(
    sheet: Mapping[str, Any], start_row: int, start_column: int
) -> Mapping[str, Any]:
    return next(
        data
        for data in sheet.get("data", [])
        if int(data.get("startRow", 0)) == start_row
        and int(data.get("startColumn", 0)) == start_column
    )


def _repair_ticker_link(
    cell: dict[str, Any], ticker: str, layout: Mapping[str, Any]
) -> bool:
    """Restore a ticker's canonical link without changing portfolio formatting."""
    url = layout["links"]["ticker"].format(ticker=ticker)
    formula = f'=HYPERLINK("{url}";"{ticker}")'
    entered = cell.get("userEnteredValue", {}).get("formulaValue")
    if entered in (formula, formula.replace(";", ",")):
        return False
    cell["userEnteredValue"] = {"formulaValue": formula}
    cell.pop("textFormatRuns", None)
    text = cell.setdefault("userEnteredFormat", {}).setdefault("textFormat", {})
    text.pop("foregroundColor", None)
    text["foregroundColorStyle"] = {"rgbColor": _rgb("#0B6E75")}
    text["underline"] = True
    text["link"] = {"uri": url}
    return True


def _writable_cell(cell: Mapping[str, Any]) -> dict[str, Any]:
    writable = {
        field: deepcopy(cell[field])
        for field in WRITABLE_CELL_FIELDS
        if field in cell
    }
    writable.get("userEnteredFormat", {}).pop("borders", None)
    text_format = writable.get("userEnteredFormat", {}).get("textFormat", {})
    link = text_format.get("link", {}).get("uri")
    text = writable.get("userEnteredValue", {}).get("stringValue")
    if link and isinstance(text, str) and text and not writable.get("textFormatRuns"):
        # Sheets normalizes one uniform linked run into textFormat.link when
        # read back. Our sort mask also writes textFormatRuns: omitting that
        # field clears the link even alongside the copied whole-cell format.
        # Reconstitute the uniform run; preserve partial runs and formulas.
        writable["textFormatRuns"] = [{"startIndex": 0, "format": deepcopy(text_format)}]
    return writable


def _cell_text(cell: Mapping[str, Any]) -> str:
    effective = cell.get("effectiveValue", {})
    entered = cell.get("userEnteredValue", {})
    value = effective.get("stringValue", entered.get("stringValue", ""))
    return str(value)


def _cell_number(cell: Mapping[str, Any]) -> float | None:
    effective = cell.get("effectiveValue", {})
    if "numberValue" in effective:
        return float(effective["numberValue"])
    text = _cell_text(cell).strip().replace(",", ".")
    try:
        return float(text)
    except ValueError:
        return None


def _support_strength(cell: Mapping[str, Any]) -> int | None:
    match = re.search(r"(?:^|\n)Fortaleza:\s*(\d{1,3})/100(?:\s|$)", str(cell.get("note") or ""))
    if not match:
        return None
    value = int(match.group(1))
    return value if 0 <= value <= 100 else None


def _ticker_is_held(cell: Mapping[str, Any], layout: Mapping[str, Any]) -> bool:
    rgb = (
        cell.get("userEnteredFormat", {})
        .get("backgroundColorStyle", {})
        .get("rgbColor")
    )
    if not isinstance(rgb, Mapping):
        return False
    actual = tuple(float(rgb.get(channel, 0.0)) for channel in ("red", "green", "blue"))
    colors = layout["format_rules"]["portfolio_ticker"]
    expected = (
        _rgb(colors["single_shot_background"]),
        _rgb(colors["double_shot_background"]),
    )
    return any(
        all(
            abs(actual[index] - float(color.get(channel, 0.0))) < 1e-6
            for index, channel in enumerate(("red", "green", "blue"))
        )
        for color in expected
    )


def _metric_sort_key(
    value: float | None, ticker: str, descending: bool
) -> tuple[bool, float, str]:
    if value is None:
        return True, 0.0, ticker
    return False, -value if descending else value, ticker


def _cell_coordinates(cell: str) -> tuple[int, int]:
    split = 0
    while split < len(cell) and cell[split].isalpha():
        split += 1
    column = column_to_index(cell[:split])
    row = int(cell[split:]) - 1
    return row, column


def _rgb(hex_color: str) -> dict[str, float]:
    value = hex_color.removeprefix("#")
    return {
        "red": int(value[0:2], 16) / 255,
        "green": int(value[2:4], 16) / 255,
        "blue": int(value[4:6], 16) / 255,
    }
