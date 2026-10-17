from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, datetime
from typing import Any


@dataclass(frozen=True)
class DailyBar:
    session_date: date
    high: float
    low: float
    close: float
    volume: float | None = None


@dataclass(frozen=True)
class Quote:
    ticker: str
    price: float
    observed_at: datetime
    source: str
    day_change: float | None = None
    cached: bool = False


@dataclass(frozen=True)
class TickerMarketData:
    quote: Quote
    daily_bars: tuple[DailyBar, ...]


@dataclass(frozen=True)
class TickerMetrics:
    ticker: str
    price: float
    day_change: float | None
    strength: float | None
    return_5d: float | None
    return_20d: float | None
    volatility: float | None
    drawdown_6m: float | None
    distance_from_6m_low: float | None
    drawdown_percentile: int | None
    drawdown_samples: int
    observed_at: datetime
    source: str
    cached: bool = False

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["observed_at"] = self.observed_at.isoformat()
        return payload


@dataclass(frozen=True)
class BenchmarkMetrics:
    ticker: str
    day_change: float | None
    drawdown: float | None
    return_20d: float | None
    observed_at: datetime
    source: str
    cached: bool = False
    drawdown_percentile: int | None = None
    drawdown_samples: int = 0

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["observed_at"] = self.observed_at.isoformat()
        return payload


@dataclass(frozen=True)
class GeneralMarketOverview:
    risk_score: int | None
    risk_label: str | None
    vxn_value: float | None
    vxn_change: float | None
    vxn_label: str | None
    vxn_observed_at: datetime | None
    vxn_source: str | None
    qqq_day_change: float | None
    qqq_drawdown_6m: float | None
    qqq_return_20d: float | None
    trading_date: date | None
    core_date: date | None
    sentiment_observed_at: datetime | None
    sentiment_source: str | None
    trading_note: str
    core_note: str
    observed_at: datetime
    sources: tuple[str, ...]
    failures: dict[str, str]

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["observed_at"] = self.observed_at.isoformat()
        payload["trading_date"] = (
            self.trading_date.isoformat() if self.trading_date else None
        )
        payload["core_date"] = self.core_date.isoformat() if self.core_date else None
        payload["sentiment_observed_at"] = (
            self.sentiment_observed_at.isoformat()
            if self.sentiment_observed_at
            else None
        )
        payload["vxn_observed_at"] = (
            self.vxn_observed_at.isoformat() if self.vxn_observed_at else None
        )
        payload["sources"] = list(self.sources)
        return payload


@dataclass(frozen=True)
class MarketSnapshot:
    schema_version: int
    generated_at: datetime
    universe: tuple[str, ...]
    metrics: tuple[TickerMetrics, ...]
    failures: dict[str, str]
    benchmarks: tuple[BenchmarkMetrics, ...] = ()
    general: GeneralMarketOverview | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "generated_at": self.generated_at.isoformat(),
            "universe": list(self.universe),
            "metrics": [item.as_dict() for item in self.metrics],
            "failures": self.failures,
            "benchmarks": [item.as_dict() for item in self.benchmarks],
            "general": self.general.as_dict() if self.general else None,
        }
