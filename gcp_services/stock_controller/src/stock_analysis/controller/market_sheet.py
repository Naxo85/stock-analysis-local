from __future__ import annotations

import json
import os
import subprocess
from collections.abc import Iterable
from datetime import date, datetime
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

from stock_analysis.contracts.market import (
    BenchmarkMetrics,
    GeneralMarketOverview,
    MarketSnapshot,
    TickerMetrics,
)
from stock_analysis.controller.sheet_layout import column_to_index
from stock_analysis.controller.sheet_tickers import (
    configured_ticker_rows,
    ordered_block_tickers,
)


def _number_cell(
    value: float | None,
    *,
    pattern: str,
    background: str,
    text_color: str = "#424242",
    note: str | None = None,
) -> dict[str, Any]:
    cell: dict[str, Any] = {
        "userEnteredFormat": {
            "numberFormat": {"type": "NUMBER", "pattern": pattern},
            "backgroundColorStyle": {"rgbColor": _rgb(background)},
            "textFormat": {
                "foregroundColorStyle": {"rgbColor": _rgb(text_color)}
            },
        }
    }
    if value is not None:
        cell["userEnteredValue"] = {"numberValue": value}
    if note is not None:
        cell["note"] = note
    return cell


def _rgb(hex_color: str) -> dict[str, float]:
    value = hex_color.removeprefix("#")
    if len(value) != 6:
        raise ValueError(f"Invalid RGB color: {hex_color!r}")
    return {
        "red": int(value[0:2], 16) / 255,
        "green": int(value[2:4], 16) / 255,
        "blue": int(value[4:6], 16) / 255,
    }


def _threshold_background(
    value: float | int | None,
    rules: list[dict[str, Any]],
    base_background: str,
) -> str:
    if value is None:
        return base_background
    for rule in rules:
        threshold = rule["value"]
        matches = {
            ">": value > threshold,
            ">=": value >= threshold,
            "<=": value <= threshold,
        }.get(rule["operator"])
        if matches is None:
            raise ValueError(f"Unsupported threshold operator: {rule['operator']}")
        if matches:
            return rule["background"]
    return base_background


def _drawdown_background(
    metric: TickerMetrics,
    format_rules: dict[str, Any],
    base_background: str,
) -> str:
    historical = _threshold_background(
        metric.drawdown_percentile,
        format_rules["drawdown_percentile"],
        base_background,
    )
    if historical != base_background:
        return historical
    if (
        metric.distance_from_6m_low is not None
        and metric.distance_from_6m_low <= format_rules["drawdown_near_low_max_distance"]
    ):
        return format_rules["drawdown_near_low_background"]
    return base_background


def metric_cells(
    metric: TickerMetrics,
    *,
    base_background: str,
    format_rules: dict[str, Any],
    as_of: datetime | None = None,
) -> list[dict[str, Any]]:
    day_background = base_background
    day_text = "#424242"
    if metric.day_change is not None and metric.day_change > 0:
        day_background = format_rules["daily_change"]["positive"]["background"]
        day_text = format_rules["daily_change"]["positive"]["text"]
    elif metric.day_change is not None and metric.day_change < 0:
        day_background = format_rules["daily_change"]["negative"]["background"]
        day_text = format_rules["daily_change"]["negative"]["text"]

    quote_note = _cached_quote_note(metric, as_of)
    return [
        _number_cell(
            round(metric.price, 4),
            pattern="0.00",
            background=base_background,
            note=quote_note,
        ),
        _number_cell(
            metric.day_change,
            pattern="0.00%",
            background=day_background,
            text_color=day_text,
            note=quote_note,
        ),
        _number_cell(
            metric.strength,
            pattern="0.00",
            background=_threshold_background(
                metric.strength, format_rules["strength"], base_background
            ),
        ),
        _number_cell(metric.return_5d, pattern="0.00%", background=base_background),
        _number_cell(metric.return_20d, pattern="0.00%", background=base_background),
        _number_cell(
            metric.volatility,
            pattern="0.00%",
            background=_threshold_background(
                metric.volatility, format_rules["volatility"], base_background
            ),
        ),
        _number_cell(
            metric.drawdown_6m,
            pattern="0.00%",
            background=_drawdown_background(metric, format_rules, base_background),
            note="",
        ),
    ]


