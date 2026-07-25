import pytest

from gcp_functions.support_resistance_values.drawdown_metrics import relative_drawdown_6m


def _points(closes):
    return [
        (f"2026-01-{index + 1:04d}", close, close, close)
        for index, close in enumerate(closes)
    ]


def test_new_high_has_zero_drawdown_and_zero_percentile():
    result = relative_drawdown_6m(150, _points(range(100, 150)), lookback=20)

    assert result["pct_from_high"] == 0
    assert result["percentile"] == 0
    assert result["peak_date"] is None


def test_metric_is_invariant_to_ticker_price_scale():
    closes = [100 + (index % 20) - index * 0.03 for index in range(200)]

    base = relative_drawdown_6m(91, _points(closes), lookback=30, history_sessions=100)
    scaled = relative_drawdown_6m(
        910,
        _points([value * 10 for value in closes]),
        lookback=30,
        history_sessions=100,
    )

    assert scaled["pct_from_high"] == base["pct_from_high"]
    assert scaled["percentile"] == base["percentile"]


def test_old_peak_outside_six_month_window_is_ignored():
    closes = [500] + [100 + index for index in range(1, 160)]

    result = relative_drawdown_6m(260, _points(closes), lookback=126)

    assert result["pct_from_high"] == 0
    assert result["peak_value"] == 260


def test_percentile_rises_for_unusually_deep_current_drawdown():
    closes = [100 + (index % 10) for index in range(300)]

    result = relative_drawdown_6m(70, _points(closes), lookback=30, history_sessions=200)

    assert result["pct_from_high"] < -30
    assert result["percentile"] >= 99
    assert result["samples"] == 200


def test_short_history_keeps_raw_drawdown_but_omits_percentile():
    result = relative_drawdown_6m(90, _points([100, 95]), lookback=126)

    assert result["pct_from_high"] == pytest.approx(-10)
    assert result["percentile"] is None
    assert result["samples"] == 0
