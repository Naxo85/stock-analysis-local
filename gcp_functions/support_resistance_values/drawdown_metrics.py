"""Ticker-relative rolling drawdown metrics.

The displayed score is a severity percentile, not a buy signal. A value of
90 means that the current six-month drawdown is deeper than roughly 90% of
the ticker's comparable observations in the selected history.
"""

from __future__ import annotations

from typing import Any, Iterable


TRADING_DAYS_6M = 126
TRADING_DAYS_3Y = 756


def relative_drawdown_6m(
    latest_price: float,
    daily_points: Iterable[tuple[Any, float, float, float]],
    *,
    lookback: int = TRADING_DAYS_6M,
    history_sessions: int = TRADING_DAYS_3Y,
) -> dict[str, Any]:
    """Calculate the current six-month drawdown and its own-history percentile.

    Rolling peaks use closing prices so that the current and historical
    observations are comparable. The live price is included in the current
    window, making a new live high a drawdown of exactly zero.
    """

    rows = list(daily_points)
    if latest_price <= 0 or not rows or lookback < 2 or history_sessions < 1:
        return _empty_result()

    closes = [float(row[1]) for row in rows if float(row[1]) > 0]
    if not closes:
        return _empty_result()

    current_rows = rows[-lookback:]
    peak_row = max(current_rows, key=lambda row: float(row[1]))
    historical_peak = float(peak_row[1])

    if latest_price >= historical_peak:
        peak_value = float(latest_price)
        peak_date = None
    else:
        peak_value = historical_peak
        peak_date = peak_row[0]

    current_severity = max(0.0, 1.0 - float(latest_price) / peak_value)
    raw_pct = -100.0 * current_severity

    if len(closes) < lookback:
        return {
            "pct_from_high": raw_pct,
            "peak_value": peak_value,
            "peak_date": peak_date,
            "percentile": None,
            "samples": 0,
        }

    first_index = max(lookback - 1, len(closes) - history_sessions)
    historical_severities: list[float] = []

    for index in range(first_index, len(closes)):
        window = closes[index - lookback + 1 : index + 1]
        rolling_peak = max(window)
        historical_severities.append(max(0.0, 1.0 - closes[index] / rolling_peak))

    if not historical_severities:
        percentile = None
    elif current_severity <= 0:
        percentile = 0.0
    else:
        less_severe = sum(value < current_severity for value in historical_severities)
        percentile = 100.0 * less_severe / len(historical_severities)

    return {
        "pct_from_high": raw_pct,
        "peak_value": peak_value,
        "peak_date": peak_date,
        "percentile": percentile,
        "samples": len(historical_severities),
    }


def _empty_result() -> dict[str, Any]:
    return {
        "pct_from_high": None,
        "peak_value": None,
        "peak_date": None,
        "percentile": None,
        "samples": 0,
    }