def build_market_value_requests(
    layout: dict[str, Any],
    snapshot: MarketSnapshot,
    ticker_rows: dict[str, int] | None = None,
) -> list[dict[str, Any]]:
    metrics = {item.ticker: item for item in snapshot.metrics}
    sheet_id = layout["sheet"]["sheet_id"]
    requests = []
    live_rows = (
        ticker_rows if ticker_rows is not None else configured_ticker_rows(layout)
    )

    for block in layout["blocks"]:
        present = [ticker for ticker in block["tickers"] if ticker in metrics]
        if not present:
            continue
        if len(present) != len(block["tickers"]):
            # Never compact partial results into the wrong ticker rows.
            continue

        physical_tickers = ordered_block_tickers(block, live_rows)
        start_row = live_rows[physical_tickers[0]]
        start_column = column_to_index(block["start_column"]) + layout[
            "table_template"
        ].get("metric_start_column_offset", 2)
        rows = []
        for ticker in physical_tickers:
            base_background = block["palette"]["body"]
            rows.append(
                {
                    "values": metric_cells(
                        metrics[ticker],
                        base_background=base_background,
                        format_rules=layout["format_rules"],
                        as_of=snapshot.generated_at,
                    )
                }
            )
        requests.append(
            {
                "updateCells": {
                    "range": {
                        "sheetId": sheet_id,
                        "startRowIndex": start_row,
                        "endRowIndex": start_row + len(rows),
                        "startColumnIndex": start_column,
                        "endColumnIndex": start_column + 7,
                    },
                    "rows": rows,
                    "fields": (
                        "userEnteredValue,note,userEnteredFormat.numberFormat,"
                        "userEnteredFormat.backgroundColorStyle,"
                        "userEnteredFormat.textFormat.foregroundColorStyle"
                    ),
                }
            }
        )
    return requests


def _format_percentage(value: float | None) -> str:
    if value is None:
        return "N/D"
    return f"{value:.1%}".replace(".", ",")


def benchmark_band_text(metric: BenchmarkMetrics) -> str:
    return (
        f"{metric.ticker} | Día {_format_percentage(metric.day_change)}"
        f" | DD6M {_format_percentage(metric.drawdown)}"
        f" | 20d {_format_percentage(metric.return_20d)}"
    )


def _cached_quote_note(
    metric: TickerMetrics | BenchmarkMetrics, as_of: datetime | None
) -> str:
    if not metric.cached:
        return ""
    observed = metric.observed_at.astimezone(ZoneInfo("Europe/Madrid"))
    age = max(
        0,
        int(
            ((as_of or datetime.now(metric.observed_at.tzinfo)) - metric.observed_at)
            .total_seconds()
        ),
    )
    if age < 3600:
        age_text = f"{age // 60} min"
    elif age < 86400:
        age_text = f"{age // 3600} h"
    else:
        days = age // 86400
        age_text = f"{days} día" if days == 1 else f"{days} días"
    return (
        f"Cotización conservada · antigüedad {age_text}\n"
        f"Último dato válido: {observed:%d/%m/%Y %H:%M} Madrid\n"
        f"Fuente original: {metric.source}"
    )


def build_benchmark_value_requests(
    layout: dict[str, Any], snapshot: MarketSnapshot
) -> list[dict[str, Any]]:
    metrics = {item.ticker: item for item in snapshot.benchmarks}
    sheet_id = layout["sheet"]["sheet_id"]
    summary = layout["summary_table"]
    base_background = summary["palette"]["body"]
    rows = []
    for group in layout["groups"]:
        metric = metrics.get(group["benchmark"])
        if metric is None:
            return []
        day_background = base_background
        day_text = "#424242"
        if metric.day_change is not None and metric.day_change > 0:
            day_background = layout["format_rules"]["daily_change"]["positive"]["background"]
            day_text = layout["format_rules"]["daily_change"]["positive"]["text"]
        elif metric.day_change is not None and metric.day_change < 0:
            day_background = layout["format_rules"]["daily_change"]["negative"]["background"]
            day_text = layout["format_rules"]["daily_change"]["negative"]["text"]
        rows.append(
            {
                "values": [
                    _number_cell(
                        metric.day_change,
                        pattern="0.00%",
                        background=day_background,
                        text_color=day_text,
                        note=_cached_quote_note(metric, snapshot.generated_at),
                    ),
                    _number_cell(
                        metric.return_20d,
                        pattern="0.00%",
                        background=base_background,
                    ),
                    _number_cell(
                        metric.drawdown,
                        pattern="0.00%",
                        background=_threshold_background(
                            metric.drawdown_percentile,
                            layout["format_rules"]["drawdown_percentile"],
                            base_background,
                        ),
                    ),
                ]
            }
        )
    start_column = column_to_index(summary["start_column"]) + 3
    return [
        {
            "updateCells": {
                "range": {
                    "sheetId": sheet_id,
                    "startRowIndex": summary["header_row"],
                    "endRowIndex": summary["header_row"] + len(rows),
                    "startColumnIndex": start_column,
                    "endColumnIndex": start_column + 3,
                },
                "rows": rows,
                "fields": (
                    "userEnteredValue,note,userEnteredFormat.numberFormat,"
                    "userEnteredFormat.backgroundColorStyle,"
                    "userEnteredFormat.textFormat.foregroundColorStyle"
                ),
            }
        }
    ]


