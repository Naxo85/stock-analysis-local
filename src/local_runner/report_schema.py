"""Parse validated report Markdown into an app-friendly structured contract."""

from __future__ import annotations

import re
import unicodedata
from datetime import date, datetime
from difflib import SequenceMatcher
from typing import Any

from src.common.analysis_validator import (
    extract_range,
    extract_score,
    extract_dimension_score,
    extract_support_strength,
)
from src.local_runner.report_dates import canonical_report_date, parse_report_date


SCHEMA_VERSION = 7
SCORE_CHANGE_THRESHOLD = 0.7
ENTRY_CHANGE_THRESHOLD_PERCENT = 1.5
AMBITIOUS_ENTRY_CHANGE_THRESHOLD_PERCENT = 1.5
TARGET_CHANGE_THRESHOLD_PERCENT = 3.0
RESISTANCE_CHANGE_THRESHOLD_PERCENT = 3.0
STRUCTURAL_STOP_CHANGE_THRESHOLD_PERCENT = 3.0
NEAR_EVENT_DAYS = 7

_REPORT_DATE_PATTERN = r"(?:\d{4}-\d{2}-\d{2}|\d{2}[-/]\d{2}[-/]\d{4})"
_CATALYST_RE = re.compile(
    rf"^(?P<date>{_REPORT_DATE_PATTERN})\s*[·|]\s*(?P<title>.+?)\s*[·|]\s*"
    r"\((?P<impact>[+-]?\d+)\)\s*$"
)
_EVENT_RE = re.compile(
    rf"^(?P<date>{_REPORT_DATE_PATTERN})\s*[·|]\s*(?P<title>.+?)\s*$"
)
_ROUTINE_OPTIONS_EVENT_RE = re.compile(
    r"\b(vencimiento|expiration|expiry|opex)\b.*\b(opciones|options)\b"
    r"|\b(opciones|options)\b.*\b(vencimiento|expiration|expiry|opex)\b",
    re.IGNORECASE,
)


def build_structured_report(
    *,
    markdown: str,
    generated_at: datetime,
    latest_price: Any,
    previous_markdown: str = "",
) -> dict[str, Any]:
    current = parse_report(markdown, latest_price=latest_price)
    previous = (
        parse_report(previous_markdown, latest_price=None)
        if previous_markdown.strip()
        else None
    )
    changes = compare_reports(current, previous)
    next_event = current.get("next_event")
    if isinstance(next_event, dict):
        _annotate_event_proximity(next_event, generated_at.date())

    alerts = build_analysis_alerts(current, changes)
    return {
        "schema_version": SCHEMA_VERSION,
        "decision": current["decision"],
        "plan": current["plan"],
        "catalysts": current["catalysts"],
        "next_event": next_event,
        "changes": changes,
        "alerts": alerts,
    }


def parse_report(markdown: str, *, latest_price: Any) -> dict[str, Any]:
    return {
        "decision": {
            "score": extract_score(markdown),
            "score_basis": "thesis" if extract_dimension_score(markdown, "Tesis") is not None else "legacy_mixed",
            "thesis_score": extract_dimension_score(markdown, "Tesis"),
            "setup_score": extract_dimension_score(markdown, "Setup"),
            "thesis_reason": _extract_prefixed_value(markdown, "Motivo de Tesis"),
            "setup_reason": _extract_prefixed_value(markdown, "Motivo de Setup"),
            "score_category": score_category(extract_score(markdown)),
            "narrative": _extract_prefixed_value(markdown, "Narrativa actual"),
            "reference_price": _number_or_none(latest_price),
        },
        "plan": {
            "entry": _range_dict(markdown, "Entrada"),
            "entry_reason": _reason_after_label(markdown, "Entrada"),
            **_support_strength_fields(markdown, "Entrada", "entry"),
            "ambitious_entry": _range_dict(markdown, "Entrada ambiciosa"),
            "ambitious_entry_reason": _reason_after_label(
                markdown, "Entrada ambiciosa"
            ),
            **_support_strength_fields(
                markdown,
                "Entrada ambiciosa",
                "washout",
            ),
            "management_stop": _single_level(markdown, "Stop de gestión"),
            "management_stop_reason": _reason_after_label(
                markdown, "Stop de gestión"
            ),
            "structural_stop": _single_level(markdown, "Stop estructural"),
            "structural_stop_reason": _reason_after_label(
                markdown, "Stop estructural"
            ),
            "resistance": _range_dict(markdown, "Resistencia estructural"),
            "resistance_reason": _reason_after_label(
                markdown, "Resistencia estructural"
            ),
            **_support_strength_fields(
                markdown,
                "Resistencia",
                "resistance",
            ),
            "target": _single_level(markdown, "Salida / objetivo principal"),
            "target_reason": _reason_after_label(
                markdown, "Salida / objetivo principal"
            ),
        },
        "catalysts": _parse_catalysts(markdown),
        "next_event": _parse_next_event(markdown),
    }


