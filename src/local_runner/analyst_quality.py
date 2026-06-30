"""Quality scoring for optional analyst consensus inputs."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_MAX_FRESH_DAYS = 90
_TARGET_FIELDS = ("target_low", "target_mean", "target_median", "target_high")
_RECOMMENDATION_FIELDS = (
    "strong_buy",
    "buy",
    "hold",
    "sell",
    "strong_sell",
)
_TARGET_ALIASES = {
    "target_low": ("target_low", "targetLow", "lowTarget", "priceTargetLow"),
    "target_mean": ("target_mean", "targetMean", "targetMeanPrice", "priceTargetAverage"),
    "target_median": ("target_median", "targetMedian", "targetMedianPrice"),
    "target_high": ("target_high", "targetHigh", "highTarget", "priceTargetHigh"),
}
_RECOMMENDATION_ALIASES = {
    "strong_buy": ("strong_buy", "strongBuy", "strongbuy"),
    "buy": ("buy",),
    "hold": ("hold",),
    "sell": ("sell",),
    "strong_sell": ("strong_sell", "strongSell", "strongsell"),
}


@dataclass(frozen=True)
class AnalystConsensusQuality:
    """Structured quality result for downstream prompts and JSON payloads."""

    status: str
    grade: str
    score: int
    analyst_count: int | None
    as_of: str | None
    source: str | None
    price_target: dict[str, Any]
    recommendations: dict[str, Any]
    checks: dict[str, Any]
    warnings: tuple[str, ...]
    usage: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "grade": self.grade,
            "score": self.score,
            "analyst_count": self.analyst_count,
            "as_of": self.as_of,
            "source": self.source,
            "price_target": self.price_target,
            "recommendations": self.recommendations,
            "checks": self.checks,
            "warnings": list(self.warnings),
            "usage": self.usage,
        }


def load_analyst_quality_context(
    repo_root: Path,
    symbol: str,
    *,
    current_price: float | None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Load the latest optional analyst consensus file and score its quality."""

    raw = load_latest_analyst_consensus(repo_root, symbol)
    quality = evaluate_analyst_consensus(
        raw,
        current_price=current_price,
        now=now,
    )
    return quality.to_dict()


