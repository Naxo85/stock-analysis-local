"""Compact recent IBKR news for the daily AI prompt."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


DEFAULT_PROMPT_LIMIT = 15


def load_recent_news(repo_root: Path, symbol: str) -> dict[str, Any]:
    path = repo_root / "data" / "ibkr_news_recent" / symbol.strip().upper() / "latest.json"

    if not path.exists():
        return {
            "status": "unavailable",
            "reason": "missing_recent_news_json",
            "items": [],
        }

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {
            "status": "unavailable",
            "reason": "invalid_recent_news_json",
            "items": [],
        }

    if not isinstance(payload, dict):
        return {
            "status": "unavailable",
            "reason": "recent_news_json_not_object",
            "items": [],
        }

    return payload


def format_recent_news_for_prompt(
    payload: dict[str, Any],
    *,
    limit: int = DEFAULT_PROMPT_LIMIT,
) -> str:
    if payload.get("status") != "ok":
        return (
            "No hay titulares recientes de IBKR disponibles. "
            f"Motivo: {payload.get('reason', 'unknown')}."
        )

    items = payload.get("items")
    if not isinstance(items, list) or not items:
        return (
            "IBKR no devolvió titulares nuevos desde el informe anterior "
            f"({payload.get('window', {}).get('start', 'unknown')})."
        )

    candidates = _filter_prompt_items(_dedupe_items(items))
    visible = candidates[:limit]
    window = payload.get("window", {})
    lines = [
        "Pistas IBKR recientes para catalizadores desde "
        f"{_short_date(window.get('start', 'unknown'))}:"
    ]

    for item in visible:
        lines.append(
            "- "
            + " | ".join(
                part
                for part in (
                    _short_date(item.get("published_at")),
                    str(item.get("headline") or ""),
                )
                if part
            )
        )

    if len(candidates) > limit or payload.get("truncated"):
        lines.append(
            "- Lista truncada; usa estos titulares como pistas y busca contexto solo si falta para un evento material."
        )

    return "\n".join(lines)


def _dedupe_items(items: list[Any]) -> list[dict[str, Any]]:
    seen = set()
    output = []
    for item in items:
        if not isinstance(item, dict):
            continue
        headline = " ".join(str(item.get("headline") or "").lower().split())
        if not headline or headline in seen:
            continue
        seen.add(headline)
        output.append(item)
    return output


def _filter_prompt_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        item
        for item in items
        if not _is_universal_noise(item.get("headline"))
    ]


def _is_universal_noise(value: Any) -> bool:
    text = " ".join(str(value or "").lower().split())
    markers = (
        "stock market today:",
        "stocks to watch:",
        "dow jones futures",
        "s&p 500 futures",
        "live coverage",
        "correction to ",
        "cfa technology:",
        "cfa high yield:",
        "insider review",
        "review --",
    )
    return any(marker in text for marker in markers)


def _short_date(value: Any) -> str:
    text = str(value or "")
    return text[:10] if len(text) >= 10 else text