def compare_reports(
    current: dict[str, Any],
    previous: dict[str, Any] | None,
) -> dict[str, Any]:
    if previous is None:
        return {
            "has_previous": False,
            "score_delta": None,
            "score_change_material": False,
            "score_category_changed": False,
            "new_catalysts": [],
            "plan_changes": [],
        }

    current_score = current["decision"].get("score")
    previous_score = previous["decision"].get("score")
    comparable = current["decision"].get("score_basis") == previous["decision"].get("score_basis")
    if not comparable:
        previous_score = None
    score_delta = _difference(current_score, previous_score)
    category_changed = comparable and (
        current["decision"].get("score_category")
        != previous["decision"].get("score_category")
    )
    score_material = (
        score_delta is not None
        and (
            abs(score_delta) >= SCORE_CHANGE_THRESHOLD
            or category_changed
        )
    )
    new_catalysts = _new_catalysts(
        current.get("catalysts", []),
        previous.get("catalysts", []),
    )
    plan_changes = _material_plan_changes(
        current.get("plan", {}),
        previous.get("plan", {}),
    )
    return {
        "has_previous": True,
        "score_basis_changed": not comparable,
        "setup_delta": _difference(current["decision"].get("setup_score"), previous["decision"].get("setup_score")),
        "score_delta": round(score_delta, 2) if score_delta is not None else None,
        "score_change_material": score_material,
        "score_category_changed": category_changed,
        "previous_score": previous_score,
        "new_catalysts": new_catalysts,
        "plan_changes": plan_changes,
    }


def build_analysis_alerts(
    current: dict[str, Any],
    changes: dict[str, Any],
) -> list[dict[str, Any]]:
    alerts: list[dict[str, Any]] = []
    if changes.get("score_change_material"):
        delta = float(changes["score_delta"])
        alerts.append(
            {
                "type": "score_change",
                "severity": "high" if abs(delta) >= 1.0 else "medium",
                "message": (
                    f"Valoración {changes.get('previous_score'):g} → "
                    f"{current['decision'].get('score'):g}"
                ),
            }
        )

    for catalyst in changes.get("new_catalysts", []):
        impact = catalyst.get("impact")
        if isinstance(impact, int) and abs(impact) >= 7:
            alerts.append(
                {
                    "type": "new_catalyst",
                    "severity": "high",
                    "message": f"{catalyst.get('title')} ({impact:+d})",
                }
            )

    for change in changes.get("plan_changes", []):
        alerts.append(
            {
                "type": "plan_change",
                "severity": "medium",
                "message": change["message"],
            }
        )

    event = current.get("next_event")
    if isinstance(event, dict) and event.get("is_home_relevant"):
        alerts.append(
            {
                "type": "near_event",
                "severity": "medium",
                "message": _event_message(event),
            }
        )
    return alerts


def score_category(score: float | None) -> str | None:
    if score is None:
        return None
    if score < 5.0:
        return "weak"
    if score < 5.5:
        return "watch"
    if score < 7.0:
        return "interesting"
    if score < 8.5:
        return "good"
    return "exceptional"


def _material_plan_changes(
    current: dict[str, Any], previous: dict[str, Any]
) -> list[dict[str, Any]]:
    changes: list[dict[str, Any]] = []
    _append_range_change(
        changes,
        label="Entrada",
        key="entry",
        reason_key="entry_reason",
        threshold=ENTRY_CHANGE_THRESHOLD_PERCENT,
        current=current,
        previous=previous,
    )
    _append_range_change(
        changes,
        label="Entrada ambiciosa",
        key="ambitious_entry",
        reason_key="ambitious_entry_reason",
        threshold=AMBITIOUS_ENTRY_CHANGE_THRESHOLD_PERCENT,
        current=current,
        previous=previous,
    )
    _append_level_change(
        changes,
        label="Salida",
        key="target",
        reason_key="target_reason",
        threshold=TARGET_CHANGE_THRESHOLD_PERCENT,
        current=current,
        previous=previous,
    )
    _append_range_change(
        changes,
        label="Resistencia estructural",
        key="resistance",
        reason_key="resistance_reason",
        threshold=RESISTANCE_CHANGE_THRESHOLD_PERCENT,
        current=current,
        previous=previous,
    )
    _append_level_change(
        changes,
        label="Stop estructural",
        key="structural_stop",
        reason_key="structural_stop_reason",
        threshold=STRUCTURAL_STOP_CHANGE_THRESHOLD_PERCENT,
        current=current,
        previous=previous,
    )
    return changes


