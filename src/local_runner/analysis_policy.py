"""Deterministic model routing for individual and batch stock analyses."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any
from zoneinfo import ZoneInfo


SOL_MODEL = "gpt-5.6-sol"
TERRA_MODEL = "gpt-5.6-terra"
LUNA_MODEL = "gpt-5.6-luna"
DEFAULT_REASONING_EFFORT = "medium"
PROMOTE_TO_SOL_SCORE = 7.0
DEMOTE_TO_TERRA_SCORE = 6.5
DAILY_SCORE_REVIEW_DELTA = 1.0
REFERENCE_MAX_AGE_DAYS = 7
MADRID_TZ = ZoneInfo("Europe/Madrid")


@dataclass(frozen=True)
class TickerRecord:
    ticker: str
    owned: bool = False
    ownership_source: str | None = None


@dataclass(frozen=True)
class ReferenceSummary:
    found: bool = False
    generated_at: datetime | None = None
    score: float | None = None
    tier: str | None = None
    model: str | None = None
    score_basis: str | None = None

    def is_fresh(self, on_date: date, max_age_days: int = REFERENCE_MAX_AGE_DAYS) -> bool:
        if not self.found or self.generated_at is None:
            return False
        reference_date = self.generated_at.astimezone(MADRID_TZ).date()
        age = (on_date - reference_date).days
        return 0 <= age <= max_age_days


@dataclass(frozen=True)
class RouteDecision:
    ticker: str
    action: str
    analysis_kind: str | None
    tier: str
    model: str | None
    reasoning_effort: str
    reviewer_model: str | None
    reason: str
    owned: bool


def batch_day_mode(on_date: date) -> str:
    """Return reference/daily/skip for the manual batch calendar."""
    weekday = on_date.weekday()
    if weekday == 6:
        return "reference"
    if weekday <= 3:
        return "daily"
    return "skip"


def resolve_tier(
    *,
    owned: bool,
    reference_score: float | None,
    previous_tier: str | None,
) -> str:
    if owned:
        return "priority"
    if reference_score is None:
        return previous_tier if previous_tier in {"priority", "tracking"} else "tracking"
    if reference_score >= PROMOTE_TO_SOL_SCORE:
        return "priority"
    if reference_score < DEMOTE_TO_TERRA_SCORE:
        return "tracking"
    if previous_tier in {"priority", "tracking"}:
        return previous_tier
    return "tracking"


def route_ticker(
    record: TickerRecord,
    reference: ReferenceSummary,
    *,
    on_date: date,
    requested_mode: str = "auto",
    model_override: str | None = None,
) -> RouteDecision:
    if requested_mode not in {"auto", "reference", "daily"}:
        raise ValueError(f"unsupported_analysis_mode: {requested_mode}")

    tier = resolve_tier(
        owned=record.owned,
        reference_score=reference.score,
        previous_tier=reference.tier,
    )
    calendar_mode = batch_day_mode(on_date)
    if requested_mode == "auto":
        if calendar_mode == "skip":
            return RouteDecision(
                ticker=record.ticker,
                action="skip",
                analysis_kind=None,
                tier=tier,
                model=None,
                reasoning_effort=DEFAULT_REASONING_EFFORT,
                reviewer_model=None,
                reason="friday_or_saturday",
                owned=record.owned,
            )
        analysis_kind = calendar_mode
        if analysis_kind == "daily" and not reference.is_fresh(on_date):
            analysis_kind = "reference"
            route_reason = "missing_or_stale_reference"
        else:
            route_reason = f"calendar_{calendar_mode}"
    else:
        analysis_kind = requested_mode
        route_reason = f"manual_{requested_mode}"

    if analysis_kind == "daily" and reference.score_basis == "legacy_mixed":
        analysis_kind = "reference"
        route_reason = "separate_thesis_setup_migration"

    if analysis_kind == "reference":
        model = SOL_MODEL if tier == "priority" else TERRA_MODEL
        reviewer = None
    else:
        model = TERRA_MODEL if tier == "priority" else LUNA_MODEL
        reviewer = SOL_MODEL if tier == "priority" else TERRA_MODEL

    if model_override:
        model = model_override
        route_reason += "+model_override"

    return RouteDecision(
        ticker=record.ticker,
        action="run",
        analysis_kind=analysis_kind,
        tier=tier,
        model=model,
        reasoning_effort=DEFAULT_REASONING_EFFORT,
        reviewer_model=reviewer,
        reason=route_reason,
        owned=record.owned,
    )


def parse_reference_summary(payload: dict[str, Any] | None) -> ReferenceSummary:
    if not isinstance(payload, dict):
        return ReferenceSummary()
    generated_at = _parse_datetime(
        payload.get("reference_generated_at") or payload.get("generated_at")
    )
    score = _number_or_none(
        payload.get("reference_score")
        if "reference_score" in payload
        else _nested(payload, "decision", "score")
    )
    if score is None:
        score = _number_or_none(_nested(payload, "validation", "score"))
    return ReferenceSummary(
        found=payload.get("analysis_status") == "ok" or bool(payload.get("reference_model")),
        generated_at=generated_at,
        score=score,
        tier=_string_or_none(payload.get("reference_tier")),
        model=_string_or_none(payload.get("reference_model") or payload.get("generation_model")),
        score_basis=_string_or_none(_nested(payload, "decision", "score_basis")) or "legacy_mixed",
    )


def _nested(payload: dict[str, Any], first: str, second: str) -> Any:
    value = payload.get(first)
    return value.get(second) if isinstance(value, dict) else None


def _parse_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=ZoneInfo("UTC"))
    return parsed


def _number_or_none(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _string_or_none(value: Any) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None