def _format_date(value: date | None) -> str:
    return value.strftime("%d/%m/%Y") if value else "N/D"


def _latest_market_analysis(
    overview: GeneralMarketOverview,
) -> tuple[date | None, str]:
    candidates = [
        (overview.trading_date, overview.trading_note),
        (overview.core_date, overview.core_note),
    ]
    available = [item for item in candidates if item[0] is not None]
    return max(available, key=lambda item: item[0]) if available else (None, "")


def general_panel_lines(overview: GeneralMarketOverview) -> list[str]:
    risk_dots = {
        "Strong Risk-on": "🟢",
        "Risk-on": "🟢",
        "Mixto": "🟡",
        "Risk-off": "🟠",
        "Strong Risk-off": "🔴",
    }
    risk = (
        f"{risk_dots.get(overview.risk_label, '')} "
        f"{overview.risk_label} {overview.risk_score}/100"
        if overview.risk_label is not None and overview.risk_score is not None
        else "Risk: N/D"
    )
    vxn = f"VXN: {overview.vxn_label}" if overview.vxn_label else "VXN: N/D"
    market_date, _ = _latest_market_analysis(overview)
    return [
        risk,
        vxn,
        "",
        f"QQQ Día: {_format_percentage(overview.qqq_day_change)}",
        f"QQQ 20d: {_format_percentage(overview.qqq_return_20d)}",
        f"Nasdaq: {_format_percentage(overview.qqq_drawdown_6m)} vs máx. 6m",
        "",
        f"Mercado: {_format_date(market_date)}",
        "",
    ]


def _format_decimal(value: float, decimals: int, *, sign: bool = False) -> str:
    prefix = "+" if sign and value >= 0 else ""
    return f"{prefix}{value:.{decimals}f}".replace(".", ",")


def risk_indicator_note(overview: GeneralMarketOverview) -> str:
    if overview.sentiment_observed_at:
        timestamp = overview.sentiment_observed_at.astimezone(
            ZoneInfo("Europe/Madrid")
        ).strftime("%d/%m/%Y %H:%M")
    else:
        timestamp = "fecha no disponible"
    source = overview.sentiment_source or "fuente no disponible"
    return (
        f"Último dato válido: {timestamp}\n"
        f"Fuente del sentimiento: {source}\n"
        "\n"
        "Leyenda del indicador:\n"
        "🟢 76-100: Risk-on fuerte\n"
        "🟢 56-75: Risk-on\n"
        "🟡 45-55: Mixto\n"
        "🟠 25-44: Risk-off\n"
        "🔴 0-24: Risk-off fuerte\n\n"
        "El score parte del Fear & Greed y se ajusta por el VXN."
    )


def vxn_indicator_note(overview: GeneralMarketOverview) -> str:
    if overview.vxn_observed_at:
        timestamp = overview.vxn_observed_at.astimezone(
            ZoneInfo("Europe/Madrid")
        ).strftime("%d/%m/%Y %H:%M")
    else:
        timestamp = "fecha no disponible"
    source = overview.vxn_source or "fuente no disponible"
    if overview.vxn_value is None:
        detail = "VXN: valor no disponible"
    else:
        detail = f"VXN: {_format_decimal(overview.vxn_value, 2)}"
        if overview.vxn_change is not None:
            detail += (
                f" ({_format_decimal(overview.vxn_change * 100, 1, sign=True)}% diario)"
            )
    return (
        f"Último dato válido: {timestamp}\n"
        f"Fuente: {source}\n"
        f"{detail}\n\n"
        "Leyenda del VXN:\n"
        "tranquilo <20\n"
        "normal 20-24,9\n"
        "tensión 25-29,9\n"
        "risk-off 30-34,9\n"
        "shock ≥35"
    )


