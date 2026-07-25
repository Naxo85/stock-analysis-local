from datetime import date

import pytest

from gcp_functions.support_resistance_values.daily_metrics import day_change_pct


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


def test_weekend_uses_fridays_close():
    rows = [_row("2026-07-09", 95), _row("2026-07-10", 100)]

    result = day_change_pct(100, rows, market_date=date(2026, 7, 11))

    assert result == 0


def test_no_completed_session_returns_none():
    rows = [_row("2026-07-14", 100)]

    assert day_change_pct(101, rows, market_date=date(2026, 7, 14)) is None
