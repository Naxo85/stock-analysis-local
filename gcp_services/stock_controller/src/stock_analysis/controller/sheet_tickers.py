from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


class TickerRows(dict[str, int]):
    """Ticker rows plus the physical native table that owns each row."""

    def __init__(
        self,
        *args: Any,
        table_by_ticker: Mapping[str, str] | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.table_by_ticker = dict(table_by_ticker or {})


def ticker_read_ranges(layout: dict[str, Any]) -> list[str]:
    """Return one bounded ticker-column range for every declared table."""
    sheet_title = layout["sheet"]["title"].replace("'", "''")
    ranges = []
    for block in layout["blocks"]:
        first_data_row = block["header_row"] + 1
        last_data_row = block["header_row"] + len(block["tickers"])
        column = _column_with_offset(
            block["start_column"],
            layout["table_template"].get("ticker_column_offset", 0),
        )
        ranges.append(
            f"'{sheet_title}'!{column}{first_data_row}:{column}{last_data_row}"
        )
    return ranges


def _column_with_offset(column: str, offset: int) -> str:
    value = 0
    for character in column:
        value = value * 26 + ord(character.upper()) - 64
    value += offset
    label = ""
    while value:
        value, remainder = divmod(value - 1, 26)
        label = chr(65 + remainder) + label
    return label


def configured_ticker_rows(layout: dict[str, Any]) -> TickerRows:
    """Return zero-based row indexes for the untouched declarative order."""
    rows = {
        ticker: block["header_row"] + offset
        for block in layout["blocks"]
        for offset, ticker in enumerate(block["tickers"])
    }
    tables = {
        ticker: block["table_name"]
        for block in layout["blocks"]
        for ticker in block["tickers"]
    }
    return TickerRows(rows, table_by_ticker=tables)


def resolve_ticker_rows(
    layout: dict[str, Any], value_ranges: Sequence[Mapping[str, Any]]
) -> TickerRows:
    """Resolve live zero-based rows and reject ambiguous or damaged tables."""
    blocks = layout["blocks"]
    if len(value_ranges) != len(blocks):
        raise ValueError(
            f"Ticker range count mismatch: expected={len(blocks)} "
            f"actual={len(value_ranges)}"
        )

    expected_universe = {
        ticker for block in blocks for ticker in block["tickers"]
    }
    resolved: dict[str, int] = {}
    table_by_ticker: dict[str, str] = {}
    for block, value_range in zip(blocks, value_ranges, strict=True):
        raw_rows = list(value_range.get("values", []))
        actual_rows = []
        for offset in range(len(block["tickers"])):
            row = raw_rows[offset] if offset < len(raw_rows) else []
            ticker = str(row[0] if row else "").strip().upper()
            actual_rows.append(ticker)

        present = {ticker for ticker in actual_rows if ticker}
        duplicates = sorted(
            ticker
            for ticker in present
            if actual_rows.count(ticker) > 1
        )
        unexpected = sorted(present - expected_universe)
        blanks = sum(not ticker for ticker in actual_rows)
        if duplicates or unexpected or blanks:
            raise ValueError(
                f"Ticker identity mismatch in {block['table_name']}: "
                f"unexpected={unexpected} "
                f"duplicates={duplicates} blanks={blanks}"
            )

        for offset, ticker in enumerate(actual_rows):
            if ticker in resolved:
                raise ValueError(f"Ticker appears in multiple tables: {ticker}")
            resolved[ticker] = block["header_row"] + offset
            table_by_ticker[ticker] = block["table_name"]

    actual_universe = set(resolved)
    if actual_universe != expected_universe:
        raise ValueError(
            f"Ticker universe mismatch: missing={sorted(expected_universe - actual_universe)} "
            f"unexpected={sorted(actual_universe - expected_universe)}"
        )

    return TickerRows(resolved, table_by_ticker=table_by_ticker)


def ordered_block_tickers(
    block: Mapping[str, Any], ticker_rows: Mapping[str, int]
) -> list[str]:
    """Return a block's tickers in their current physical row order."""
    if isinstance(ticker_rows, TickerRows):
        candidates = [
            ticker
            for ticker, table in ticker_rows.table_by_ticker.items()
            if table == block["table_name"]
        ]
    else:
        candidates = list(block["tickers"])
    ordered = sorted(
        candidates,
        key=ticker_rows.__getitem__,
    )
    if len(ordered) != len(block["tickers"]):
        raise ValueError(
            f"Wrong ticker count in {block['table_name']}: "
            f"expected={len(block['tickers'])} actual={len(ordered)}"
        )
    actual_rows = [ticker_rows[ticker] for ticker in ordered]
    expected_rows = list(
        range(block["header_row"], block["header_row"] + len(ordered))
    )
    if actual_rows != expected_rows:
        raise ValueError(
            f"Non-contiguous ticker rows in {block['table_name']}: {actual_rows}"
        )
    return ordered
