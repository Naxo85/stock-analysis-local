"""Parse structured analyst actions from IBKR news headlines."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


_COMPANY_PREFIX_RE = re.compile(r"^.+?\s+")
_TARGET_CHANGE_RE = re.compile(
    r"^(?P<company>.+?) Price Target (?P<action>Raised|Lowered) "
    r"to \$(?P<target>[\d,.]+)(?:/Share)? From \$(?P<previous>[\d,.]+) "
    r"by (?P<firm>.+)$",
    re.IGNORECASE,
)
_TARGET_MAINTAINED_RE = re.compile(
    r"^(?P<company>.+?) Price Target Maintained With a "
    r"\$(?P<target>[\d,.]+)(?:/Share)? by (?P<firm>.+)$",
    re.IGNORECASE,
)
_RATING_MAINTAINED_RE = re.compile(
    r"^(?P<company>.+?) Is Maintained at (?P<rating>.+?) by (?P<firm>.+)$",
    re.IGNORECASE,
)
_RATING_CHANGE_RE = re.compile(
    r"^(?P<company>.+?) Is (?P<action>Upgraded|Downgraded) "
    r"to (?P<rating>.+?) by (?P<firm>.+)$",
    re.IGNORECASE,
)
_COVERAGE_INITIATED_RE = re.compile(
    r"^(?P<firm>.+?) initiated (?P<company>.+?) "
    r"\((?P<ticker>[A-Z.\-]+)\) coverage with (?P<rating>.+?)"
    r"(?: and target \$(?P<target>[\d,.]+))?$",
    re.IGNORECASE,
)
_COVERAGE_REITERATED_RE = re.compile(
    r"^(?P<firm>.+?) reiterated (?P<company>.+?) "
    r"\((?P<ticker>[A-Z.\-]+)\) coverage with (?P<rating>.+?)"
    r"(?: and target \$(?P<target>[\d,.]+))?$",
    re.IGNORECASE,
)
_BRIEFING_RATING_CHANGE_RE = re.compile(
    r"^(?P<firm>.+?) (?P<action>upgraded|downgraded) (?P<company>.+?) "
    r"\((?P<ticker>[A-Z.\-]+)\) to (?P<rating>.+?)"
    r"(?: with target \$(?P<target>[\d,.]+))?$",
    re.IGNORECASE,
)

_BUY_RATINGS = {
    "buy",
    "strong buy",
    "overweight",
    "outperform",
    "positive",
    "mkt outperform",
    "market outperform",
}
_HOLD_RATINGS = {
    "hold",
    "neutral",
    "equal weight",
    "market perform",
    "sector perform",
    "sector weight",
    "peer perform",
}
_SELL_RATINGS = {
    "sell",
    "underweight",
    "underperform",
    "negative",
    "reduce",
}


@dataclass(frozen=True)
class ParsedAnalystAction:
    parse_status: str
    event_type: str | None
    firm: str | None
    rating: str | None = None
    rating_bucket: str = "unknown"
    target: float | None = None
    previous_target: float | None = None
    company: str | None = None
    ticker: str | None = None
    warnings: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "parse_status": self.parse_status,
            "event_type": self.event_type,
            "firm": self.firm,
            "rating": self.rating,
            "rating_bucket": self.rating_bucket,
            "target": self.target,
            "previous_target": self.previous_target,
            "company": self.company,
            "ticker": self.ticker,
            "warnings": list(self.warnings),
        }


def parse_analyst_headline(headline: str) -> dict[str, Any]:
    """Parse an IBKR analyst headline into a structured event."""

    text = _normalize_headline(headline)

    for parser in (
        _parse_target_change,
        _parse_target_maintained,
        _parse_rating_maintained,
        _parse_rating_change,
        _parse_coverage_initiated,
        _parse_coverage_reiterated,
        _parse_briefing_rating_change,
    ):
        parsed = parser(text)
        if parsed is not None:
            return parsed.to_dict()

    return ParsedAnalystAction(
        parse_status="unparsed",
        event_type=None,
        firm=None,
    ).to_dict()


def bucket_rating(rating: str | None) -> str:
    normalized = _clean_text(rating).lower()

    if normalized in _BUY_RATINGS:
        return "buy"
    if normalized in _HOLD_RATINGS:
        return "hold"
    if normalized in _SELL_RATINGS:
        return "sell"

    return "unknown"


def parse_price(value: str | None) -> float | None:
    if value is None:
        return None

    try:
        parsed = float(str(value).replace(",", ""))
    except ValueError:
        return None

    return int(parsed) if parsed.is_integer() else parsed


def _parse_target_change(text: str) -> ParsedAnalystAction | None:
    match = _TARGET_CHANGE_RE.match(text)
    if not match:
        return None

    action = match.group("action").lower()
    return ParsedAnalystAction(
        parse_status="parsed",
        event_type=f"price_target_{action}",
        firm=_clean_text(match.group("firm")),
        target=parse_price(match.group("target")),
        previous_target=parse_price(match.group("previous")),
        company=_clean_text(match.group("company")),
    )


def _parse_target_maintained(text: str) -> ParsedAnalystAction | None:
    match = _TARGET_MAINTAINED_RE.match(text)
    if not match:
        return None

    return ParsedAnalystAction(
        parse_status="parsed",
        event_type="price_target_maintained",
        firm=_clean_text(match.group("firm")),
        target=parse_price(match.group("target")),
        company=_clean_text(match.group("company")),
    )


def _parse_rating_maintained(text: str) -> ParsedAnalystAction | None:
    match = _RATING_MAINTAINED_RE.match(text)
    if not match:
        return None

    rating = _clean_text(match.group("rating"))
    return ParsedAnalystAction(
        parse_status="parsed",
        event_type="rating_maintained",
        firm=_clean_text(match.group("firm")),
        rating=rating,
        rating_bucket=bucket_rating(rating),
        company=_clean_text(match.group("company")),
    )


def _parse_rating_change(text: str) -> ParsedAnalystAction | None:
    match = _RATING_CHANGE_RE.match(text)
    if not match:
        return None

    rating = _clean_text(match.group("rating"))
    action = match.group("action").lower()
    return ParsedAnalystAction(
        parse_status="parsed",
        event_type=f"rating_{action}",
        firm=_clean_text(match.group("firm")),
        rating=rating,
        rating_bucket=bucket_rating(rating),
        company=_clean_text(match.group("company")),
    )


def _parse_coverage_initiated(text: str) -> ParsedAnalystAction | None:
    match = _COVERAGE_INITIATED_RE.match(text)
    if not match:
        return None

    rating = _clean_text(match.group("rating"))
    return ParsedAnalystAction(
        parse_status="parsed",
        event_type="coverage_initiated",
        firm=_clean_text(match.group("firm")),
        rating=rating,
        rating_bucket=bucket_rating(rating),
        target=parse_price(match.group("target")),
        company=_clean_text(match.group("company")),
        ticker=match.group("ticker").upper(),
    )


def _parse_coverage_reiterated(text: str) -> ParsedAnalystAction | None:
    match = _COVERAGE_REITERATED_RE.match(text)
    if not match:
        return None

    rating = _clean_text(match.group("rating"))
    return ParsedAnalystAction(
        parse_status="parsed",
        event_type="coverage_reiterated",
        firm=_clean_text(match.group("firm")),
        rating=rating,
        rating_bucket=bucket_rating(rating),
        target=parse_price(match.group("target")),
        company=_clean_text(match.group("company")),
        ticker=match.group("ticker").upper(),
    )


def _parse_briefing_rating_change(text: str) -> ParsedAnalystAction | None:
    match = _BRIEFING_RATING_CHANGE_RE.match(text)
    if not match:
        return None

    rating = _clean_text(match.group("rating"))
    action = match.group("action").lower()
    return ParsedAnalystAction(
        parse_status="parsed",
        event_type=f"rating_{action}",
        firm=_clean_text(match.group("firm")),
        rating=rating,
        rating_bucket=bucket_rating(rating),
        target=parse_price(match.group("target")),
        company=_clean_text(match.group("company")),
        ticker=match.group("ticker").upper(),
    )


def _normalize_headline(value: str) -> str:
    return " ".join(str(value or "").split())


def _clean_text(value: str | None) -> str:
    text = str(value or "").replace("-", " ")
    return " ".join(text.split()).strip()