def _append_range_change(
    changes: list[dict[str, Any]],
    *,
    label: str,
    key: str,
    reason_key: str,
    threshold: float,
    current: dict[str, Any],
    previous: dict[str, Any],
) -> None:
    new = current.get(key)
    old = previous.get(key)
    reason = current.get(reason_key)
    if isinstance(old, dict) and new is None:
        changes.append(
            {
                "field": key,
                "change_kind": "removed",
                "change_percent": None,
                "previous": old,
                "current": None,
                "reason": reason,
                "message": (
                    f"{label} {_format_range(old)} retirada: "
                    f"{reason or 'sin zona verificable vigente'}"
                ),
            }
        )
        return
    if old is None and isinstance(new, dict):
        changes.append(
            {
                "field": key,
                "change_kind": "added",
                "change_percent": None,
                "previous": None,
                "current": new,
                "reason": reason,
                "message": (
                    f"{label} añadida en {_format_range(new)}: "
                    f"{reason or 'motivo actualizado'}"
                ),
            }
        )
        return
    if not isinstance(new, dict) or not isinstance(old, dict):
        return
    new_mid = (new["lower"] + new["upper"]) / 2
    old_mid = (old["lower"] + old["upper"]) / 2
    change_percent = _percent_change(new_mid, old_mid)
    if change_percent is not None and abs(change_percent) < threshold:
        if _signals_evidence_replacement(reason):
            changes.append(
                {
                    "field": key,
                    "change_kind": "evidence_replaced",
                    "change_percent": round(change_percent, 2),
                    "previous": old,
                    "current": new,
                    "reason": reason,
                    "message": f"{label} mantiene precio con fundamento sustituido: {reason}",
                }
            )
        return
    if change_percent is None:
        return
    if not _reason_materially_changed(reason, previous.get(reason_key)):
        return
    changes.append(
        {
            "field": key,
            "change_kind": "moved",
            "change_percent": round(change_percent, 2),
            "previous": old,
            "current": new,
            "reason": reason,
            "message": (
                f"{label} {_format_range(old)} → {_format_range(new)}: "
                f"{reason or 'motivo actualizado'}"
            ),
        }
    )


def _append_level_change(
    changes: list[dict[str, Any]],
    *,
    label: str,
    key: str,
    reason_key: str,
    threshold: float,
    current: dict[str, Any],
    previous: dict[str, Any],
) -> None:
    new = current.get(key)
    old = previous.get(key)
    change_percent = _percent_change(new, old)
    if change_percent is None or abs(change_percent) < threshold:
        return
    if not _reason_materially_changed(current.get(reason_key), previous.get(reason_key)):
        return
    changes.append(
        {
            "field": key,
            "change_percent": round(change_percent, 2),
            "previous": old,
            "current": new,
            "reason": current.get(reason_key),
            "message": (
                f"{label} {_format_number(old)} → {_format_number(new)}: "
                f"{current.get(reason_key) or 'motivo actualizado'}"
            ),
        }
    )


def _parse_catalysts(markdown: str) -> list[dict[str, Any]]:
    lines = _section_lines(markdown, "1)", "2)")
    catalysts: list[dict[str, Any]] = []
    index = 0
    while index < len(lines):
        match = _CATALYST_RE.match(_clean_line(lines[index]))
        if not match:
            index += 1
            continue
        explanation = ""
        if index + 1 < len(lines) and not _CATALYST_RE.match(
            _clean_line(lines[index + 1])
        ):
            explanation = _clean_line(lines[index + 1])
            index += 1
        catalysts.append(
            {
                "date": canonical_report_date(match.group("date")),
                "title": match.group("title").strip(),
                "impact": int(match.group("impact")),
                "explanation": explanation,
            }
        )
        index += 1
    return catalysts


def _parse_next_event(markdown: str) -> dict[str, Any] | None:
    lines = [_clean_line(line) for line in _section_lines(markdown, "2)", "3)")]
    lines = [line for line in lines if line]
    if not lines:
        return None
    match = _EVENT_RE.match(lines[0])
    if not match:
        return {"date": None, "title": lines[0], "explanation": " ".join(lines[1:])}
    return {
        "date": canonical_report_date(match.group("date")),
        "title": match.group("title").strip(),
        "explanation": " ".join(lines[1:]),
    }


def _annotate_event_proximity(event: dict[str, Any], analysis_date: date) -> None:
    event["is_routine_market_event"] = _is_routine_market_event(event)
    raw_date = event.get("date")
    event_date = parse_report_date(str(raw_date))
    if event_date is None:
        event["days_away"] = None
        event["is_near"] = False
        event["is_home_relevant"] = False
        return
    days_away = (event_date - analysis_date).days
    event["days_away"] = days_away
    event["is_near"] = 0 <= days_away <= NEAR_EVENT_DAYS
    event["is_home_relevant"] = (
        event["is_near"] and not event["is_routine_market_event"]
    )


