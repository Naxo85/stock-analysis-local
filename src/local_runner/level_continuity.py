"""Build a deterministic continuity warning for prior entry levels."""

from __future__ import annotations

from typing import Any

from src.common.analysis_validator import PriceRange, extract_range


_TECHNICAL_LEVELS = (
    "sma20",
    "sma50",
    "sma200",
    "donchian20_low",
    "keltner_lower",
)


def build_level_continuity_precheck(
    previous_markdown: str,
    slim: dict[str, Any],
) -> str:
    """Describe whether prior entry ranges still appear in the current slim."""

    if not previous_markdown.strip():
        return "Sin informe anterior: no hay niveles previos que comprobar."

    candidates = _current_level_candidates(slim)
    atr10 = _number((slim.get("technicals") or {}).get("atr10"))
    blocks = [
        _range_status(
            "Entrada",
            extract_range(previous_markdown, "Entrada"),
            candidates,
            atr10,
        ),
        _range_status(
            "Entrada ambiciosa",
            extract_range(previous_markdown, "Entrada ambiciosa"),
            candidates,
            atr10,
        ),
    ]
    return "\n\n".join(blocks)


def _range_status(
    label: str,
    previous: PriceRange | None,
    candidates: list[dict[str, Any]],
    atr10: float | None,
) -> str:
    if previous is None:
        return f"{label} anterior: no disponible."

    midpoint = (previous.lower + previous.upper) / 2
    tolerance = max(midpoint * 0.005, (atr10 or 0) * 0.25)
    matches = [
        candidate
        for candidate in candidates
        if previous.lower - tolerance
        <= candidate["level"]
        <= previous.upper + tolerance
    ]
    previous_text = f"{previous.lower:g}-{previous.upper:g}"
    if matches:
        evidence = "; ".join(_format_candidate(item) for item in matches)
        return (
            f"{label} anterior: {previous_text}\n"
            f"Estado mecánico: evidence_present_in_current_slim\n"
            f"Coincidencias actuales: {evidence}"
        )

    return (
        f"{label} anterior: {previous_text}\n"
        "Estado mecánico: missing_from_current_slim\n"
        "Coincidencias actuales: ninguna. El estado mecánico no invalida por sí solo "
        "el nivel, pero prohíbe conservarlo por inercia: hay que demostrar evidencia "
        "independiente vigente o corregirlo/retirarlo."
    )


def _current_level_candidates(slim: dict[str, Any]) -> list[dict[str, Any]]:
    levels = slim.get("levels") if isinstance(slim.get("levels"), dict) else {}
    candidates: list[dict[str, Any]] = []

    for item in levels.get("supports") or []:
        if not isinstance(item, dict):
            continue
        level = _number(item.get("level"))
        if level is None:
            continue
        candidates.append(
            {
                "level": level,
                "kind": str(item.get("type") or "support"),
                "date": item.get("date"),
                "strength": item.get("strength_score"),
            }
        )

    for item in levels.get("put_walls_top") or []:
        if not isinstance(item, dict):
            continue
        level = _number(item.get("level"))
        if level is None:
            continue
        candidates.append(
            {
                "level": level,
                "kind": "put_wall",
                "expiration": item.get("expiration"),
            }
        )

    technicals = slim.get("technicals")
    if isinstance(technicals, dict):
        for key in _TECHNICAL_LEVELS:
            level = _number(technicals.get(key))
            if level is not None:
                candidates.append({"level": level, "kind": key})

    return candidates


def _format_candidate(candidate: dict[str, Any]) -> str:
    details = [f"{candidate['kind']}={candidate['level']:g}"]
    if candidate.get("date"):
        details.append(f"origen={candidate['date']}")
    if candidate.get("expiration"):
        details.append(f"vencimiento={candidate['expiration']}")
    if candidate.get("strength") is not None:
        details.append(f"strength={candidate['strength']}")
    return " (" + ", ".join(details) + ")"


def _number(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    return None
