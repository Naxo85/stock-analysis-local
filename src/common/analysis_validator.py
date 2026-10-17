"""Validation helpers for generated stock analysis markdown."""

from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass
from decimal import Decimal
from typing import Any


@dataclass(frozen=True)
class PriceRange:
    lower: float
    upper: float

    def to_dict(self) -> dict[str, float]:
        return {
            "lower": self.lower,
            "upper": self.upper,
        }


@dataclass(frozen=True)
class SupportStrength:
    score: int | None
    category: str
    factors: str
    breakdown: dict[str, int]
    applicable: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "score": self.score,
            "category": self.category,
            "factors": self.factors,
            "breakdown": self.breakdown,
            "applicable": self.applicable,
        }


@dataclass(frozen=True)
class ValidationResult:
    ok: bool
    status: str
    errors: tuple[str, ...]
    score: float | None = None
    entry_range: PriceRange | None = None
    ambitious_entry_range: PriceRange | None = None
    resistance_range: PriceRange | None = None
    entry_strength: SupportStrength | None = None
    ambitious_entry_strength: SupportStrength | None = None
    resistance_strength: SupportStrength | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "status": self.status,
            "errors": list(self.errors),
            "score": self.score,
            "entry_range": (
                self.entry_range.to_dict() if self.entry_range else None
            ),
            "ambitious_entry_range": (
                self.ambitious_entry_range.to_dict()
                if self.ambitious_entry_range
                else None
            ),
            "resistance_range": (
                self.resistance_range.to_dict() if self.resistance_range else None
            ),
            "entry_strength": (
                self.entry_strength.to_dict() if self.entry_strength else None
            ),
            "ambitious_entry_strength": (
                self.ambitious_entry_strength.to_dict()
                if self.ambitious_entry_strength
                else None
            ),
            "resistance_strength": (
                self.resistance_strength.to_dict()
                if self.resistance_strength
                else None
            ),
        }


_SCORE_RE = re.compile(
    r"Valoracion\s*:\s*([0-9]+(?:[.,][0-9]+)?)\s*/\s*10",
    re.IGNORECASE,
)

_NUMBER_RE = re.compile(
    # Consume the COMPLETE numeric token before interpreting locale. A
    # thousands-first alternative used to split 208.9032 into 208.903 + 2.
    r'-?[0-9]+(?:[.,][0-9]+)*'
)
_PRICE_RANGE_SEPARATOR_RE = re.compile(
    r"(?<=\d)\s*[-\u2010\u2011\u2012\u2013\u2014\u2212]\s*(?=\$?\s*\d)"
)


