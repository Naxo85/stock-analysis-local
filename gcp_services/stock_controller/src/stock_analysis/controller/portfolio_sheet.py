from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from datetime import date
from pathlib import Path
from typing import Any

from stock_analysis.controller.sheet_layout import column_to_index
from stock_analysis.controller.sheet_tickers import (
    configured_ticker_rows,
    ordered_block_tickers,
)


DEFAULT_PORTFOLIO_PATH = (
    Path(__file__).resolve().parents[3] / "config" / "portfolio.json"
)


def load_positions(path: Path | None = None) -> dict[str, int]:
    portfolio_path = path or DEFAULT_PORTFOLIO_PATH
    with portfolio_path.open(encoding="utf-8") as source:
        payload = json.load(source)
    return {
        str(ticker).strip().upper(): int(shots)
        for ticker, shots in payload["positions"].items()
        if int(shots) > 0
    }


def load_held_tickers(path: Path | None = None) -> tuple[str, ...]:
    return tuple(load_positions(path))


def update_positions(
    *,
    set_shots: Mapping[str, int] | None = None,
    remove: Iterable[str] = (),
    path: Path | None = None,
) -> dict[str, int]:
    portfolio_path = path or DEFAULT_PORTFOLIO_PATH
    with portfolio_path.open(encoding="utf-8") as source:
        payload = json.load(source)

    changes = {
        ticker.strip().upper(): int(shots)
        for ticker, shots in (set_shots or {}).items()
        if ticker.strip()
    }
    if any(shots < 1 for shots in changes.values()):
        raise ValueError("Shots must be positive integers")
    removals = {ticker.strip().upper() for ticker in remove if ticker.strip()}
    overlap = set(changes) & removals
    if overlap:
        raise ValueError(f"Tickers cannot be added and removed together: {sorted(overlap)}")

    positions = load_positions(portfolio_path)
    for ticker in removals:
        positions.pop(ticker, None)
    positions.update(changes)
    payload["updated_at"] = date.today().isoformat()
    payload["positions"] = positions

    temporary = portfolio_path.with_suffix(".json.tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8"
    )
    temporary.replace(portfolio_path)
    return positions


def _rgb(hex_color: str) -> dict[str, float]:
    value = hex_color.removeprefix("#")
    if len(value) != 6:
        raise ValueError(f"Invalid RGB color: {hex_color!r}")
    return {
        "red": int(value[0:2], 16) / 255,
        "green": int(value[2:4], 16) / 255,
        "blue": int(value[4:6], 16) / 255,
    }


def build_portfolio_format_requests(
    layout: dict[str, Any],
    positions: Mapping[str, int] | Iterable[str],
    ticker_rows: Mapping[str, int] | None = None,
) -> list[dict[str, Any]]:
    """Reconcile every ticker cell against the declared portfolio state."""
    if isinstance(positions, Mapping):
        shots_by_ticker = {
            ticker.strip().upper(): int(shots) for ticker, shots in positions.items()
        }
    else:
        shots_by_ticker = {ticker.strip().upper(): 1 for ticker in positions}
    colors = layout["format_rules"]["portfolio_ticker"]
    sheet_id = layout["sheet"]["sheet_id"]
    requests = []
    live_rows = (
        ticker_rows if ticker_rows is not None else configured_ticker_rows(layout)
    )

    for block in layout["blocks"]:
        column_index = (
            column_to_index(block["start_column"])
            + layout["table_template"].get("ticker_column_offset", 0)
        )
        physical_tickers = ordered_block_tickers(block, live_rows)
        for ticker in physical_tickers:
            shots = shots_by_ticker.get(ticker, 0)
            if shots >= 2:
                background = colors["double_shot_background"]
            elif shots == 1:
                background = colors["single_shot_background"]
            else:
                background = block["palette"]["body"]

            row_index = live_rows[ticker]
            requests.append(
                {
                    "repeatCell": {
                        "range": {
                            "sheetId": sheet_id,
                            "startRowIndex": row_index,
                            "endRowIndex": row_index + 1,
                            "startColumnIndex": column_index,
                            "endColumnIndex": column_index + 1,
                        },
                        "cell": {
                            "userEnteredFormat": {
                                "backgroundColorStyle": {"rgbColor": _rgb(background)}
                            }
                        },
                        "fields": "userEnteredFormat.backgroundColorStyle",
                    }
                }
            )
    return requests


