from datetime import date, datetime

import pytest

from gcp_functions.support_resistance_values.daily_metrics import (
    day_change_pct,
    market_date_for_day_change,
)


def _row(day, close):
    return (day, close, close, close)


def test_premarket_uses_last_available_close():
    rows = [_row("2026-07-10", 100), _row("2026-07-13", 110)]

    result = day_change_pct(111, rows, market_date=date(2026, 7, 14))

    assert result == pytest.approx(0.9090909)


def test_intraday_ignores_todays_partial_daily_candle():
    rows = [
        _row("2026-07-10", 100),
        _row("2026-07-13", 110),
        _row("2026-07-14", 108),
    ]

    result = day_change_pct(111, rows, market_date=date(2026, 7, 14))

    assert result == pytest.approx(0.9090909)


def test_date_after_latest_session_compares_with_latest_completed_close():
    rows = [_row("2026-07-09", 95), _row("2026-07-10", 100)]

    result = day_change_pct(100, rows, market_date=date(2026, 7, 11))

    assert result == 0


def test_weekend_keeps_fridays_session_change():
    rows = [_row("2026-07-09", 95), _row("2026-07-10", 100)]
    market_date = market_date_for_day_change(
        datetime(2026, 7, 11, 12),
        datetime(2026, 7, 10, 20),
    )

    result = day_change_pct(100, rows, market_date=market_date)

    assert market_date == date(2026, 7, 10)
    assert result == pytest.approx(5.2631579)


def test_weekday_uses_current_market_date():
    market_date = market_date_for_day_change(
        datetime(2026, 7, 14, 8),
        datetime(2026, 7, 13, 20),
    )

    assert market_date == date(2026, 7, 14)


def test_no_completed_session_returns_none():
    rows = [_row("2026-07-14", 100)]

    assert day_change_pct(101, rows, market_date=date(2026, 7, 14)) is None