def validate_markdown(
    markdown: str | None,
    *,
    authoritative_context: str | None = None,
    require_support_strengths: bool = False,
    require_resistance: bool = False,
    require_separate_scores: bool = False,
) -> ValidationResult:
    """Validate the minimum contract expected by the Sheet/parser."""

    text = markdown or ""
    errors: list[str] = []

    if not text.strip():
        return ValidationResult(
            ok=False,
            status="failed",
            errors=("markdown_empty",),
        )

    if ":contentReference[" in text or "oaicite:" in text:
        errors.append(
            "invalid_internal_citation_marker: remove ChatGPT contentReference/oaicite artifacts"
        )

    context_denial = _previous_context_denial(text)
    if context_denial:
        errors.append(
            "previous_analysis_ignored: final reports may not claim that supplied analysis context is inaccessible"
        )

    if authoritative_context:
        errors.extend(
            _validate_previous_level_references(text, authoritative_context)
        )

    separate = require_separate_scores or any(
        _extract_line_value(text, label) for label in ("Tesis", "Setup")
    )
    if separate:
        for label in ("Tesis", "Setup"):
            dimension = extract_dimension_score(text, label)
            if dimension is None or not 0 <= dimension <= 10:
                errors.append(f"missing_or_invalid_{label.lower()}_score: expected '{label}: X / 10' in [0, 10]")
            if not _extract_line_value(text, f"Motivo de {label}"):
                errors.append(f"missing_{label.lower()}_reason")
        if _extract_line_value(text, "Valoración"):
            errors.append("mixed_score_contract: use Tesis and Setup without Valoración")
    score = extract_score(text)
    if not separate and score is None:
        errors.append("missing_or_invalid_score: expected 'Valoración: X / 10'")
    elif not separate and (score < 0 or score > 10):
        errors.append("score_out_of_range: expected 0 <= score <= 10")

    entry_range = extract_range(text, "Entrada")
    if entry_range is None:
        errors.append("missing_or_invalid_entry_range: expected 'Entrada: $A - $B'")

    ambitious_entry_range = extract_range(text, "Entrada ambiciosa")
    ambitious_unavailable = (
        ambitious_entry_range is None
        and has_explicitly_unavailable_level(text, "Entrada ambiciosa")
    )
    if ambitious_entry_range is None and not ambitious_unavailable:
        errors.append(
            "missing_or_invalid_ambitious_entry_range: "
            "expected 'Entrada ambiciosa: $C - $D' or "
            "'Entrada ambiciosa: Sin zona verificable'"
        )
    if authoritative_context and ambitious_unavailable and entry_range is not None:
        lower_support = _distinct_lower_support(
            authoritative_context,
            entry_floor=entry_range.lower,
        )
        if lower_support is not None:
            errors.append(
                "ambitious_entry_unavailable_despite_lower_support: "
                f"slim contains a distinct lower support at ${lower_support:g}; "
                "turn it into an ambitious-entry range and score its actual "
                "strength instead of returning Sin zona verificable"
            )

    entry_strength = extract_support_strength(text, "Entrada")
    ambitious_entry_strength = extract_support_strength(
        text,
        "Entrada ambiciosa",
    )
    resistance_range = extract_range(text, "Resistencia estructural")
    resistance_strength = extract_support_strength(text, "Resistencia")
    if require_support_strengths:
        if entry_strength is None or not entry_strength.applicable:
            errors.append(
                "missing_or_invalid_entry_strength: expected integer N/100, "
                "matching category, complete breakdown and nonempty evidence text"
            )
        ambitious_unavailable = (
            ambitious_entry_range is None
            and has_explicitly_unavailable_level(text, "Entrada ambiciosa")
        )
        if (
            ambitious_entry_strength is None
            or ambitious_entry_strength.applicable == ambitious_unavailable
        ):
            errors.append(
                "missing_or_invalid_ambitious_entry_strength: expected N/100 "
                "with matching category, complete breakdown and nonempty evidence text; use No aplicable only "
                "when no zone exists"
            )
    if require_resistance:
        if resistance_range is None:
            errors.append(
                "missing_or_invalid_resistance_range: expected "
                "'Resistencia estructural: $A - $B'"
            )
        if resistance_strength is None or not resistance_strength.applicable:
            errors.append(
                "missing_or_invalid_resistance_strength: expected integer N/100, "
                "matching category, complete breakdown and nonempty evidence text"
            )

    ok = not errors

    return ValidationResult(
        ok=ok,
        status="ok" if ok else "failed",
        errors=tuple(errors),
        score=score,
        entry_range=entry_range,
        ambitious_entry_range=ambitious_entry_range,
        resistance_range=resistance_range,
        entry_strength=entry_strength,
        ambitious_entry_strength=ambitious_entry_strength,
        resistance_strength=resistance_strength,
    )


