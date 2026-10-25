from __future__ import annotations

from collections.abc import Collection, Mapping, Sequence
import re
from typing import Any

from stock_analysis.contracts.analysis import AnalysisSheetRecord, PriceRange, support_validity_floor
from stock_analysis.controller.sheet_layout import column_to_index
from stock_analysis.controller.sheet_tickers import (
    ordered_block_tickers,
    resolve_ticker_rows,
)


SUPPORT_STRENGTH_BORDER_THRESHOLD = 85
SUPPORT_STRENGTH_EXCEPTIONAL_THRESHOLD = 95
SUPPORT_STRENGTH_VISIBLE_THRESHOLD = 65
RESISTANCE_STRENGTH_VISIBLE_THRESHOLD = 70
SUPPORT_STRENGTH_STRONG_BORDER_COLOR = "#1F4E78"
SUPPORT_STRENGTH_EXCEPTIONAL_BORDER_COLOR = "#00A2FF"


def analysis_read_ranges(layout: dict[str, Any]) -> list[str]:
    sheet_title = layout["sheet"]["title"].replace("'", "''")
    ranges = []
    for block in layout["blocks"]:
        first_row = block["header_row"] + 1
        last_row = block["header_row"] + len(block["tickers"])
        ticker_column = _column_with_offset(
            block["start_column"],
            layout["table_template"].get("ticker_column_offset", 0),
        )
        score_column = _column_with_offset(
            block["start_column"],
            layout["table_template"].get("analysis_start_column_offset", 9) + 3,
        )
        ranges.append(
            f"'{sheet_title}'!{ticker_column}{first_row}:{score_column}{last_row}"
        )
    return ranges


def resolve_ticker_rows_and_prices(
    layout: dict[str, Any], value_ranges: Sequence[Mapping[str, Any]]
) -> tuple[dict[str, int], dict[str, float]]:
    rows = resolve_ticker_rows(layout, value_ranges)
    prices: dict[str, float] = {}
    for block, value_range in zip(layout["blocks"], value_ranges, strict=True):
        raw_rows = list(value_range.get("values", []))
        for offset in range(len(block["tickers"])):
            row = raw_rows[offset] if offset < len(raw_rows) else []
            ticker = str(row[0] if row else "").strip().upper()
            price = _number(row[1] if len(row) > 1 else None)
            if ticker and price is not None:
                prices[ticker] = price
    return rows, prices


def resolve_visible_scores(
    layout: dict[str, Any], value_ranges: Sequence[Mapping[str, Any]]
) -> dict[str, float]:
    scores: dict[str, float] = {}
    ticker_offset = layout["table_template"].get("ticker_column_offset", 0)
    score_offset = layout["table_template"].get("analysis_start_column_offset", 9) + 3
    relative_score_offset = score_offset - ticker_offset
    for block, value_range in zip(layout["blocks"], value_ranges, strict=True):
        raw_rows = list(value_range.get("values", []))
        for offset in range(len(block["tickers"])):
            row = raw_rows[offset] if offset < len(raw_rows) else []
            ticker = str(row[0] if row else "").strip().upper()
            score = _number(
                row[relative_score_offset]
                if len(row) > relative_score_offset
                else None
            )
            if ticker and score is not None:
                scores[ticker] = score
    return scores


