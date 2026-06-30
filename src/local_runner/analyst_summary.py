"""Compact analyst summary for report JSON, prompts, and Sheets."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_compact_analyst_summary(repo_root: Path, symbol: str) -> dict[str, Any]:
    path = repo_root / "data" / "analyst_ratings" / symbol.strip().upper() / "current.json"

    if not path.exists():
        return {
            "status": "unavailable",
            "reason": "missing_current_json",
        }

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {
            "status": "unavailable",
            "reason": "invalid_current_json",
        }

    if not isinstance(payload, dict):
        return {
            "status": "unavailable",
            "reason": "current_json_not_object",
        }

    return compact_analyst_summary(payload)


def compact_analyst_summary(payload: dict[str, Any]) -> dict[str, Any]:
    summary = payload.get("summary_active") or {}
    earnings = payload.get("earnings") or {}

    if not isinstance(summary, dict) or not summary:
        return {
            "status": "unavailable",
            "reason": "missing_summary_active",
        }

    return {
        "status": "ok",
        "source": payload.get("source") or "IBKR_ANALYST_RATINGS",
        "as_of": payload.get("as_of"),
        "basis": summary.get("basis"),
        "quality": summary.get("quality"),
        "active_firm_count": summary.get("active_firm_count"),
        "stale_or_excluded_count": summary.get("stale_or_excluded_count"),
        "rating_counts": _rating_counts(summary.get("rating_counts")),
        "target_count": summary.get("target_count"),
        "target_low": summary.get("target_low"),
        "target_high": summary.get("target_high"),
        "target_mean": summary.get("target_mean"),
        "target_median": summary.get("target_median"),
        "previous_earnings_date": earnings.get("previous_earnings_date"),
        "next_earnings_date": earnings.get("next_earnings_date"),
    }


def format_analyst_summary_for_sheet(summary: dict[str, Any]) -> str:
    if not isinstance(summary, dict) or summary.get("status") != "ok":
        return ""

    quality = str(summary.get("quality") or "")
    if quality in ("none", ""):
        return ""

    target_median = _number(summary.get("target_median"))
    rating_counts = _rating_counts(summary.get("rating_counts"))

    parts: list[str] = []

    if target_median is not None:
        parts.append(_format_price(target_median))

    parts.append(f"{rating_counts['buy']}-{rating_counts['hold']}-{rating_counts['sell']}")

    return " | ".join(parts)


def _rating_counts(value: Any) -> dict[str, int]:
    value = value if isinstance(value, dict) else {}
    return {
        "buy": _integer(value.get("buy")) or 0,
        "hold": _integer(value.get("hold")) or 0,
        "sell": _integer(value.get("sell")) or 0,
        "unknown": _integer(value.get("unknown")) or 0,
    }


def _number(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _integer(value: Any) -> int | None:
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return None


def _format_price(value: float) -> str:
    if float(value).is_integer():
        return str(int(value))
    return f"{value:.1f}"