def extract_support_strength(
    markdown: str,
    level_label: str,
) -> SupportStrength | None:
    strength_value = _extract_line_value(
        markdown,
        f"Fortaleza de {level_label}",
    )
    factors = _extract_line_value(markdown, f"Factores de {level_label}")
    breakdown_value = _extract_line_value(
        markdown,
        f"Desglose de {level_label}",
    )
    if not strength_value or not re.search(r"\w", factors) or not breakdown_value:
        return None
    if _normalize_for_match(strength_value).casefold().strip(" \t.;:!?") == "no aplicable":
        if _normalize_for_match(breakdown_value).casefold().strip(" \t.;:!?") != "no aplicable":
            return None
        return SupportStrength(
            score=None,
            category="no_aplica",
            factors=factors,
            breakdown={},
            applicable=False,
        )
    match = re.fullmatch(
        r"\s*(\d{1,3})\s*/\s*100(?:\s*[·|:,\-–—]\s*|\s+)(.+?)\s*",
        _clean_line(strength_value),
    )
    if not match:
        return None
    score = int(match.group(1))
    if not 0 <= score <= 100:
        return None
    # Evidence is required, but prose delimiters cannot measure its quality.
    # A fifth semicolon may be an explanation, not a fifth independent fact.
    # Keep every factor/comment verbatim; validate scores and sources instead.
    expected = support_strength_category(score)
    category = _normalize_for_match(match.group(2)).casefold().strip(" \t.;:!?¡¿")
    if category != _normalize_for_match(expected).casefold():
        return None
    breakdown = _parse_strength_breakdown(breakdown_value)
    if (
        breakdown is None
        or sum(breakdown.values()) != score
        or not _strength_breakdown_qualifies(score, breakdown)
    ):
        return None
    return SupportStrength(
        score=score,
        category=expected,
        factors=factors,
        breakdown=breakdown,
    )


def support_strength_category(score: int) -> str:
    if score < 40:
        return "débil"
    if score < 70:
        return "moderado"
    if score < 85:
        return "sólido"
    if score < 95:
        return "fuerte"
    return "excepcional"


def _strength_breakdown_qualifies(score: int, breakdown: dict[str, int]) -> bool:
    """Require real evidence pillars before assigning higher categories."""
    if score < 70:
        return True
    structure = breakdown["estructura"]
    volume = breakdown["volumen"]
    options = breakdown["opciones"]
    confluence = breakdown["confluencia"]
    durability = breakdown["durabilidad"]
    if structure < 13 or (volume < 10 and options < 12):
        return False
    if score < 85:
        return True
    primary_pillars = sum(
        (
            structure >= 18,
            volume >= 14,
            options >= 18,
        )
    )
    if (
        primary_pillars < 2
        or (structure < 18 and volume < 14)
        or confluence < 10
        or durability < 9
    ):
        return False
    if score >= 95:
        return (
            structure >= 22
            and volume >= 17
            and confluence >= 13
            and durability >= 12
        )
    return True


def _parse_strength_breakdown(value: str) -> dict[str, int] | None:
    # Parse the five typed components, not a prescribed delimiter. Punctuation
    # can vary; missing/duplicate components, extra prose/numbers and wrong
    # denominators/ranges must still fail. No score or meaning is rewritten.
    value = _clean_line(value)
    maxima = {
        "estructura": 25,
        "volumen": 20,
        "opciones": 25,
        "confluencia": 15,
        "durabilidad": 15,
    }
    result: dict[str, int] = {}
    pattern = re.compile(
        r"\b(estructura|volumen|opciones|confluencia|durabilidad)\s*[:=]?\s*"
        r"(\d{1,3})\s*/\s*(\d{1,3})\b", re.IGNORECASE)
    cursor = 0
    punctuation = r"[\s,;·|:\-–—.!?()\[\]]*"
    for match in pattern.finditer(value):
        if not re.fullmatch(punctuation, value[cursor:match.start()]):
            return None
        key = _normalize_for_match(match.group(1)).casefold()
        points = int(match.group(2))
        maximum = int(match.group(3))
        if key not in maxima or maximum != maxima[key] or not 0 <= points <= maximum:
            return None
        if key in result:
            return None
        result[key] = points
        cursor = match.end()
    if not re.fullmatch(punctuation, value[cursor:]):
        return None
    return result if set(result) == set(maxima) else None


