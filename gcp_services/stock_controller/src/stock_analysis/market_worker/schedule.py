from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from stock_analysis.market_worker.session import MarketSession, us_market_session


@dataclass(frozen=True)
class ScheduleBucket:
    key: str
    session: MarketSession
    starts_at: datetime


def schedule_bucket(now: datetime | None = None) -> ScheduleBucket:
    session = us_market_session(now)
    interval = session.target_interval_minutes
    if interval is None:
        raise ValueError(f"Session without target interval: {session.name}")

    starts_at = session.now_et.replace(second=0, microsecond=0)
    starts_at -= timedelta(minutes=starts_at.minute % interval)
    return ScheduleBucket(
        key=f"{session.name}:{starts_at.isoformat()}",
        session=session,
        starts_at=starts_at,
    )