def build_analysis_value_requests(
    layout: dict[str, Any],
    records: Mapping[str, AnalysisSheetRecord],
    *,
    ticker_rows: Mapping[str, int],
    prices: Mapping[str, float],
    held_tickers: Collection[str] | None = None,
    allow_missing: bool = False,
) -> list[dict[str, Any]]:
    requests = []
    expected = {
        # Each ticker owns all analysis cells in its current physical row.
        ticker for block in layout["blocks"] for ticker in block["tickers"]
    }
    missing = sorted(expected - set(records))
    if missing and not allow_missing:
        raise ValueError(f"Missing analysis records: {missing}")
    held = (
        None
        if held_tickers is None
        else {str(ticker).strip().upper() for ticker in held_tickers}
    )

    for block in layout["blocks"]:
        ordered = ordered_block_tickers(block, ticker_rows)
        rows = []
        for ticker in ordered:
            base_background = block["palette"]["body"]
            record = records.get(ticker)
            if record is None:
                rows.append(
                    {"values": [_blank_cell(base_background) for _ in range(5 if "Setup" in layout["table_template"].get("headers", []) else 4)]}
                )
                continue
            price = prices.get(ticker)
            rows.append(
                {
                    "values": [
                        _visible_level_cell(
                            record.entry,
                            stop=record.entry_stop,
                            strength=record.entry_strength,
                            strength_category=record.entry_strength_category,
                            strength_factors=record.entry_strength_factors,
                            price=price,
                            base_background=base_background,
                            proximity_rules=layout["format_rules"]["entry_proximity"],
                            support_validity=record.entry_support_validity,
                            suppress_broken=(
                                price is not None
                                and record.washout is not None
                                and record.washout_strength is not None
                                and record.washout_strength
                                >= SUPPORT_STRENGTH_VISIBLE_THRESHOLD
                                and price <= record.washout.upper
                            ),
                        ),
                        _visible_level_cell(
                            record.washout,
                            stop=record.washout_stop,
                            strength=record.washout_strength,
                            strength_category=record.washout_strength_category,
                            strength_factors=record.washout_strength_factors,
                            price=price,
                            base_background=base_background,
                            proximity_rules=layout["format_rules"]["entry_proximity"],
                            support_validity=record.washout_support_validity,
                        ),
                        _blank_cell(base_background) if not layout['table_template'].get('show_resistance', True) else _resistance_cell(
                            record.resistance,
                            strength=record.resistance_strength,
                            strength_category=record.resistance_strength_category,
                            strength_factors=record.resistance_strength_factors,
                            strength_breakdown=record.resistance_strength_breakdown,
                            price=price,
                            base_background=base_background,
                            proximity_rules=layout["format_rules"][
                                "resistance_proximity"
                            ],
                            color_proximity=held is None or ticker in held,
                        ),
                        _score_cell(record, base_background, thesis="Tesis" in layout["table_template"].get("headers", [])),
                    ]
                    + ([_setup_cell(record, base_background)] if "Setup" in layout["table_template"].get("headers", []) else [])
                }
            )

        start_column = column_to_index(block["start_column"]) + layout[
            "table_template"
        ].get("analysis_start_column_offset", 9)
        requests.append(
            {
                "updateCells": {
                    "range": {
                        "sheetId": layout["sheet"]["sheet_id"],
                        "startRowIndex": block["header_row"],
                        "endRowIndex": block["header_row"] + len(rows),
                        "startColumnIndex": start_column,
                        "endColumnIndex": start_column + (5 if "Setup" in layout["table_template"].get("headers", []) else 4),
                    },
                    "rows": rows,
                    "fields": (
                        "userEnteredValue,note,textFormatRuns,"
                        "userEnteredFormat.numberFormat,"
                        "userEnteredFormat.backgroundColorStyle,"
                        "userEnteredFormat.horizontalAlignment,"
                        "userEnteredFormat.verticalAlignment,"
                        "userEnteredFormat.textFormat.link,"
                        "userEnteredFormat.textFormat.foregroundColorStyle,"
                        "userEnteredFormat.textFormat.underline,"
                        "userEnteredFormat.hyperlinkDisplayType"
                    ),
                }
            }
        )
    return requests



def build_strength_border_requests(
    layout: dict[str, Any],
    records: Mapping[str, AnalysisSheetRecord],
    *,
    ticker_rows: Mapping[str, int],
) -> list[dict[str, Any]]:
    strengths = {
        ticker: (
            record.entry_strength,
            record.washout_strength,
            record.resistance_strength if layout['table_template'].get('show_resistance', True) else None,
        )
        for ticker, record in records.items()
    }
    return build_strength_border_requests_for_values(
        layout,
        strengths,
        ticker_rows=ticker_rows,
    )


