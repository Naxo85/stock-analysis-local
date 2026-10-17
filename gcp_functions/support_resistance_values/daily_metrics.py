"""Daily price metrics that remain correct before and during the session."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Iterable


def market_date_for_day_change(now: date | datetime, latest_session: date | datetime) -> date:
    """Keep showing the latest session's move during the weekend."""

    current_date = _as_date(now)
    if current_date.weekday() >= 5:
        return _as_date(latest_session)
    return current_date


def day_change_pct(
    latest_price: float,
    daily_points: Iterable[tuple[Any, float, float, float]],
    *,
    market_date: date,
) -> float | None:
    """Return today's change against the latest completed session close.

    Tradier may omit today's daily candle before the session and include it
    later. Therefore the previous close is the last row before ``market_date``,
    not unconditionally the penultimate row.
    """

    rows = list(daily_points)
    if latest_price <= 0 or not rows:
        return None

    completed_rows = [row for row in rows if _as_date(row[0]) < market_date]
    if not completed_rows:
        return None

    previous_close = float(completed_rows[-1][1])
    if previous_close <= 0:
        return None

    return (float(latest_price) / previous_close - 1.0) * 100.0


def _as_date(value: Any) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])
