from __future__ import annotations

import importlib.util
import math
import sys
import types
import pytest
from datetime import date, timedelta
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


try:
    from google import genai as _genai  # noqa: F401
except ImportError:
    import google

    genai_stub = types.ModuleType("google.genai")
    genai_types_stub = types.ModuleType("google.genai.types")
    genai_stub.Client = lambda **kwargs: object()
    genai_types_stub.GenerateContentConfig = object
    genai_types_stub.ThinkingConfig = object
    google.genai = genai_stub
    sys.modules["google.genai"] = genai_stub
    sys.modules["google.genai.types"] = genai_types_stub


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


raw = _load(
    "support_resistances_raw_source",
    ROOT / "gcp_functions" / "support_resistances_raw" / "main.py",
)
slim = _load(
    "support_resistances_slim_source",
    ROOT / "gcp_functions" / "support_resistances_slim" / "main.py",
)


def _daily_bars(count: int = 140) -> list[dict]:
    bars = []
    day = date(2025, 1, 2)
    for index in range(count):
        while day.weekday() >= 5:
            day += timedelta(days=1)
        base = 100.0 + ((index % 7) - 3) * 0.2
        if index in {30, 60, 90, 120}:
            low, high, close = 97.9, 100.2, 99.4
        elif index - 1 in {30, 60, 90, 120}:
            low, high, close = 99.5, 102.5, 102.0
        else:
            low, high, close = base - 1.0, base + 1.0, base
        bars.append({
            "date": day.isoformat(),
            "open": base,
            "high": high,
            "low": low,
            "close": close,
            "volume": 2_000_000 if 99.0 <= base <= 101.0 else 500_000,
        })
        day += timedelta(days=1)
    return bars


def test_raw_builds_profile_and_measured_support_reactions():
    bars = _daily_bars()
    profile = raw._build_daily_volume_profile(bars)
    supports = [{"type": "test_support", "level": 98.0, "meta": {"tolerance": 0.5}}]
    walls = [{"level": 100.0}]

    raw._annotate_support_evidence(supports, walls, bars, 2.0, profile)

    assert profile["status"] == "available"
    assert profile["approximate"] is True
    assert profile["poc"]["level"] > 0
    assert len(profile["hvn"]) >= 1
    reaction = supports[0]["meta"]["historical_reaction"]
    assert reaction["status"] == "available"
    assert reaction["test_count"] >= 4
    assert reaction["defense_count"] >= 4
    assert reaction["last_test_date"]
    assert reaction["median_rebound_5d_pct"] > 0
    assert supports[0]["meta"]["volume_profile_proximity"]["status"] == "available"
    assert walls[0]["historical_reaction"]["status"] == "available"


def test_raw_reports_unavailable_instead_of_negative_evidence():
    profile = raw._build_daily_volume_profile(_daily_bars(10))
    reaction = raw._historical_support_reactions(100.0, _daily_bars(10), 2.0)

    assert profile == {
        "status": "unavailable",
        "reason": "fewer_than_20_complete_ohlcv_bars",
        "method": "daily_ohlcv_uniform_range",
        "lookback_sessions": 10,
    }
    assert reaction["status"] == "unavailable"
    assert reaction["reason"] == "insufficient_daily_history"


def test_raw_rejects_non_finite_market_values():
    assert raw._to_float(float("nan")) is None
    assert raw._to_float(float("inf")) is None
    assert raw._to_float(float("-inf")) is None
    assert raw._to_float("12.5") == 12.5

    bars = _daily_bars()
    bars[-1]["volume"] = math.nan
    volume = raw._volume_20d_package(bars, quote={"volume": math.nan})

    assert volume["series"]["shares_20d"][-1] == 0
    assert volume["current_session"] is None


def test_slim_preserves_profile_and_level_evidence_contract():
    bars = _daily_bars()
    profile = raw._build_daily_volume_profile(bars)
    supports = [{"type": "range_bottom_3_6m", "level": 98.0, "meta": {"tolerance": 0.5}}]
    walls = [{"level": 95.0, "expiration": "2026-09-18"}]
    raw._annotate_support_evidence(supports, walls, bars, 2.0, profile)

    result = slim._build_slim({
        "symbol": "TEST",
        "latest_price": 105.0,
        "supports": supports,
        "put_walls_top": walls,
        "volume_profile": profile,
    })

    assert result["volume_profile"]["status"] == "available"
    support_evidence = result["levels"]["supports"][0]["evidence"]
    assert support_evidence["volume_profile"]["nearest_level"] > 0
    assert support_evidence["historical_reaction"]["test_count"] >= 4
    wall_evidence = result["levels"]["put_walls_top"][0]["evidence"]
    assert wall_evidence["volume_profile"]["status"] == "available"