def general_panel_notes(overview: GeneralMarketOverview) -> list[str]:
    _, market_note = _latest_market_analysis(overview)
    return [
        risk_indicator_note(overview),
        vxn_indicator_note(overview),
        "",
        "",
        "",
        "",
        "",
        market_note,
        "",
    ]


def build_general_panel_requests(
    layout: dict[str, Any], snapshot: MarketSnapshot
) -> list[dict[str, Any]]:
    if snapshot.general is None:
        return []
    panel = layout["general_panel"]
    start_column = column_to_index(panel["column"])
    start_row = panel["start_row"] - 1
    risk_colors = panel["risk_text_colors"]
    bold_lines = set(panel.get("bold_lines", ()))
    partial_bold_prefixes = panel.get("partial_bold_prefixes", {})
    rows = []
    notes = general_panel_notes(snapshot.general)
    # A9:A10 belong exclusively to the analysis completion synchronizer.
    managed_lines = general_panel_lines(snapshot.general)[:7]
    for index, value in enumerate(managed_lines):
        text_color = panel["text_color"]
        if index == 0 and snapshot.general.risk_label:
            text_color = risk_colors.get(snapshot.general.risk_label, text_color)
        line_name = panel["lines"][index]
        prefix = partial_bold_prefixes.get(line_name)
        text_format_runs = []
        if prefix:
            text_format_runs = [
                {"startIndex": 0, "format": {"bold": True}},
                {"startIndex": len(prefix), "format": {"bold": False}},
            ]
        rows.append(
            {
                "values": [
                    {
                        "userEnteredValue": {"stringValue": value},
                        "note": notes[index],
                        "textFormatRuns": text_format_runs,
                        "userEnteredFormat": {
                            "backgroundColorStyle": {
                                "rgbColor": _rgb(panel["background"])
                            },
                            "horizontalAlignment": panel["horizontal_alignment"],
                            "verticalAlignment": "MIDDLE",
                            "wrapStrategy": "CLIP",
                            "textFormat": {
                                "fontFamily": panel["font_family"],
                                "fontSize": panel["font_size"],
                                "foregroundColorStyle": {"rgbColor": _rgb(text_color)},
                                "bold": line_name in bold_lines,
                            },
                        },
                    }
                ]
            }
        )
    return [
        {
            "updateCells": {
                "range": {
                    "sheetId": layout["sheet"]["sheet_id"],
                    "startRowIndex": start_row,
                    "endRowIndex": start_row + len(rows),
                    "startColumnIndex": start_column,
                    "endColumnIndex": start_column + 1,
                },
                "rows": rows,
                "fields": (
                    "userEnteredValue,note,textFormatRuns,"
                    "userEnteredFormat.backgroundColorStyle,"
                    "userEnteredFormat.horizontalAlignment,"
                    "userEnteredFormat.verticalAlignment,userEnteredFormat.wrapStrategy,"
                    "userEnteredFormat.textFormat"
                ),
            }
        }
    ]


