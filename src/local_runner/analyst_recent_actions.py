"""Recent analyst actions for the daily AI prompt.

This is intentionally different from the aggregate analyst consensus summary.
The consensus is for Sheets/display; this module only exposes analyst actions
that happened after the previous analysis, so the daily model sees fresh events
without being nudged by old consensus data.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_LIMIT = 8


def load_recent_analyst_actions(
    repo_root: Path,
    symbol: str,
    *,
    since: str | None,
    limit: int = DEFAULT_LIMIT,
) -> dict[str, Any]:
    if not since:
        return {
            "status": "unavailable",
            "reason": "missing_previous_analysis_timestamp",
            "since": None,
            "actions": [],
        }

    since_dt = _parse_datetime(since)
    if since_dt is None:
        return {
            "status": "unavailable",
            "reason": "invalid_previous_analysis_timestamp",
            "since": since,
            "actions": [],
        }

    state_path = repo_root / "data" / "analyst_ratings" / symbol.strip().upper() / "current.json"
    if not state_path.exists():
        return {
            "status": "unavailable",
            "reason": "missing_current_json",
            "since": since_dt.isoformat(),
            "actions": [],
        }

    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {
            "status": "unavailable",
            "reason": "invalid_current_json",
            "since": since_dt.isoformat(),
            "actions": [],
        }

    actions = _collect_recent_actions(state, since_dt)
    actions = sorted(actions, key=lambda item: item["published_at"], reverse=True)

    return {
        "status": "ok",
        "source": state.get("source") or "IBKR_ANALYST_RATINGS",
        "as_of": state.get("as_of"),
        "since": since_dt.isoformat(),
        "count": len(actions),
        "actions": actions[:limit],
        "truncated": len(actions) > limit,
    }


def format_recent_analyst_actions_for_prompt(payload: dict[str, Any]) -> str:
    if payload.get("status") != "ok":
        return (
            f"No hay acciones recientes de analistas disponibles. "
            f"Motivo: {payload.get('reason', 'unknown')}."
        )

    actions = payload.get("actions")
    if not isinstance(actions, list) or not actions:
        return (
            "No hay acciones recientes de analistas desde el informe anterior "
            f"({payload.get('since')})."
        )

    lines = [f"Acciones recientes de analistas desde {_short_date(payload.get('since'))}:"]

    for action in _compact_actions(actions):
        lines.append(f"- {action}")

    if payload.get("truncated"):
        lines.append("- Lista truncada; hay más acciones recientes en el estado local.")

    return "\n".join(lines)


def _collect_recent_actions(state: dict[str, Any], since: datetime) -> list[dict[str, Any]]:
    firms = state.get("firms")
    if not isinstance(firms, dict):
        return []

    actions: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()

    for firm in firms.values():
        if not isinstance(firm, dict):
            continue

        for event_key in ("last_event", "target_last_event"):
            event = firm.get(event_key)
            if not isinstance(event, dict):
                continue

            published_at = _parse_datetime(event.get("published_at"))
            if published_at is None or published_at <= since:
                continue

            dedupe_key = (
                str(event.get("articleId") or ""),
                str(firm.get("firm") or ""),
                str(event.get("headline") or ""),
            )
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)

            actions.append(
                {
                    "published_at": published_at.isoformat(),
                    "firm": firm.get("firm"),
                    "event_type": event.get("event_type"),
                    "rating": firm.get("rating"),
                    "rating_bucket": firm.get("rating_bucket"),
                    "target": firm.get("target"),
                    "headline": event.get("headline"),
                    "articleId": event.get("articleId"),
                    "providerCode": event.get("providerCode"),
                }
            )

    return actions


def _parse_datetime(value: Any) -> datetime | None:
    if not value:
        return None

    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)

    return parsed.astimezone(timezone.utc)


def _rating_text(action: dict[str, Any]) -> str:
    rating = action.get("rating")
    bucket = action.get("rating_bucket")
    if rating and bucket:
        return f"rating={rating} ({bucket})"
    if rating:
        return f"rating={rating}"
    return ""


def _target_text(action: dict[str, Any]) -> str:
    target = action.get("target")
    if isinstance(target, (int, float)):
        return f"target={target:g}"
    return ""


def _compact_actions(actions: list[Any]) -> list[str]:
    grouped: dict[tuple[str, str], dict[str, Any]] = {}
    for action in actions:
        if not isinstance(action, dict):
            continue
        key = (_short_date(action.get("published_at")), str(action.get("firm") or ""))
        current = grouped.setdefault(
            key,
            {
                "date": key[0],
                "firm": key[1],
                "event_types": [],
                "rating": None,
                "rating_bucket": None,
                "target": None,
            },
        )
        event_type = action.get("event_type")
        if event_type and event_type not in current["event_types"]:
            current["event_types"].append(event_type)
        if action.get("rating"):
            current["rating"] = action.get("rating")
            current["rating_bucket"] = action.get("rating_bucket")
        if action.get("target") is not None:
            current["target"] = action.get("target")

    return [_compact_action_line(item) for item in grouped.values()]


def _compact_action_line(item: dict[str, Any]) -> str:
    details = []
    event_types = set(item.get("event_types") or [])
    if item.get("rating"):
        verb = "mantiene" if "rating_maintained" in event_types else "rating"
        bucket = f" ({item.get('rating_bucket')})" if item.get("rating_bucket") else ""
        details.append(f"{verb} {item['rating']}{bucket}")
    if item.get("target") is not None:
        if "price_target_raised" in event_types:
            details.append(f"sube PT a {item['target']:g}")
        elif "price_target_lowered" in event_types:
            details.append(f"baja PT a {item['target']:g}")
        else:
            details.append(f"PT {item['target']:g}")
    if not details:
        details.append(", ".join(sorted(event_types)) or "acción reciente")
    return f"{item.get('date')} | {item.get('firm')} | " + "; ".join(details)


def _short_date(value: Any) -> str:
    text = str(value or "")
    return text[:10] if len(text) >= 10 else text
