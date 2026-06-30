"""Maintain current analyst ratings per ticker from parsed IBKR headlines."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from statistics import mean, median
from typing import Any


DEFAULT_MAX_AGE_DAYS = 180
MEDIUM_COVERAGE_DAYS = 90
FIRM_ALIASES = {
    "keybanc": "KeyBanc Capital Markets",
    "key banc": "KeyBanc Capital Markets",
    "keybanc capital markets": "KeyBanc Capital Markets",
    "keybanc capital": "KeyBanc Capital Markets",
}


def build_empty_ratings_state(
    *,
    symbol: str,
    now: datetime,
    previous_earnings_date: str | None = None,
    next_earnings_date: str | None = None,
) -> dict[str, Any]:
    return {
        "source": "IBKR_ANALYST_RATINGS",
        "ticker": symbol.strip().upper(),
        "as_of": now.isoformat(),
        "earnings": {
            "previous_earnings_date": previous_earnings_date,
            "next_earnings_date": next_earnings_date,
        },
        "firms": {},
        "summary_active": _empty_summary("none"),
    }


def apply_probe_payload(
    state: dict[str, Any],
    payload: dict[str, Any],
    *,
    now: datetime,
) -> dict[str, Any]:
    updated = dict(state)
    updated["as_of"] = now.isoformat()
    firms = _canonicalize_firms(dict(updated.get("firms") or {}))

    for item in payload.get("headlines") or []:
        action = item.get("analyst_action")
        if not isinstance(action, dict) or action.get("parse_status") != "parsed":
            continue

        firm_name = _canonical_firm_name(action.get("firm"))
        if not firm_name:
            continue

        current = dict(firms.get(firm_name) or _empty_firm(firm_name))
        event_time = _normalize_datetime(item.get("published_at_raw"))
        event_record = {
            "published_at": event_time,
            "providerCode": item.get("providerCode"),
            "articleId": item.get("articleId"),
            "headline": item.get("headline_clean"),
            "event_type": action.get("event_type"),
        }

        if action.get("rating"):
            current["rating"] = action.get("rating")
            current["rating_bucket"] = action.get("rating_bucket") or "unknown"
            current["rating_last_updated"] = event_time

        if action.get("target") is not None:
            current["target"] = action.get("target")
            current["target_last_updated"] = event_time
            current["target_last_event"] = event_record

        if action.get("previous_target") is not None:
            current["previous_target"] = action.get("previous_target")
            current["target_prior_to_last_change"] = action.get("previous_target")

        current["last_updated"] = _max_iso_datetime(
            current.get("last_updated"),
            event_time,
        )
        current["last_provider"] = item.get("providerCode")
        current["last_headline"] = item.get("headline_clean")
        current["last_article_ids"] = _append_unique(
            current.get("last_article_ids") or [],
            item.get("articleId"),
            limit=10,
        )
        current["events_seen"] = int(current.get("events_seen") or 0) + 1
        current["last_event"] = event_record
        firms[firm_name] = current

    updated["firms"] = _canonicalize_firms(firms)
    updated["summary_active"] = summarize_active_ratings(updated, now=now)
    return updated


def summarize_active_ratings(
    state: dict[str, Any],
    *,
    now: datetime,
    max_age_days: int = DEFAULT_MAX_AGE_DAYS,
) -> dict[str, Any]:
    firms = list(_canonicalize_firms(state.get("firms") or {}).values())
    previous_earnings_date = (state.get("earnings") or {}).get(
        "previous_earnings_date"
    )
    active = _choose_active_firms(
        firms,
        now=now,
        previous_earnings_date=previous_earnings_date,
        max_age_days=max_age_days,
    )
    basis = _summary_basis(
        active,
        previous_earnings_date=previous_earnings_date,
        now=now,
    )

    if not active:
        return _empty_summary(basis)

    rating_counts = {"buy": 0, "hold": 0, "sell": 0, "unknown": 0}
    for firm in active:
        bucket = firm.get("rating_bucket") or "unknown"
        rating_counts[bucket] = rating_counts.get(bucket, 0) + 1

    targets = [
        float(firm["target"])
        for firm in active
        if isinstance(firm.get("target"), (int, float))
    ]

    stale_count = len(firms) - len(active)
    quality = _quality_for_active(active, basis=basis)

    return {
        "basis": basis,
        "quality": quality,
        "active_firm_count": len(active),
        "stale_or_excluded_count": stale_count,
        "rating_counts": rating_counts,
        "target_count": len(targets),
        "target_low": min(targets) if targets else None,
        "target_high": max(targets) if targets else None,
        "target_mean": round(mean(targets), 2) if targets else None,
        "target_median": median(targets) if targets else None,
        "firms": sorted(firm["firm"] for firm in active),
    }


def _choose_active_firms(
    firms: list[dict[str, Any]],
    *,
    now: datetime,
    previous_earnings_date: str | None,
    max_age_days: int,
) -> list[dict[str, Any]]:
    recent_180 = _firms_since(firms, now.date() - timedelta(days=max_age_days))

    if not previous_earnings_date:
        return recent_180

    earnings_date = _parse_date(previous_earnings_date)
    if earnings_date is None:
        return recent_180

    post_earnings = _firms_since(firms, earnings_date)

    if len(post_earnings) >= 8:
        return post_earnings

    if len(post_earnings) >= 4:
        return _merge_firms(post_earnings, _firms_since(firms, now.date() - timedelta(days=MEDIUM_COVERAGE_DAYS)))

    if post_earnings:
        return _merge_firms(post_earnings, recent_180)

    return recent_180


def _summary_basis(
    active: list[dict[str, Any]],
    *,
    previous_earnings_date: str | None,
    now: datetime,
) -> str:
    if not previous_earnings_date:
        return "recent_180d_no_earnings_date"

    earnings_date = _parse_date(previous_earnings_date)
    if earnings_date is None:
        return "recent_180d_invalid_earnings_date"

    post_count = len(_firms_since(active, earnings_date))

    if post_count >= 8 and post_count == len(active):
        return "post_earnings_only"
    if post_count >= 4:
        return "post_earnings_plus_90d"
    if post_count >= 1:
        return "post_earnings_plus_180d"
    return "recent_180d_no_post_earnings_updates"


def _quality_for_active(active: list[dict[str, Any]], *, basis: str) -> str:
    count = len(active)

    if count >= 8 and basis == "post_earnings_only":
        return "high"
    if count >= 4:
        return "medium"
    if count >= 1:
        return "low"
    return "none"


def _firms_since(firms: list[dict[str, Any]], threshold: date) -> list[dict[str, Any]]:
    return [
        firm
        for firm in firms
        if (firm_date := _firm_last_updated_date(firm)) is not None
        and firm_date >= threshold
    ]


def _merge_firms(
    first: list[dict[str, Any]],
    second: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    merged = {firm["firm"]: firm for firm in second}
    merged.update({firm["firm"]: firm for firm in first})
    return list(merged.values())


def _firm_last_updated_date(firm: dict[str, Any]) -> date | None:
    value = _parse_datetime(firm.get("last_updated"))
    return value.date() if value else None


def _canonicalize_firms(firms: dict[str, Any]) -> dict[str, dict[str, Any]]:
    canonical: dict[str, dict[str, Any]] = {}

    for raw_name, raw_firm in firms.items():
        if not isinstance(raw_firm, dict):
            continue

        firm_name = _canonical_firm_name(raw_firm.get("firm") or raw_name)
        if not firm_name:
            continue

        firm = dict(raw_firm)
        firm["firm"] = firm_name

        if firm_name in canonical:
            canonical[firm_name] = _merge_firm_states(canonical[firm_name], firm)
        else:
            canonical[firm_name] = firm

    return canonical


def _canonical_firm_name(value: Any) -> str:
    cleaned = _clean_firm(value)
    if not cleaned:
        return ""

    return FIRM_ALIASES.get(_firm_alias_key(cleaned), cleaned)


def _firm_alias_key(value: Any) -> str:
    text = _clean_firm(value).lower()
    return " ".join(text.replace("&", " and ").replace("-", " ").split())


def _merge_firm_states(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    merged = dict(left)
    merged["firm"] = _canonical_firm_name(left.get("firm") or right.get("firm"))

    if _is_newer(right.get("rating_last_updated"), left.get("rating_last_updated")):
        for key in ("rating", "rating_bucket", "rating_last_updated"):
            merged[key] = right.get(key)
    elif not merged.get("rating") and right.get("rating"):
        for key in ("rating", "rating_bucket", "rating_last_updated"):
            merged[key] = right.get(key)

    if _is_newer(right.get("target_last_updated"), left.get("target_last_updated")):
        for key in (
            "target",
            "previous_target",
            "target_prior_to_last_change",
            "target_last_updated",
            "target_last_event",
        ):
            merged[key] = right.get(key)
    elif merged.get("target") is None and right.get("target") is not None:
        for key in (
            "target",
            "previous_target",
            "target_prior_to_last_change",
            "target_last_updated",
            "target_last_event",
        ):
            merged[key] = right.get(key)

    if _is_newer(right.get("last_updated"), left.get("last_updated")):
        for key in ("last_updated", "last_provider", "last_headline", "last_event"):
            merged[key] = right.get(key)
    else:
        merged["last_updated"] = _max_iso_datetime(
            left.get("last_updated"),
            right.get("last_updated"),
        )

    article_ids = list(left.get("last_article_ids") or [])
    for article_id in right.get("last_article_ids") or []:
        article_ids = _append_unique(article_ids, article_id, limit=10)
    merged["last_article_ids"] = article_ids
    merged["events_seen"] = int(left.get("events_seen") or 0) + int(
        right.get("events_seen") or 0
    )

    return merged


def _is_newer(left: Any, right: Any) -> bool:
    left_dt = _parse_datetime(left)
    right_dt = _parse_datetime(right)

    if left_dt and right_dt:
        return left_dt > right_dt
    return bool(left_dt and not right_dt)


def _empty_firm(firm: str) -> dict[str, Any]:
    return {
        "firm": firm,
        "rating": None,
        "rating_bucket": "unknown",
        "target": None,
        "previous_target": None,
        "target_prior_to_last_change": None,
        "last_updated": None,
        "rating_last_updated": None,
        "target_last_updated": None,
        "target_last_event": None,
        "last_provider": None,
        "last_headline": None,
        "last_article_ids": [],
        "events_seen": 0,
    }


def _empty_summary(basis: str) -> dict[str, Any]:
    return {
        "basis": basis,
        "quality": "none",
        "active_firm_count": 0,
        "stale_or_excluded_count": 0,
        "rating_counts": {"buy": 0, "hold": 0, "sell": 0, "unknown": 0},
        "target_count": 0,
        "target_low": None,
        "target_high": None,
        "target_mean": None,
        "target_median": None,
        "firms": [],
    }


def _append_unique(values: list[Any], value: Any, *, limit: int) -> list[Any]:
    if value is None:
        return values[-limit:]

    output = [item for item in values if item != value]
    output.append(value)
    return output[-limit:]


def _max_iso_datetime(left: Any, right: Any) -> str | None:
    left_dt = _parse_datetime(left)
    right_dt = _parse_datetime(right)

    if left_dt and right_dt:
        return max(left_dt, right_dt).isoformat()
    if right_dt:
        return right_dt.isoformat()
    if left_dt:
        return left_dt.isoformat()
    return None


def _normalize_datetime(value: Any) -> str | None:
    parsed = _parse_datetime(value)
    return parsed.isoformat() if parsed else None


def _parse_datetime(value: Any) -> datetime | None:
    if value is None:
        return None

    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    text = str(value).strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"

    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None

    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)

    return parsed.astimezone(timezone.utc)


def _parse_date(value: Any) -> date | None:
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _clean_firm(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()