def _extract_line_value(markdown: str, label: str) -> str:
    normalized_label = _normalize_for_match(label).casefold()
    for raw_line in markdown.splitlines():
        clean = _clean_line(raw_line)
        if ":" not in clean:
            continue
        prefix, value = clean.split(":", 1)
        if _normalize_for_match(prefix).casefold() == normalized_label:
            return value.strip()
    return ""


def _validate_previous_level_references(
    markdown: str,
    authoritative_context: str,
) -> list[str]:
    fields = (
        ("Entrada", "entrada_anterior"),
        ("Entrada ambiciosa", "entrada_ambiciosa_anterior"),
        ("Stop de gestión", "stop_de_gestion_anterior"),
        ("Stop estructural", "stop_estructural_anterior"),
        ("Resistencia estructural", "resistencia_anterior"),
        ("Salida / objetivo principal", "salida_anterior"),
    )
    errors: list[str] = []
    for label, context_key in fields:
        previous_value = _extract_context_value(authoritative_context, context_key)
        block = _extract_plan_block(markdown, label, tuple(item[0] for item in fields))
        if not block:
            continue

        if _declares_obsolete_level_replacement(block):
            errors.append(
                f"invalid_previous_level_continuity: {label} cannot use "
                "Se sustituye fundamento; recalculate and declare Se corrige"
            )
            continue

        if previous_value and "no extra" not in _normalize_for_match(previous_value).casefold():
            if not _declares_level_continuity(block):
                errors.append(
                    f"missing_previous_level_continuity: {label} must declare Se conserva/Se reprioriza/Se corrige/Se retira"
                )
                continue

        if not _declares_level_change(block):
            continue

        if not previous_value or "no extra" in _normalize_for_match(previous_value).casefold():
            if _mentions_invented_previous_price(block, label):
                errors.append(
                    f"invented_previous_level: {label} has no authoritative prior value"
                )
            continue

        expected = _numbers_before_percentage(previous_value)
        if _declares_level_reprioritization(block):
            current = _numbers_before_percentage(block.splitlines()[0])
            if _price_ranges_overlap(expected, current):
                errors.append(
                    f"reprioritized_overlapping_level: {label} overlaps the previous range; "
                    "the same support must use Se conserva with exact prices"
                )
                continue
        mentioned = _dollar_numbers(block)
        mentioned.extend(_numbers_in_previous_reference(block))
        missing = [
            number
            for number in expected
            if not any(abs(number - candidate) <= 0.02 for candidate in mentioned)
        ]
        if missing:
            expected_text = ",".join(f"{number:g}" for number in expected)
            errors.append(
                f"previous_level_mismatch: {label} expected={expected_text}"
            )
    return errors


def _previous_context_denial(markdown: str) -> bool:
    output = _normalize_for_match(markdown).casefold()
    inaccessible_markers = (
        "sin comparacion de continuidad",
        "previous analysis context autorizado no esta accesible",
        "previous analysis context no esta accesible",
        "informe anterior no esta accesible",
        "informe anterior no esta disponible",
    )
    return any(marker in output for marker in inaccessible_markers)


def _extract_context_value(context: str, key: str) -> str:
    match = re.search(
        rf"(?mi)^{re.escape(key)}\s*:\s*(.+?)\s*$",
        context,
    )
    return match.group(1).strip() if match else ""