def _new_catalysts(
    current: list[dict[str, Any]], previous: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    previous_titles = [str(item.get("title") or "") for item in previous]
    for catalyst in current:
        title = str(catalyst.get("title") or "")
        if not any(_text_similarity(title, old) >= 0.72 for old in previous_titles):
            result.append(catalyst)
    return result


def _reason_after_label(markdown: str, label: str) -> str | None:
    lines = markdown.splitlines()
    normalized_label = _normalize(label)
    for index, raw_line in enumerate(lines):
        clean = _clean_line(raw_line)
        if ":" not in clean or _normalize(clean.split(":", 1)[0]) != normalized_label:
            continue
        for following in lines[index + 1 : index + 6]:
            value = _clean_line(following)
            if not value:
                continue
            prefix = _normalize(value.split(":", 1)[0]) if ":" in value else ""
            if prefix == "motivo":
                return value.split(":", 1)[1].strip() or None
            if prefix == "estado actual":
                continue
            if prefix.startswith("fortaleza de") or prefix.startswith("factores de"):
                continue
            if prefix in {
                "entrada",
                "entrada ambiciosa",
                "stop de gestion",
                "stop estructural",
                "salida objetivo principal",
            } or re.match(r"^\d+\)", value):
                break
            return value
    return None


def _support_strength_fields(
    markdown: str,
    label: str,
    key: str,
) -> dict[str, Any]:
    strength = extract_support_strength(markdown, label)
    if strength is None:
        return {
            f"{key}_strength_score": None,
            f"{key}_strength_category": None,
            f"{key}_strength_factors": None,
            f"{key}_strength_breakdown": None,
        }
    return {
        f"{key}_strength_score": strength.score,
        f"{key}_strength_category": strength.category,
        f"{key}_strength_factors": strength.factors,
        f"{key}_strength_breakdown": strength.breakdown,
    }


def _signals_evidence_replacement(reason: Any) -> bool:
    normalized = _normalize(str(reason or ""))
    return "se sustituye fundamento" in normalized


def _extract_prefixed_value(markdown: str, label: str) -> str | None:
    normalized_label = _normalize(label)
    for raw_line in markdown.splitlines():
        clean = _clean_line(raw_line)
        if ":" in clean and _normalize(clean.split(":", 1)[0]) == normalized_label:
            return clean.split(":", 1)[1].strip() or None
    return None


def _range_dict(markdown: str, label: str) -> dict[str, float] | None:
    value = extract_range(markdown, label)
    return value.to_dict() if value else None


def _single_level(markdown: str, label: str) -> float | None:
    value = extract_range(markdown, label)
    return value.lower if value else None


def _section_lines(markdown: str, start: str, end: str) -> list[str]:
    collecting = False
    result: list[str] = []
    for raw_line in markdown.splitlines():
        clean = _clean_line(raw_line)
        if clean.startswith(end):
            break
        if collecting and clean:
            result.append(clean)
        if clean.startswith(start):
            collecting = True
    return result


def _reason_materially_changed(current: Any, previous: Any) -> bool:
    if not current:
        return False
    if not previous:
        return True
    return _text_similarity(str(current), str(previous)) < 0.8


def _event_message(event: dict[str, Any]) -> str:
    days = event.get("days_away")
    when = "hoy" if days == 0 else f"en {days} días"
    return f"Evento {when} · {event.get('date')}: {event.get('title')}"


def _is_routine_market_event(event: dict[str, Any]) -> bool:
    text = f"{event.get('title') or ''} {event.get('explanation') or ''}"
    return bool(_ROUTINE_OPTIONS_EVENT_RE.search(_normalize(text)))


def _text_similarity(left: str, right: str) -> float:
    return SequenceMatcher(None, _normalize(left), _normalize(right)).ratio()


def _normalize(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", str(value or "").casefold())
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", ascii_value)).strip()


def _clean_line(value: str) -> str:
    return (
        str(value or "")
        .strip()
        .lstrip("-*•# ")
        .replace("**", "")
        .replace("*", "")
        .strip()
    )


def _difference(current: Any, previous: Any) -> float | None:
    if not isinstance(current, (int, float)) or not isinstance(previous, (int, float)):
        return None
    return float(current) - float(previous)


def _percent_change(current: Any, previous: Any) -> float | None:
    if not isinstance(current, (int, float)) or not isinstance(previous, (int, float)):
        return None
    if float(previous) == 0:
        return None
    return (float(current) - float(previous)) / abs(float(previous)) * 100


def _number_or_none(value: Any) -> float | None:
    return float(value) if isinstance(value, (int, float)) else None


def _format_range(value: dict[str, float]) -> str:
    return f"{value['lower']:g}–{value['upper']:g}"


def _format_number(value: Any) -> str:
    return f"{float(value):g}" if isinstance(value, (int, float)) else "?"