def build_group_summary_position_requests(
    layout: dict[str, Any],
    positions: Mapping[str, int],
    group_order: Iterable[str] | None = None,
) -> list[dict[str, Any]]:
    """Write portfolio counts for every configured group."""
    summary = layout["summary_table"]
    start_column = column_to_index(summary["start_column"]) + 6
    by_label = {
        f"{group['sector']} / {group['label']}": group
        for group in layout["groups"]
    }
    labels = list(group_order) if group_order is not None else list(by_label)
    if len(labels) != len(by_label) or set(labels) != set(by_label):
        raise ValueError("Group summary order does not match configured groups")
    rows = []
    for label in labels:
        group = by_label[label]
        held = [ticker for ticker in group["tickers"] if positions.get(ticker, 0) > 0]
        shots = sum(int(positions.get(ticker, 0)) for ticker in group["tickers"])
        rows.append(
            {
                "values": [
                    {"userEnteredValue": {"numberValue": len(held)}},
                    {"userEnteredValue": {"numberValue": shots}},
                ]
            }
        )
    return [
        {
            "updateCells": {
                "range": {
                    "sheetId": layout["sheet"]["sheet_id"],
                    "startRowIndex": summary["header_row"],
                    "endRowIndex": summary["header_row"] + len(rows),
                    "startColumnIndex": start_column,
                    "endColumnIndex": start_column + 2,
                },
                "rows": rows,
                "fields": "userEnteredValue",
            }
        }
    ]


def build_group_shot_strip_requests(
    layout: dict[str, Any],
    positions: Mapping[str, int],
    ticker_rows: Mapping[str, int] | None = None,
) -> list[dict[str, Any]]:
    """Write each subsector's total shots beside every ticker in that group."""
    normalized_positions = {
        ticker.strip().upper(): int(shots) for ticker, shots in positions.items()
    }
    group_by_ticker = {
        ticker: group
        for group in layout["groups"]
        for ticker in group["tickers"]
    }
    shots_by_group = {
        group["id"]: sum(
            normalized_positions.get(ticker, 0) for ticker in group["tickers"]
        )
        for group in layout["groups"]
    }
    live_rows = (
        ticker_rows if ticker_rows is not None else configured_ticker_rows(layout)
    )
    requests = []
    for block in layout["blocks"]:
        physical_tickers = ordered_block_tickers(block, live_rows)
        rows = []
        for ticker in physical_tickers:
            group = group_by_ticker[ticker]
            rows.append(
                {
                    "values": [
                        {
                            "userEnteredValue": {
                                "numberValue": shots_by_group[group["id"]]
                            },
                            "userEnteredFormat": {
                                "backgroundColorStyle": {
                                    "rgbColor": _rgb(group["background"])
                                },
                                "textFormat": {
                                    "fontFamily": layout["table_template"]["font_family"],
                                    "fontSize": layout["table_template"]["font_size"],
                                    "foregroundColorStyle": {
                                        "rgbColor": _rgb(group["text"])
                                    },
                                    "bold": True,
                                },
                            },
                        }
                    ]
                }
            )
        start_column = column_to_index(block["start_column"])
        requests.append(
            {
                "updateCells": {
                    "range": {
                        "sheetId": layout["sheet"]["sheet_id"],
                        "startRowIndex": block["header_row"],
                        "endRowIndex": block["header_row"] + len(rows),
                        "startColumnIndex": start_column,
                        "endColumnIndex": start_column + 1,
                    },
                    "rows": rows,
                    "fields": (
                        "userEnteredValue,userEnteredFormat.backgroundColorStyle,"
                        "userEnteredFormat.textFormat"
                    ),
                }
            }
        )
    return requests