def _distinct_lower_support(context: str, *, entry_floor: float) -> float | None:
    marker = re.search(r"(?im)^## JSON T[eé]cnico Slim\s*$", context)
    if not marker:
        return None
    fenced = re.search(
        r"```json\s*(\{.*?\})\s*```",
        context[marker.end() :],
        re.DOTALL | re.IGNORECASE,
    )
    if not fenced:
        return None
    try:
        slim = json.loads(fenced.group(1))
    except (TypeError, json.JSONDecodeError):
        return None
    levels = slim.get("levels") if isinstance(slim, dict) else None
    supports = levels.get("supports") if isinstance(levels, dict) else None
    if not isinstance(supports, list):
        return None

    latest_price = _positive_number(slim.get("latest_price"))
    technicals = slim.get("technicals") if isinstance(slim, dict) else None
    options = slim.get("options") if isinstance(slim, dict) else None
    atr10 = _positive_number(
        technicals.get("atr10") if isinstance(technicals, dict) else None
    )
    expected_move = _positive_number(
        options.get("expected_move_1w_abs") if isinstance(options, dict) else None
    )
    volatility_scales = [value for value in (atr10, expected_move) if value]
    ambitious_max_distance = (
        2.0 * max(volatility_scales)
        if latest_price is not None and volatility_scales
        else None
    )

    candidates: list[float] = []
    for support in supports:
        value = support.get("level") if isinstance(support, dict) else None
        if (
            isinstance(value, (int, float))
            and not isinstance(value, bool)
            and 0 < float(value) < float(entry_floor) * 0.98
            and (
                ambitious_max_distance is None
                or latest_price is None
                or latest_price - float(value) <= ambitious_max_distance
            )
        ):
            candidates.append(float(value))
    return max(candidates) if candidates else None


def _positive_number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    return number if number > 0 else None


def _extract_plan_block(
    markdown: str,
    label: str,
    labels: tuple[str, ...],
) -> str:
    lines = markdown.splitlines()
    start = None
    normalized_label = _normalize_for_match(label).casefold()
    normalized_labels = tuple(
        _normalize_for_match(item).casefold() for item in labels
    )
    for index, raw_line in enumerate(lines):
        line = _normalize_for_match(_clean_line(raw_line)).casefold()
        if line.startswith(f"{normalized_label}:"):
            start = index
            break
    if start is None:
        return ""

    block = [lines[start]]
    for raw_line in lines[start + 1 :]:
        line = _normalize_for_match(_clean_line(raw_line)).casefold()
        if any(line.startswith(f"{candidate}:") for candidate in normalized_labels):
            break
        if re.match(r"^4\)\s*conclusion", line):
            break
        block.append(raw_line)
    return "\n".join(block)


def _declares_level_change(block: str) -> bool:
    normalized = _normalize_for_match(block).casefold()
    return bool(re.search(r'\bse\s+(?:reprioriza|corrige|retira)\b', normalized))


def _declares_level_continuity(block: str) -> bool:
    normalized = _normalize_for_match(block).casefold()
    # The transition verb matters, not its following colon. Exact previous
    # prices, overlap and provenance checks remain mandatory.
    return bool(re.search(r'\bse\s+(?:conserva|reprioriza|corrige|retira)\b', normalized))


def _declares_obsolete_level_replacement(block: str) -> bool:
    return "se sustituye fundamento:" in _normalize_for_match(block).casefold()


def _declares_level_reprioritization(block: str) -> bool:
    return bool(re.search(r'\bse\s+reprioriza\b', _normalize_for_match(block).casefold()))


def _mentions_invented_previous_price(block: str, label: str) -> bool:
    """Reject invented continuity, not unrelated historic technical references."""

    normalized_label = _normalize_for_match(label).casefold()
    previous_markers = ("anterior", "antiguo", "antigua", "previo", "previa")
    # Scope a missing-prior statement to its sentence. A later invented
    # prior price must not be hidden by an earlier "Sin zona verificable".
    clauses = [clause for raw in block.splitlines()
               for clause in re.split(r"(?<=[.!?])\s+(?=[A-Za-zÁÉÍÓÚÑ¿¡])", _clean_line(raw))]
    for raw_line in clauses:
        clean = _clean_line(raw_line)
        normalized = _normalize_for_match(clean).casefold()
        if normalized.startswith(
            ("fortaleza de ", "desglose de ", "factores de ")
        ):
            continue
        if not any(marker in normalized for marker in previous_markers):
            continue
        if _declares_missing_previous_level(clean, label):
            continue
        if not _numbers_before_percentage(clean):
            continue
        if normalized_label in normalized or _declares_level_continuity(clean):
            return True
    return False