def build_strength_border_requests_for_values(
    layout: dict[str, Any],
    strengths: Mapping[
        str,
        tuple[int | None, int | None, int | None],
    ],
    *,
    ticker_rows: Mapping[str, int],
) -> list[dict[str, Any]]:
    requests = []
    analysis_offset = layout["table_template"].get(
        "analysis_start_column_offset",
        9,
    )
    blocks_by_name = {
        block["table_name"]: block for block in layout["blocks"]
    }
    table_by_ticker = getattr(ticker_rows, "table_by_ticker", {})
    for ticker, ticker_strengths in strengths.items():
        table_name = table_by_ticker.get(ticker)
        block = blocks_by_name.get(table_name)
        if block is None:
            block = next(
                (
                    candidate
                    for candidate in layout["blocks"]
                    if ticker in candidate["tickers"]
                ),
                None,
            )
        if block is None:
            continue
        entry_column = column_to_index(block["start_column"]) + analysis_offset
        row = ticker_rows.get(ticker)
        if row is None:
            continue
        for column_offset, strength in enumerate(ticker_strengths):
            if column_offset == 2 and not layout['table_template'].get('show_resistance', True):
                continue
            if strength is None or strength < SUPPORT_STRENGTH_BORDER_THRESHOLD:
                continue
            border_color = (
                SUPPORT_STRENGTH_EXCEPTIONAL_BORDER_COLOR
                if strength >= SUPPORT_STRENGTH_EXCEPTIONAL_THRESHOLD
                else SUPPORT_STRENGTH_STRONG_BORDER_COLOR
            )
            border = {
                "style": "SOLID_THICK",
                "colorStyle": {"rgbColor": _rgb(border_color)},
            }
            requests.append(
                {
                    "updateBorders": {
                        "range": {
                            "sheetId": layout["sheet"]["sheet_id"],
                            "startRowIndex": row,
                            "endRowIndex": row + 1,
                            "startColumnIndex": entry_column + column_offset,
                            "endColumnIndex": entry_column + column_offset + 1,
                        },
                        "top": border,
                        "bottom": border,
                        "left": border,
                        "right": border,
                    }
                }
            )
    return requests