def load_latest_analyst_consensus(repo_root: Path, symbol: str) -> dict[str, Any] | None:
    """Return latest analyst consensus JSON for a ticker, when present."""

    consensus_dir = repo_root / "data" / "analyst_consensus" / symbol.strip().upper()

    if not consensus_dir.exists():
        return None

    latest_path = consensus_dir / "latest.json"
    candidate_paths = [latest_path] if latest_path.exists() else sorted(
        consensus_dir.glob("*.json")
    )

    if not candidate_paths:
        return None

    raw_path = candidate_paths[-1]

    try:
        payload = json.loads(raw_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {
            "source": "local_file",
            "quality_warning": f"invalid_json: {raw_path}",
        }

    return payload if isinstance(payload, dict) else None


def evaluate_analyst_consensus(
    raw: dict[str, Any] | None,
    *,
    current_price: float | None,
    now: datetime | None = None,
    max_fresh_days: int = DEFAULT_MAX_FRESH_DAYS,
) -> AnalystConsensusQuality:
    """Score analyst consensus quality without depending on a data provider."""

    if not raw:
        return _unavailable("missing_consensus_data")

    now = now or datetime.now(timezone.utc)
    warnings: list[str] = []

    source = _clean_string(raw.get("source") or raw.get("provider"))
    as_of = _extract_as_of(raw)
    age_days = _age_days(as_of, now)
    analyst_count = _extract_analyst_count(raw)
    targets = _extract_price_targets(raw, current_price=current_price)
    recommendations = _extract_recommendations(raw)

    freshness_score, freshness_status = _score_freshness(
        age_days,
        has_as_of=as_of is not None,
        max_fresh_days=max_fresh_days,
    )
    coverage_score, coverage_status = _score_coverage(analyst_count)
    target_score, target_status = _score_targets(targets)
    recommendation_score, recommendation_status = _score_recommendations(
        recommendations
    )
    traceability_score, traceability_status = _score_traceability(source, as_of)

    if raw.get("quality_warning"):
        warnings.append(str(raw["quality_warning"]))
    if age_days is None:
        warnings.append("missing_or_invalid_as_of")
    elif age_days > max_fresh_days:
        warnings.append(f"stale_consensus: {age_days} days old")
    if analyst_count is None:
        warnings.append("missing_analyst_count")
    elif analyst_count < 3:
        warnings.append("low_analyst_count")
    if target_status == "missing":
        warnings.append("missing_price_targets")
    elif target_status == "wide_dispersion":
        warnings.append("wide_price_target_dispersion")
    if recommendation_status == "missing":
        warnings.append("missing_recommendation_breakdown")
    if not source:
        warnings.append("missing_source")

    score = round(
        freshness_score * 0.30
        + coverage_score * 0.25
        + target_score * 0.20
        + recommendation_score * 0.15
        + traceability_score * 0.10
    )

    status, grade, usage = _classify(score, warnings)

    checks = {
        "freshness": {
            "status": freshness_status,
            "score": freshness_score,
            "age_days": age_days,
            "max_fresh_days": max_fresh_days,
        },
        "coverage": {
            "status": coverage_status,
            "score": coverage_score,
        },
        "price_targets": {
            "status": target_status,
            "score": target_score,
        },
        "recommendations": {
            "status": recommendation_status,
            "score": recommendation_score,
        },
        "traceability": {
            "status": traceability_status,
            "score": traceability_score,
        },
    }

    return AnalystConsensusQuality(
        status=status,
        grade=grade,
        score=score,
        analyst_count=analyst_count,
        as_of=as_of,
        source=source,
        price_target=targets,
        recommendations=recommendations,
        checks=checks,
        warnings=tuple(warnings),
        usage=usage,
    )


def _unavailable(reason: str) -> AnalystConsensusQuality:
    return AnalystConsensusQuality(
        status="unavailable",
        grade="none",
        score=0,
        analyst_count=None,
        as_of=None,
        source=None,
        price_target={},
        recommendations={},
        checks={"reason": reason},
        warnings=(reason,),
        usage="Do not mention analyst consensus unless independently verified.",
    )


def _extract_as_of(raw: dict[str, Any]) -> str | None:
    for key in ("as_of", "date", "updated_at", "last_updated", "lastUpdated", "period"):
        normalized = _parse_date(raw.get(key))
        if normalized:
            return normalized
    return None


def _extract_analyst_count(raw: dict[str, Any]) -> int | None:
    for key in ("analyst_count", "number_of_analysts", "num_analysts"):
        count = _to_int(raw.get(key))
        if count is not None:
            return count

    recommendations = raw.get("recommendations")
    if isinstance(recommendations, list):
        recommendations = recommendations[0] if recommendations else {}

    if isinstance(recommendations, dict):
        counts = [
            _first_int(recommendations, aliases)
            for aliases in _RECOMMENDATION_ALIASES.values()
        ]
        usable_counts = [count for count in counts if count is not None]
        if usable_counts:
            return sum(usable_counts)

    return None


def _extract_price_targets(
    raw: dict[str, Any],
    *,
    current_price: float | None,
) -> dict[str, Any]:
    targets_source = raw.get("price_target")
    targets_raw = targets_source if isinstance(targets_source, dict) else raw
    targets = {
        field: _first_float(targets_raw, aliases)
        for field, aliases in _TARGET_ALIASES.items()
    }

    current = _to_float(current_price)
    mean = targets.get("target_mean")

    if current and mean:
        targets["upside_to_mean_pct"] = round(((mean / current) - 1) * 100, 2)

    available = [value for value in targets.values() if isinstance(value, float)]
    if not available:
        return {}

    return targets


def _extract_recommendations(raw: dict[str, Any]) -> dict[str, Any]:
    recommendations = raw.get("recommendations")
    if isinstance(recommendations, list):
        recommendations = recommendations[0] if recommendations else {}

    source = recommendations if isinstance(recommendations, dict) else raw
    counts = {
        field: _first_int(source, aliases) or 0
        for field, aliases in _RECOMMENDATION_ALIASES.items()
    }
    total = sum(counts.values())

    if total <= 0:
        return {}

    buyish = counts["strong_buy"] + counts["buy"]
    bearish = counts["sell"] + counts["strong_sell"]
    counts.update(
        {
            "total": total,
            "buyish_pct": round((buyish / total) * 100, 1),
            "bearish_pct": round((bearish / total) * 100, 1),
        }
    )

    return counts


def _score_freshness(
    age_days: int | None,
    *,
    has_as_of: bool,
    max_fresh_days: int,
) -> tuple[int, str]:
    if not has_as_of or age_days is None:
        return 10, "missing"
    if age_days <= 14:
        return 100, "fresh"
    if age_days <= 45:
        return 80, "recent"
    if age_days <= max_fresh_days:
        return 55, "aging"
    return 0, "stale"


def _score_coverage(analyst_count: int | None) -> tuple[int, str]:
    if analyst_count is None:
        return 20, "missing"
    if analyst_count >= 10:
        return 100, "broad"
    if analyst_count >= 5:
        return 75, "usable"
    if analyst_count >= 3:
        return 45, "thin"
    if analyst_count > 0:
        return 15, "very_thin"
    return 0, "missing"


def _score_targets(targets: dict[str, Any]) -> tuple[int, str]:
    if not targets:
        return 0, "missing"

    mean = _to_float(targets.get("target_mean"))
    low = _to_float(targets.get("target_low"))
    high = _to_float(targets.get("target_high"))

    if not mean or mean <= 0:
        return 20, "partial"

    if low and high and high >= low:
        dispersion = (high - low) / mean
        if dispersion <= 0.35:
            return 100, "tight"
        if dispersion <= 0.75:
            return 75, "normal"
        if dispersion <= 1.25:
            return 45, "wide_dispersion"
        return 20, "extreme_dispersion"

    return 60, "partial"


def _score_recommendations(recommendations: dict[str, Any]) -> tuple[int, str]:
    total = _to_int(recommendations.get("total")) if recommendations else None
    if not total:
        return 0, "missing"
    if total >= 10:
        return 100, "broad"
    if total >= 5:
        return 75, "usable"
    if total >= 3:
        return 45, "thin"
    return 20, "very_thin"


def _score_traceability(source: str | None, as_of: str | None) -> tuple[int, str]:
    if source and as_of:
        return 100, "traceable"
    if source or as_of:
        return 45, "partial"
    return 0, "missing"


def _classify(score: int, warnings: list[str]) -> tuple[str, str, str]:
    if "missing_consensus_data" in warnings:
        return (
            "unavailable",
            "none",
            "Do not mention analyst consensus unless independently verified.",
        )
    if any(warning.startswith("stale_consensus") for warning in warnings):
        return (
            "stale",
            "low",
            "Use only as historical context; do not lean on it for the rating.",
        )
    if score >= 80:
        return (
            "usable",
            "high",
            "Can be used as supporting evidence, never as the main thesis driver.",
        )
    if score >= 55:
        return (
            "usable_with_caution",
            "medium",
            "Mention cautiously and qualify source quality.",
        )
    return (
        "weak",
        "low",
        "Do not use for conclusions; at most note that analyst data is weak.",
    )


def _age_days(as_of: str | None, now: datetime) -> int | None:
    if not as_of:
        return None

    parsed = _parse_date(as_of)
    if not parsed:
        return None

    as_of_date = date.fromisoformat(parsed)
    return max(0, (now.date() - as_of_date).days)


def _parse_date(value: Any) -> str | None:
    if not value:
        return None

    text = str(value).strip()
    if not text:
        return None

    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"

    try:
        return datetime.fromisoformat(text).date().isoformat()
    except ValueError:
        pass

    try:
        return date.fromisoformat(text[:10]).isoformat()
    except ValueError:
        return None


def _clean_string(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _to_float(value: Any) -> float | None:
    if value is None:
        return None

    try:
        return float(str(value).replace(",", "."))
    except (TypeError, ValueError):
        return None


def _first_float(source: dict[str, Any], keys: tuple[str, ...]) -> float | None:
    for key in keys:
        value = _to_float(source.get(key))
        if value is not None:
            return value
    return None


def _first_int(source: dict[str, Any], keys: tuple[str, ...]) -> int | None:
    for key in keys:
        value = _to_int(source.get(key))
        if value is not None:
            return value
    return None


def _to_int(value: Any) -> int | None:
    if value is None:
        return None

    try:
        return int(float(str(value).replace(",", ".")))
    except (TypeError, ValueError):
        return None
