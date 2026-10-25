"""Descriptive horizontal-price paths; no support score, fill or trading rule.

Input bars must already be completed sessions in chronological order. The
contact-session OHLC cannot establish the order of a hypothetical fill and an
extreme, so all path measurements start at its observed close and use later
sessions only. This does not backdate knowledge of the level or reconstruct an
AVWAP curve / historical option inventory.
"""
from __future__ import annotations

import math
from datetime import date, timedelta
from statistics import median

try:
    from .market_sessions import market_session
except ImportError:
    try:
        from gcp_functions.support_resistances_raw.market_sessions import market_session
    except ImportError:  # Cloud Functions source directory.
        from market_sessions import market_session


def _number(value):
    return (float(value) if isinstance(value, (int, float))
            and not isinstance(value, bool) and math.isfinite(value) else None)


def horizontal_path_evidence(level, bars, tolerance, *, forward_sessions=5,
                             max_events=3, extra_closures=()):
    """Describe calendar-complete contacts, with bounded detail for the model.

    Missing expected sessions are unavailable data, never inferred failures.
    extra_closures contains explicitly supplied ISO dates, as in market_session.
    """
    level, tolerance = _number(level), _number(tolerance)
    if level is None or level <= 0 or tolerance is None or tolerance < 0:
        return {"status": "unavailable", "reason": "invalid_coordinate_or_tolerance"}
    if type(forward_sessions) is not int or forward_sessions < 1:
        raise ValueError("forward_sessions_must_be_positive_integer")
    if type(max_events) is not int or max_events < 0:
        raise ValueError("max_events_must_be_nonnegative_integer")
    dates = [str(row.get("date") or "")[:10] for row in bars]
    if any(not day for day in dates) or dates != sorted(set(dates)):
        return {"status": "unavailable", "reason": "invalid_session_order"}
    try:
        session_dates = [date.fromisoformat(day) for day in dates]
    except ValueError:
        return {"status": "unavailable", "reason": "invalid_session_date"}
    extra_closures = tuple(extra_closures)
    events, pending, invalid, previous_touch = [], 0, 0, False
    contacts = []
    for index, row in enumerate(bars):
        low, high = _number(row.get("low")), _number(row.get("high"))
        touched = (low is not None and high is not None and low <= high
                   and low <= level + tolerance and high >= level - tolerance)
        if touched and not previous_touch:
            contacts.append(index)
        previous_touch = touched
    for index in contacts:
        contact = [_number(bars[index].get(k)) for k in ("low", "high", "close")]
        if (not market_session(session_dates[index], extra_closures)
                or any(value is None or value <= 0 for value in contact)
                or not contact[0] <= contact[2] <= contact[1]):
            invalid += 1
            continue
        origin = contact[2]
        future = bars[index + 1:index + 1 + forward_sessions]
        expected = []
        day = session_dates[index]
        while len(expected) < forward_sessions:
            day += timedelta(days=1)
            if market_session(day, extra_closures):
                expected.append(day)
        observed = session_dates[index + 1:index + 1 + forward_sessions]
        if observed != expected[:len(observed)]:
            invalid += 1
            continue
        if len(future) < forward_sessions:
            pending += 1
            continue
        values = [[_number(row.get(k)) for k in ("low", "high", "close")]
                  for row in future]
        if (any(
                any(x is None or x <= 0 for x in row)
                or not row[0] <= row[2] <= row[1] for row in values)):
            invalid += 1
            continue
        lows, highs, closes = zip(*values)
        high, low = max(highs), min(lows)
        hi_at, lo_at = highs.index(high) + 1, lows.index(low) + 1
        prior = _number(bars[index - 1].get("close")) if index else None
        direction = ("unknown" if prior is None else
                     "from_above" if prior > level + tolerance else
                     "from_below" if prior < level - tolerance else
                     "prior_close_inside_band")
        order = ("same_session_unknown" if hi_at == lo_at else
                 "favorable_extreme_first" if hi_at < lo_at else
                 "adverse_extreme_first")
        events.append({
            "contact_date": dates[index], "window_end": dates[index + forward_sessions],
            "contact_close": origin, "approach": direction,
            "favorable_excursion_pct": round(max(0.0, 100 * (high / origin - 1)), 6),
            "adverse_excursion_pct": round(max(0.0, 100 * (1 - low / origin)), 6),
            "terminal_close_return_pct": round(100 * (closes[-1] / origin - 1), 6),
            "favorable_extreme_session": hi_at, "adverse_extreme_session": lo_at,
            "extreme_order": order,
            "first_close_at_or_above_contact_close_session": next(
                (j for j, value in enumerate(closes, 1) if value >= origin), None),
            "overlaps_previous_window": bool(events and
                dates[index] <= events[-1]["window_end"]),
        })
    result = {
        "status": "available" if events else "unavailable",
        "method": "horizontal_coordinate_post_contact_close_path_v40",
        "measurement_origin": "contact_session_close",
        "scope": "Horizontal coordinate, not a historical AVWAP curve or option inventory; descriptive, not ex-ante validation or executed trades.",
        "intraday_order": "unknown_with_daily_bars",
        "forward_sessions": forward_sessions,
        "coordinate": level, "tolerance_abs": tolerance,
        "history_first_session": dates[0] if dates else None,
        "history_last_session": dates[-1] if dates else None,
        "contact_count": len(contacts), "completed_count": len(events),
        "pending_count": pending, "incomplete_data_count": invalid,
        "overlapping_window_count": sum(e["overlaps_previous_window"] for e in events),
        "independent_trials_assumed": False,
        "summary_scope": "all_completed_contacts",
        "event_detail_selection": "latest_completed_contacts",
        "negative_terminal_count": sum(e["terminal_close_return_pct"] < 0 for e in events),
        "positive_excursion_negative_terminal_count": sum(
            e["favorable_excursion_pct"] > 0 and e["terminal_close_return_pct"] < 0
            for e in events),
        "adverse_extreme_first_count": sum(
            e["extreme_order"] == "adverse_extreme_first" for e in events),
        "same_session_extremes_count": sum(
            e["extreme_order"] == "same_session_unknown" for e in events),
        "events": events[-max_events:] if max_events else [],
        "events_omitted": max(0, len(events) - max_events),
    }
    if events:
        result["max_adverse_excursion_pct"] = max(e["adverse_excursion_pct"] for e in events)
        result["min_terminal_close_return_pct"] = min(e["terminal_close_return_pct"] for e in events)
        for key in ("favorable_excursion_pct", "adverse_excursion_pct", "terminal_close_return_pct"):
            result["median_" + key] = round(median(e[key] for e in events), 6)
    else:
        result["reason"] = "no_complete_path_observations"
    return result