def build_live_proximity_background_requests(
    layout: dict[str, Any],
    levels: Mapping[str, tuple[str, str, str]],
    *,
    ticker_rows: Mapping[str, int],
    prices: Mapping[str, float],
    held_tickers: Collection[str] | None = None,
    support_validity: Mapping[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Refresh Entry/Washout colors from the latest visible market price."""
    requests = []
    analysis_offset = layout["table_template"].get(
        "analysis_start_column_offset", 9
    )
    entry_proximity_rules = layout["format_rules"]["entry_proximity"]
    resistance_proximity_rules = layout["format_rules"]["resistance_proximity"]
    held = (
        None
        if held_tickers is None
        else {str(ticker).strip().upper() for ticker in held_tickers}
    )
    for block in layout["blocks"]:
        ordered = ordered_block_tickers(block, ticker_rows)
        base_background = block["palette"]["body"]
        rows = []
        for ticker in ordered:
            ticker_levels = levels.get(ticker, ("", "", ""))
            validity = (support_validity or {}).get(ticker) or {}
            if not isinstance(validity, dict):
                validity = {}
            entry_level = _parse_display_range(ticker_levels[0])
            washout_level = _parse_display_range(ticker_levels[1])
            # Sheet displays one decimal; use the exact typed range only when
            # its display matches the zone in this ticker's current row.
            entry_level = _bound_live_range(ticker_levels[0], entry_level, validity.get('entry'))
            washout_level = _bound_live_range(ticker_levels[1], washout_level, validity.get('washout'))
            price = prices.get(ticker)
            rows.append(
                {
                    "values": [
                        {
                            "userEnteredFormat": {
                                "backgroundColorStyle": {
                                    "rgbColor": _rgb(
                                        _proximity_background(
                                            entry_level,
                                            price,
                                            base_background,
                                            entry_proximity_rules,
                                            support_validity=validity.get('entry'),
                                            suppress_broken=(
                                                washout_level is not None
                                                and price is not None
                                                and price <= washout_level.upper
                                            ),
                                        )
                                    )
                                }
                            }
                        },
                        {
                            "userEnteredFormat": {
                                "backgroundColorStyle": {
                                    "rgbColor": _rgb(
                                        _proximity_background(
                                            washout_level,
                                            price,
                                            base_background,
                                            entry_proximity_rules,
                                            support_validity=validity.get('washout'),
                                        )
                                    )
                                }
                            }
                        },
                    ]
                    + [
                        {
                            "userEnteredFormat": {
                                "backgroundColorStyle": {
                                    "rgbColor": _rgb(
                                        _resistance_proximity_background(
                                            _parse_display_range(ticker_levels[2]),
                                            prices.get(ticker),
                                            base_background,
                                            resistance_proximity_rules,
                                        )
                                        if layout['table_template'].get('show_resistance', True) and (held is None or ticker in held)
                                        else base_background
                                    )
                                }
                            }
                        }
                    ]
                }
            )
        start_column = column_to_index(block["start_column"]) + analysis_offset
        requests.append(
            {
                "updateCells": {
                    "range": {
                        "sheetId": layout["sheet"]["sheet_id"],
                        "startRowIndex": block["header_row"],
                        "endRowIndex": block["header_row"] + len(rows),
                        "startColumnIndex": start_column,
                        "endColumnIndex": start_column + 3,
                    },
                    "rows": rows,
                    "fields": "userEnteredFormat.backgroundColorStyle",
                }
            }
        )
    return requests



def _blank_cell(base_background: str) -> dict[str, Any]:
    return {
        "userEnteredValue": {"stringValue": ""},
        "note": "",
        "textFormatRuns": [],
        "userEnteredFormat": _cell_format(base_background),
    }


def _visible_level_cell(
    level: PriceRange | None,
    *,
    stop: float | None,
    strength: int | None,
    strength_category: str | None,
    strength_factors: str | None,
    price: float | None,
    base_background: str,
    proximity_rules: list[dict[str, Any]],
    suppress_broken: bool = False,
    support_validity: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if strength is None or strength < SUPPORT_STRENGTH_VISIBLE_THRESHOLD:
        return _blank_cell(base_background)
    return _level_cell(
        level,
        stop=stop,
        strength=strength,
        strength_category=strength_category,
        strength_factors=strength_factors,
        price=price,
        base_background=base_background,
        proximity_rules=proximity_rules,
        suppress_broken=suppress_broken,
        support_validity=support_validity,
    )



def _level_cell(
    level: PriceRange | None,
    *,
    stop: float | None,
    strength: int | None,
    strength_category: str | None,
    strength_factors: str | None,
    price: float | None,
    base_background: str,
    proximity_rules: list[dict[str, Any]],
    suppress_broken: bool = False,
    support_validity: dict[str, Any] | None = None,
) -> dict[str, Any]:
    value = _format_range(level) if level else ""
    return {
        "userEnteredValue": {"stringValue": value},
        "note": _level_note(
            level=level,
            stop=stop,
            strength=strength,
            strength_category=strength_category,
            strength_factors=strength_factors,
            support_validity=support_validity,
        ),
        "textFormatRuns": [],
        "userEnteredFormat": _cell_format(
            _proximity_background(
                level,
                price,
                base_background,
                proximity_rules,
                suppress_broken=suppress_broken,
                support_validity=support_validity,
            )
        ),
    }



def _resistance_cell(
    level: PriceRange | None,
    *,
    strength: int | None,
    strength_category: str | None,
    strength_factors: str | None,
    strength_breakdown: Mapping[str, int] | None,
    price: float | None,
    base_background: str,
    proximity_rules: list[dict[str, Any]],
    color_proximity: bool = True,
) -> dict[str, Any]:
    if (
        level is None
        or strength is None
        or strength < RESISTANCE_STRENGTH_VISIBLE_THRESHOLD
    ):
        return _blank_cell(base_background)
    return {
        "userEnteredValue": {"stringValue": _format_range(level)},
        "note": _resistance_note(
            level=level,
            strength=strength,
            strength_category=strength_category,
            strength_factors=strength_factors,
            strength_breakdown=strength_breakdown,
            price=price,
        ),
        "textFormatRuns": [],
        "userEnteredFormat": _cell_format(
            _resistance_proximity_background(
                level,
                price,
                base_background,
                proximity_rules,
            )
            if color_proximity
            else base_background
        ),
    }


def _score_cell(record: AnalysisSheetRecord, base_background: str, *, thesis: bool = False) -> dict[str, Any]:
    score = record.thesis_score if thesis else record.score
    value = _format_price(score) if score is not None else ("Ver" if thesis else "")
    if record.attempt_notice:
        value = (value or "Ver") + " ⚠"
    runs = []
    if value:
        runs = [
            {
                "startIndex": 0,
                "format": {
                    "link": {"uri": record.report_url},
                    "foregroundColorStyle": {"rgbColor": _rgb("#1155CC")},
                    "underline": True,
                    "bold": False,
                },
            }
        ]
    cell_format = _cell_format(
        (record.score_background if score is not None else None) or base_background
    )
    if value:
        # A whole-cell link survives value rewrites that erase rich text runs.
        cell_format["textFormat"] = runs[0]["format"].copy()
        cell_format["hyperlinkDisplayType"] = "LINKED"
    return {
        "userEnteredValue": {"stringValue": value},
        "note": (record.attempt_notice + "\n" if record.attempt_notice else "") + (
            "Pendiente de separar Tesis y Setup en el próximo análisis. El enlace conserva el informe histórico y su nota mixta."
            if thesis and score is None and record.generated_at is not None else "\n".join(filter(None, [record.thesis_reason if thesis else "", record.score_note]))
        ),
        "textFormatRuns": runs,
        "userEnteredFormat": cell_format,
    }



def _setup_cell(record: AnalysisSheetRecord, base_background: str) -> dict[str, Any]:
    cell = _blank_cell(base_background)
    if record.setup_score is not None:
        cell["userEnteredValue"] = {"stringValue": _format_price(record.setup_score)}
        cell["note"] = record.setup_reason
    else:
        cell["note"] = ("Setup pendiente del próximo análisis; no se deduce de la nota histórica."
                        if record.generated_at is not None else "Todavía no hay un informe válido disponible.")
    return cell


def _cell_format(background: str) -> dict[str, Any]:
    return {
        "numberFormat": {"type": "TEXT"},
        "backgroundColorStyle": {"rgbColor": _rgb(background)},
        "horizontalAlignment": "CENTER",
        "verticalAlignment": "MIDDLE",
    }


def _proximity_background(
    level: PriceRange | None,
    price: float | None,
    base_background: str,
    rules: list[dict[str, Any]],
    *,
    suppress_broken: bool = False,
    support_validity: dict[str, Any] | None = None,
) -> str:
    from math import isfinite
    if (level is None or type(price) not in (int, float) or not isfinite(price) or price <= 0
            or any(type(n) not in (int, float) or not isfinite(n) or n <= 0 for n in (level.lower, level.upper))
            or level.lower > level.upper):
        return base_background
    floor = support_validity_floor(level, support_validity)
    if price > level.upper or price < (floor if floor is not None else level.lower):
        return base_background
    return next(
        (
            rule["background"]
            for rule in rules
            if rule.get("state") in ("inside_range", "inside_or_up_to_0_5_pct_above")
        ),
        base_background,
    )



def _resistance_proximity_background(
    level: PriceRange | None,
    price: float | None,
    base_background: str,
    rules: list[dict[str, Any]],
) -> str:
    if level is None or price is None or price > level.upper:
        return base_background
    if price >= level.lower * 0.995:
        state = "inside_or_up_to_0_5_pct_below"
    elif price >= level.lower * 0.985:
        state = "from_0_5_to_1_5_pct_below"
    else:
        return base_background
    return next(
        (
            rule["background"]
            for rule in rules
            if rule.get("state") == state
        ),
        base_background,
    )


def _level_note(
    *,
    level: PriceRange | None,
    stop: float | None,
    strength: int | None,
    strength_category: str | None,
    strength_factors: str | None,
    support_validity: dict[str, Any] | None = None,
) -> str:
    lines = []
    floor = support_validity_floor(level, support_validity)
    if floor is not None:
        lines.append('Extensión inferior estimada: ' + str(floor).removesuffix('.0').replace('.', ',') +
                     ' · evaluada ' + str(support_validity['assessed_at'])[:10])
    if stop is not None:
        support_midpoint = (
            (
                _display_price_value(level.lower)
                + _display_price_value(level.upper)
            )
            / 2
            if level is not None
            else None
        )
        lines.append(
            f"Stop: {_level_with_distance(_display_price_value(stop), support_midpoint)}"
        )
    if strength is not None:
        category = f" ({strength_category})" if strength_category else ""
        lines.append(f"Fortaleza: {strength}/100{category}")
    if strength_factors:
        lines.append(f"Factores: {strength_factors}")
    return "\n".join(lines)



def _resistance_note(
    *,
    level: PriceRange,
    strength: int,
    strength_category: str | None,
    strength_factors: str | None,
    strength_breakdown: Mapping[str, int] | None,
    price: float | None,
) -> str:
    midpoint = (_display_price_value(level.lower) + _display_price_value(level.upper)) / 2
    lines = [f"Distancia: {_level_with_distance(midpoint, price)}"]
    category = f" ({strength_category})" if strength_category else ""
    lines.append(f"Fortaleza: {strength}/100{category}")
    if strength_breakdown:
        labels = (
            ("estructura", "estructura", 25),
            ("volumen", "volumen", 20),
            ("opciones", "opciones", 25),
            ("confluencia", "confluencia", 15),
            ("durabilidad", "durabilidad", 15),
        )
        parts = [
            f"{label} {strength_breakdown[key]}/{maximum}"
            for key, label, maximum in labels
            if key in strength_breakdown
        ]
        if parts:
            lines.append("Desglose: " + "; ".join(parts))
    if strength_factors:
        lines.append(f"Factores: {strength_factors}")
    return "\n".join(lines)


def _level_with_distance(level: float, price: float | None) -> str:
    text = _format_price(level)
    if price is None or price <= 0:
        return text
    distance = (level / price - 1) * 100
    return f"{text} ({distance:+.1f}%)".replace(".", ",")


def _format_range(level: PriceRange) -> str:
    if level.lower == level.upper:
        return _format_price(level.lower)
    return f"{_format_price(level.lower)}-{_format_price(level.upper)}"


def _parse_display_range(value: str) -> PriceRange | None:
    numbers = re.findall(r"\d+(?:[.,]\d+)?", str(value))
    if not numbers:
        return None
    parsed = [float(number.replace(",", ".")) for number in numbers[:2]]
    lower = parsed[0]
    upper = parsed[1] if len(parsed) > 1 else lower
    if lower <= 0 or upper <= 0:
        return None
    return PriceRange(min(lower, upper), max(lower, upper))


def _format_price(value: float) -> str:
    return f"{value:.1f}".replace(".", ",")


def _display_price_value(value: float) -> float:
    return float(f"{value:.1f}")


def _number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            cleaned = value.strip()
            if "," in cleaned and "." in cleaned:
                cleaned = cleaned.replace(".", "").replace(",", ".")
            elif "," in cleaned:
                cleaned = cleaned.replace(",", ".")
            return float(cleaned)
        except ValueError:
            return None
    return None


def _column_with_offset(column: str, offset: int) -> str:
    value = column_to_index(column) + offset + 1
    label = ""
    while value:
        value, remainder = divmod(value - 1, 26)
        label = chr(65 + remainder) + label
    return label


def _rgb(hex_color: str) -> dict[str, float]:
    value = hex_color.removeprefix("#")
    return {
        "red": int(value[0:2], 16) / 255,
        "green": int(value[2:4], 16) / 255,
        "blue": int(value[4:6], 16) / 255,
    }


def _bound_live_range(text: str, displayed: PriceRange | None, extent: Any) -> PriceRange | None:
    if not isinstance(extent, dict) or not isinstance(extent.get('range'), dict):
        return displayed
    zone = extent['range']
    try:
        exact = PriceRange(zone['lower'], zone['upper'])
        if support_validity_floor(exact, extent) is not None and _format_range(exact) == text:
            return exact
    except (KeyError, TypeError, ValueError):
        pass
    return displayed