def _isolated_reaction_bars():
    bars = _daily_bars(50)
    for bar in bars:
        bar.update(low=110.0, high=112.0, close=111.0)
    for index in (20, 44):
        bars[index].update(low=99.8, high=100.4, close=100.2)
    for bar in bars[45:]:
        bar.update(low=100.8, high=101.23, close=101.0)
    return bars


@pytest.mark.parametrize("observed", range(6))
@pytest.mark.parametrize("high", [101.23, 103.0])
def test_reaction_waits_for_full_window_for_successes_and_failures(observed, high):
    bars = _isolated_reaction_bars()[:45 + observed]
    for bar in bars[45:]:
        bar["high"] = high
    result = raw._historical_support_reactions(100.0, bars, 4.0)
    complete = observed == 5
    assert result["test_count"] == 1 + int(complete)
    assert result["defense_count"] == 1 + int(complete and high == 103.0)
    assert result["defense_rate_pct"] == (50.0 if complete and high == 101.23 else 100.0)
    assert result["last_test_date"] == bars[44 if complete else 20]["date"]
    assert result["pending_test_count"] == (0 if complete else 1)
    assert result["last_pending_observed_sessions"] == (None if complete else observed)
    assert result["last_test_rebound_5d_pct"] == (round(high - 100, 2) if complete else 12.0)
    assert result["median_rebound_5d_pct"] == (round((12 + high - 100) / 2, 2) if complete else 12.0)


def test_pending_only_is_unavailable_not_zero_defenses_and_survives_slim():
    bars = _isolated_reaction_bars()[:46]
    bars[20].update(low=110.0, high=112.0, close=111.0)
    supports = [{"type": "test_support", "level": 100.0}]
    walls = [{"level": 100.0}]
    raw._annotate_support_evidence(supports, walls, bars, 4.0, {})
    result = slim._build_slim({"symbol": "TEST", "latest_price": 101.0,
                               "supports": supports, "put_walls_top": walls})
    for levels in (result["levels"]["supports"], result["levels"]["put_walls_top"]):
        reaction = levels[0]["evidence"]["historical_reaction"]
        assert reaction["status"] == "unavailable"
        assert reaction.get("test_count") is None
        assert reaction.get("defense_rate_pct") is None
        assert reaction["pending_test_count"] == 1
        assert reaction["last_pending_observed_sessions"] == 1
        assert reaction["last_pending_test_date"] == bars[44]["date"]
        assert reaction["forward_sessions"] == 5
        assert reaction["observation_policy"] == "complete_forward_window_only"


@pytest.mark.parametrize("field,index,value", [
    ("high", 47, None), ("high", 49, float("nan")), ("close", 44, None),
])
def test_incomplete_price_data_is_not_a_completed_failed_defense(field, index, value):
    bars = _isolated_reaction_bars()
    bars[index][field] = value
    result = raw._historical_support_reactions(100.0, bars, 4.0)
    assert result["test_count"] == 1
    assert result["defense_rate_pct"] == 100.0
    assert result["excluded_incomplete_data_test_count"] == 1


def test_current_session_cannot_complete_the_five_session_window():
    bars = _isolated_reaction_bars()
    bars[-1]["date"] = raw.datetime.now(raw.timezone.utc).date().isoformat()
    result = raw._historical_support_reactions(100.0, bars, 4.0)
    assert result["test_count"] == 1
    assert result["last_pending_observed_sessions"] == 4


def test_full_window_can_confirm_failure_and_later_bars_do_not_rewrite_it():
    bars = _isolated_reaction_bars()
    before = raw._historical_support_reactions(100.0, bars, 4.0)
    extra = dict(bars[-1], date="2025-06-01", high=120.0, low=110.0, close=115.0)
    after = raw._historical_support_reactions(100.0, bars + [extra], 4.0)
    assert before["defense_count"] == after["defense_count"] == 1
    assert before["test_count"] == after["test_count"] == 2
    assert before["last_test_rebound_5d_pct"] == after["last_test_rebound_5d_pct"] == 1.23
