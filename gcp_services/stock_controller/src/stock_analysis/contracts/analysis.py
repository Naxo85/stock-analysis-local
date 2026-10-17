from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import math
from typing import Any


@dataclass(frozen=True)
class PriceRange:
    lower: float
    upper: float


@dataclass(frozen=True)
class AnalysisSheetRecord:
    ticker: str
    score: float | None
    entry: PriceRange | None
    washout: PriceRange | None
    entry_stop: float | None
    washout_stop: float | None
    resistance: PriceRange | None
    entry_strength: int | None
    washout_strength: int | None
    resistance_strength: int | None
    generated_at: datetime
    report_url: str
    score_background: str | None
    score_note: str
    entry_strength_category: str | None = None
    entry_strength_factors: str | None = None
    washout_strength_category: str | None = None
    washout_strength_factors: str | None = None
    resistance_strength_category: str | None = None
    resistance_strength_factors: str | None = None
    resistance_strength_breakdown: dict[str, int] | None = None
    thesis_score: float | None = None
    setup_score: float | None = None
    thesis_reason: str = ""
    setup_reason: str = ""
    entry_support_validity: dict[str, Any] | None = None
    washout_support_validity: dict[str, Any] | None = None


def support_validity_floor(level: PriceRange | None, extent: Any) -> float | None:
    """Unknown, malformed, or stale-range estimates must not extend green."""
    if level is None or not isinstance(extent, dict):
        return None
    if extent.get('range') != {'lower': level.lower, 'upper': level.upper}:
        return None
    bound = extent.get('lower_bound')
    if (type(bound) not in (int, float) or not math.isfinite(bound)
            or bound <= 0 or bound > level.lower
            or not isinstance(extent.get('reason'), str) or not extent['reason'].strip()):
        return None
    try:
        stamp = datetime.fromisoformat(str(extent.get('assessed_at')).replace('Z', '+00:00'))
        if stamp.tzinfo is None:
            return None
    except (TypeError, ValueError):
        return None
    return float(bound)