def _declares_missing_previous_level(value: str, label: str) -> bool:
    """Allow an explicit first-publication statement followed by current evidence."""

    normalized = _normalize_for_match(value).casefold()
    del label  # The caller already scopes the text to one plan-level block.
    absence_patterns = (
        r"\b(?:antes|anteriormente)\s+(?:figuraba|constaba|aparecia)\s+(?:como\s+)?sin\s+zona\s+verificable\b",
        r"\bno\s+(?:habia|hubo|existia)\b.{0,60}\b(?:rango|resistencia|entrada|nivel)\b.{0,60}\b(?:anterior(?:mente)?|previo|previa)\b",
        r"\bno\s+se\s+(?:habia\s+)?(?:publico|extrajo|proporciono)\b.{0,80}\b(?:anterior(?:mente)?|previo|previa)\b",
        r"\b(?:anterior(?:mente)?|previo|previa)\b.{0,60}\b(?:no\s+(?:estaba|fue)\s+(?:disponible|extraid[oa])|no\s+extrajo)\b",
        r"\b(?:anterior(?:mente)?|previo|previa)\b.{0,60}\bsin\s+zona\s+verificable\b",
        r"\bsin\s+zona\s+verificable\b.{0,60}\b(?:anterior(?:mente)?|previo|previa)\b",
    )
    return any(re.search(pattern, normalized) for pattern in absence_patterns)


def _numbers_before_percentage(value: str) -> list[float]:
    level_text = value.split("(", 1)[0]
    level_text = _normalize_price_range_separators(level_text)
    return [
        number
        for number in (_to_number(match.group(0)) for match in _NUMBER_RE.finditer(level_text))
        if number is not None
    ]


def _dollar_numbers(value: str) -> list[float]:
    dollar_range_re = re.compile(
        rf"\$\s*({_NUMBER_RE.pattern})\s*[-–—]\s*\$?\s*({_NUMBER_RE.pattern})"
    )
    numbers = [
        number
        for match in dollar_range_re.finditer(value)
        for number in (_to_number(match.group(1)), _to_number(match.group(2)))
        if number is not None
    ]
    dollar_re = re.compile(rf"\$\s*({_NUMBER_RE.pattern})")
    numbers.extend(
        number
        for number in (_to_number(match.group(1)) for match in dollar_re.finditer(value))
        if number is not None
    )
    return numbers


def _numbers_in_previous_reference(value: str) -> list[float]:
    """Accept exact prior prices even when the model omits the currency sign."""
    markers = ("anterior", "anteriores", "previo", "previa", "antiguo", "antigua")
    numbers: list[float] = []
    for raw_line in value.splitlines():
        raw_line = _clean_line(raw_line)
        line = _normalize_for_match(raw_line).casefold()
        if line.startswith(("fortaleza de ", "desglose de ", "factores de ")):
            continue
        # The continuity declaration itself scopes the prior reference. It
        # need not repeat "anterior" or a currency sign (AMAT/IREN, 02-Oct).
        if not any(marker in line for marker in markers) and not _declares_level_change(raw_line):
            continue
        line = _normalize_for_match(
            _normalize_price_range_separators(raw_line)
        ).casefold()
        numbers.extend(
            number
            for number in (
                _to_number(match.group(0)) for match in _NUMBER_RE.finditer(line)
            )
            if number is not None
        )
    return numbers


def _price_ranges_overlap(previous: list[float], current: list[float]) -> bool:
    if len(previous) < 2 or len(current) < 2:
        return False
    previous_low, previous_high = sorted(previous[:2])
    current_low, current_high = sorted(current[:2])
    return max(previous_low, current_low) <= min(previous_high, current_high) + 0.02


def _normalize_price_range_separators(value: str) -> str:
    return _PRICE_RANGE_SEPARATOR_RE.sub(" ", value)


