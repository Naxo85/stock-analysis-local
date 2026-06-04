"""Validation helpers for generated stock analysis markdown."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
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
class ValidationResult:
    ok: bool
    status: str
    errors: tuple[str, ...]
    score: float | None = None
    entry_range: PriceRange | None = None
    ambitious_entry_range: PriceRange | None = None

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
        }


_SCORE_RE = re.compile(
    r"Valoracion\s*:\s*([0-9]+(?:[.,][0-9]+)?)\s*/\s*10",
    re.IGNORECASE,
)

_NUMBER_RE = re.compile(
    r"-?[0-9]+(?:[.,][0-9]+)?"
)


def validate_markdown(markdown: str | None) -> ValidationResult:
    """Validate the minimum contract expected by the Sheet/parser."""

    text = markdown or ""
    errors: list[str] = []

    if not text.strip():
        return ValidationResult(
            ok=False,
            status="failed",
            errors=("markdown_empty",),
        )

    score = extract_score(text)
    if score is None:
        errors.append("missing_or_invalid_score: expected 'Valoración: X / 10'")
    elif score < 0 or score > 10:
        errors.append("score_out_of_range: expected 0 <= score <= 10")

    entry_range = extract_range(text, "Entrada")
    if entry_range is None:
        errors.append("missing_or_invalid_entry_range: expected 'Entrada: $A - $B'")

    ambitious_entry_range = extract_range(text, "Entrada ambiciosa")
    if ambitious_entry_range is None:
        errors.append(
            "missing_or_invalid_ambitious_entry_range: "
            "expected 'Entrada ambiciosa: $C - $D'"
        )

    ok = not errors

    return ValidationResult(
        ok=ok,
        status="ok" if ok else "failed",
        errors=tuple(errors),
        score=score,
        entry_range=entry_range,
        ambitious_entry_range=ambitious_entry_range,
    )


def extract_score(markdown: str) -> float | None:
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


def _to_number(value: str) -> float | None:
    normalized = str(value or "").strip().replace(",", ".")

    try:
        number = float(normalized)
    except ValueError:
        return None

    return number
