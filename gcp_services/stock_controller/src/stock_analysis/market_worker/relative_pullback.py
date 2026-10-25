"""Current QQQ close-to-close swing; no trades, scores or historical display."""
from __future__ import annotations

from datetime import datetime, time, timedelta
from math import isfinite
from zoneinfo import ZoneInfo

from stock_analysis.contracts.market import DailyBar
from stock_analysis.market_worker.session import standard_us_market_holidays

THRESHOLD = 0.05
METHOD = "daily_close_reversal_5pct_v1"
NEW_YORK = ZoneInfo("America/New_York")


def _session(day):
    return day.weekday() < 5 and day not in standard_us_market_holidays(day.year)


def current_pullback(bars: tuple[DailyBar, ...], *, as_of: datetime) -> dict:
    """One alert per decline; rearm only after a 5% rise from its running low.

    Today's daily candle is excluded before 16:00 ET. A missing expected close,
    gap, duplicate, invalid close or unconfirmed starting leg is unavailable.
    Nothing is inferred from the current intraday quote or from a rolling high.
    """
    if as_of.tzinfo is None:
        raise ValueError("as_of must be timezone aware")
    now = as_of.astimezone(NEW_YORK)
    expected = now.date()
    if now.time().replace(tzinfo=None) < time(16):
        expected -= timedelta(days=1)
    while not _session(expected):
        expected -= timedelta(days=1)
    unavailable = {"status": "unavailable", "method": METHOD,
                   "expected_close_date": expected.isoformat()}
    rows = [bar for bar in bars if bar.session_date <= expected]
    if len(rows) < 3:
        return {**unavailable, "reason": "Historial de cierres no disponible"}
    dates = [bar.session_date for bar in rows]
    if dates != sorted(set(dates)) or any(
        not _session(bar.session_date) or not isfinite(bar.close) or bar.close <= 0
        for bar in rows
    ):
        return {**unavailable, "reason": "Historial de cierres inválido"}
    if rows[-1].session_date != expected:
        return {**unavailable, "reason": "Pendiente del último cierre",
                "last_available_close_date": rows[-1].session_date.isoformat()}
    peak = rows[0]
    trough = rows[0]
    declining = False
    synchronized = False
    trigger = None
    previous = rows[0]
    for bar in rows[1:]:
        next_day = previous.session_date + timedelta(days=1)
        while not _session(next_day):
            next_day += timedelta(days=1)
        if bar.session_date != next_day:
            # A gap (including an unmodelled exchange closure) invalidates the
            # current leg until an independently observed down/up cycle resets it.
            peak = trough = bar
            declining = synchronized = False
            trigger = None
        previous = bar
        if not declining:
            if bar.close > peak.close:
                peak = bar
            if bar.close <= peak.close * (1 - THRESHOLD):
                declining = True
                trough = bar
                trigger = bar.session_date
        else:
            if bar.close < trough.close:
                trough = bar
            if bar.close >= trough.close * (1 + THRESHOLD):
                synchronized = True
                declining = False
                peak = bar
                trigger = None
    if not synchronized:
        return {**unavailable, "reason": "Tramo inicial sin confirmar"}
    last = rows[-1]
    return {"status": "ok", "method": METHOD, "source": "Tradier QQQ",
            "close": last.close, "close_date": last.session_date.isoformat(),
            "peak": peak.close, "peak_date": peak.session_date.isoformat(),
            "drawdown": min(0.0, last.close / peak.close - 1),
            "threshold": THRESHOLD, "threshold_price": peak.close * (1 - THRESHOLD),
            "trigger_date": trigger.isoformat() if trigger else None,
            "phase": "open" if declining else "tracking"}