def extract_dimension_score(markdown: str, label: str) -> float | None:
    value = _extract_line_value(markdown, label)
    match = re.fullmatch(r"([0-9]+(?:[.,][0-9]+)?)\s*/\s*10[\s.;:!?]*", value)
    return _to_number(match.group(1)) if match else None


def extract_score(markdown: str) -> float | None:
    thesis = extract_dimension_score(markdown, "Tesis")
    if thesis is not None:
        return thesis
    for raw_line in markdown.splitlines():
        line = _clean_line(raw_line)
        match = _SCORE_RE.search(_normalize_for_match(line))

        if match:
            return _to_number(match.group(1))

    return None


def extract_range(markdown: str, label: str) -> PriceRange | None:
    escaped_label = re.escape(label)
    label_re = re.compile(rf"^{escaped_label}\s*:\s*(.+)$", re.IGNORECASE)

    for raw_line in markdown.splitlines():
        line = _clean_line(raw_line)
        match = label_re.match(line)

        if not match:
            continue

        value_part = match.group(1).split("(", 1)[0]
        # A compact price range such as ``52.6-53`` uses the hyphen as a
        # separator, not as the sign of the second (necessarily positive) price.
        value_part = _normalize_price_range_separators(value_part)
        numbers = [
            number
            for number in (
                _to_number(m.group(0))
                for m in _NUMBER_RE.finditer(value_part)
            )
            if number is not None
        ]

        if not numbers:
            return None

        if len(numbers) == 1:
            return PriceRange(lower=numbers[0], upper=numbers[0])

        first, second = numbers[0], numbers[1]

        return PriceRange(
            lower=min(first, second),
            upper=max(first, second),
        )

    return None


def has_explicitly_unavailable_level(markdown: str, label: str) -> bool:
    escaped_label = re.escape(label)
    label_re = re.compile(rf"^{escaped_label}\s*:\s*(.+)$", re.IGNORECASE)

    for raw_line in markdown.splitlines():
        line = _clean_line(raw_line)
        match = label_re.match(line)
        if not match:
            continue
        value = _normalize_for_match(match.group(1)).strip().casefold()
        return value.strip(" \t.;:!?") == "sin zona verificable"
    return False


def _clean_line(line: str) -> str:
    cleaned = str(line or "").strip()
    cleaned = re.sub(r"^[-*•]\s+", "", cleaned).strip()
    cleaned = cleaned.replace("**", "").replace("*", "").strip()
    return cleaned


def _normalize_for_match(value: str) -> str:
    fixed = (
        str(value or "")
        .replace("Ã³", "o")
        .replace("ÃƒÂ³", "o")
    )
    normalized = unicodedata.normalize("NFKD", fixed)
    return normalized.encode("ascii", "ignore").decode("ascii")


def format_exact_price(value: float) -> str:
    '''Round-trip a numeric price without six-digit truncation/locale ambiguity.'''
    number = Decimal(str(value))
    if not number.is_finite():
        raise ValueError('nonfinite_price')
    token = format(number, 'f')
    if '.' in token:
        token = token.rstrip('0').rstrip('.')
    # The existing bilingual reader treats three decimals as a thousands
    # group. An extra zero disambiguates the SAME value, not a new rounding.
    if '.' in token and len(token.partition('.')[2]) == 3:
        token += '0'
    return token


def _to_number(value: str) -> float | None:
    normalized = str(value or "").strip()
    if re.fullmatch(r"-?[0-9]{1,3}(?:,[0-9]{3})+(?:\.[0-9]+)?", normalized):
        normalized = normalized.replace(",", "")
    elif re.fullmatch(r"-?[0-9]{1,3}(?:\.[0-9]{3})+(?:,[0-9]+)?", normalized):
        normalized = normalized.replace(".", "").replace(",", ".")
    else:
        normalized = normalized.replace(",", ".")

    try:
        number = float(normalized)
    except ValueError:
        return None

    return number