class GoogleSheetsRestClient:
    def __init__(
        self,
        access_token: str | None = None,
        service_account: str | None = None,
    ) -> None:
        self._access_token = access_token
        self._service_account = service_account

    def _token(self) -> str:
        if self._access_token is None:
            self._access_token = _google_access_token(self._service_account)
        return self._access_token

    def get_spreadsheet(
        self,
        spreadsheet_id: str,
        *,
        include_grid_data: bool = False,
        ranges: Iterable[str] = (),
    ) -> dict[str, Any]:
        token = self._token()
        query: list[tuple[str, str]] = [
            ("includeGridData", str(include_grid_data).lower())
        ]
        query.extend(("ranges", item) for item in ranges)
        request = Request(
            f"https://sheets.googleapis.com/v4/spreadsheets/{spreadsheet_id}"
            f"?{urlencode(query)}",
            method="GET",
            headers={"Authorization": f"Bearer {token}"},
        )
        try:
            with urlopen(request, timeout=30) as response:
                if response.status >= 300:
                    raise RuntimeError(f"Google Sheets returned HTTP {response.status}")
                return json.loads(response.read().decode("utf-8"))
        except (HTTPError, URLError, TimeoutError) as error:
            raise RuntimeError(f"Google Sheets read failed: {error}") from error

    def batch_update(
        self, spreadsheet_id: str, requests: Iterable[dict[str, Any]]
    ) -> dict[str, Any]:
        token = self._token()
        payload = json.dumps({"requests": list(requests)}).encode("utf-8")
        request = Request(
            f"https://sheets.googleapis.com/v4/spreadsheets/{spreadsheet_id}:batchUpdate",
            data=payload,
            method="POST",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
        )
        try:
            with urlopen(request, timeout=30) as response:
                if response.status >= 300:
                    raise RuntimeError(f"Google Sheets returned HTTP {response.status}")
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as error:
            detail = error.read().decode("utf-8", errors="replace")
            raise RuntimeError(
                f"Google Sheets batch update failed: {error}; {detail}"
            ) from error
        except (URLError, TimeoutError) as error:
            raise RuntimeError(f"Google Sheets batch update failed: {error}") from error

    def batch_get_values(
        self,
        spreadsheet_id: str,
        ranges: Iterable[str],
        *,
        value_render_option: str = "FORMATTED_VALUE",
    ) -> list[dict[str, Any]]:
        token = self._token()
        query: list[tuple[str, str]] = [
            ("majorDimension", "ROWS"),
            ("valueRenderOption", value_render_option),
        ]
        query.extend(("ranges", item) for item in ranges)
        request = Request(
            f"https://sheets.googleapis.com/v4/spreadsheets/{spreadsheet_id}"
            f"/values:batchGet?{urlencode(query)}",
            method="GET",
            headers={"Authorization": f"Bearer {token}"},
        )
        try:
            with urlopen(request, timeout=30) as response:
                if response.status >= 300:
                    raise RuntimeError(f"Google Sheets returned HTTP {response.status}")
                payload = json.loads(response.read().decode("utf-8"))
        except (HTTPError, URLError, TimeoutError) as error:
            raise RuntimeError(f"Google Sheets value read failed: {error}") from error
        return list(payload.get("valueRanges", []))


def _run_gcloud_access_token(command: list[str]) -> str | None:
    try:
        result = subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
            timeout=20,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return result.stdout.strip() or None


def _service_account_access_token(service_account: str) -> str:
    source_token = _run_gcloud_access_token(
        ["gcloud.cmd", "auth", "print-access-token"]
    )
    if source_token is None:
        raise RuntimeError("No gcloud user token available for service account impersonation")

    account = quote(service_account, safe="")
    request = Request(
        "https://iamcredentials.googleapis.com/v1/projects/-/serviceAccounts/"
        f"{account}:generateAccessToken",
        data=json.dumps(
            {
                "scope": ["https://www.googleapis.com/auth/spreadsheets"],
                "lifetime": "3600s",
            }
        ).encode("utf-8"),
        method="POST",
        headers={
            "Authorization": f"Bearer {source_token}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urlopen(request, timeout=30) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError) as error:
        raise RuntimeError(f"Google service account impersonation failed: {error}") from error
    token = str(payload.get("accessToken", "")).strip()
    if not token:
        raise RuntimeError("Google service account impersonation returned no access token")
    return token


def _google_access_token(service_account: str | None = None) -> str:
    configured = os.environ.get("GOOGLE_OAUTH_ACCESS_TOKEN", "").strip()
    if configured:
        return configured
    if service_account:
        try:
            return _service_account_access_token(service_account)
        except RuntimeError:
            pass

    try:
        import google.auth
        from google.auth.exceptions import GoogleAuthError
        from google.auth.transport.requests import Request as GoogleAuthRequest
    except ImportError:
        pass
    else:
        try:
            credentials, _ = google.auth.default(
                scopes=["https://www.googleapis.com/auth/spreadsheets"]
            )
            credentials.refresh(GoogleAuthRequest())
            if credentials.token:
                return credentials.token
        except GoogleAuthError:
            pass

    commands = (
        ["gcloud.cmd", "auth", "application-default", "print-access-token"],
        ["gcloud.cmd", "auth", "print-access-token"],
    )
    for command in commands:
        token = _run_gcloud_access_token(command)
        if token:
            return token
    raise RuntimeError("No Google OAuth token available for Sheets publishing")
