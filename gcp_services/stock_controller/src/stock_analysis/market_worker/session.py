from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo


NEW_YORK = ZoneInfo("America/New_York")


@dataclass(frozen=True)
class MarketSession:
    name: str
    open: bool
    target_interval_minutes: int | None
    now_et: datetime


def _nth_weekday(year: int, month: int, weekday: int, occurrence: int) -> date:
    first = date(year, month, 1)
    offset = (weekday - first.weekday()) % 7
    return first + timedelta(days=offset + 7 * (occurrence - 1))


def _last_weekday(year: int, month: int, weekday: int) -> date:
    if month == 12:
        last = date(year + 1, 1, 1) - timedelta(days=1)
    else:
        last = date(year, month + 1, 1) - timedelta(days=1)
    return last - timedelta(days=(last.weekday() - weekday) % 7)


def _observed(day: date) -> date:
    if day.weekday() == 5:
        return day - timedelta(days=1)
    if day.weekday() == 6:
        return day + timedelta(days=1)
    return day


def _easter_sunday(year: int) -> date:
    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    correction = (32 + 2 * e + 2 * i - h - k) % 7
    remainder = (a + 11 * h + 22 * correction) // 451
    month = (h + correction - 7 * remainder + 114) // 31
    day = (h + correction - 7 * remainder + 114) % 31 + 1
    return date(year, month, day)


def standard_us_market_holidays(year: int) -> frozenset[date]:
    holidays = {
        _observed(date(year, 1, 1)),
        _nth_weekday(year, 1, 0, 3),
        _nth_weekday(year, 2, 0, 3),
        _easter_sunday(year) - timedelta(days=2),
        _last_weekday(year, 5, 0),
        _observed(date(year, 6, 19)),
        _observed(date(year, 7, 4)),
        _nth_weekday(year, 9, 0, 1),
        _nth_weekday(year, 11, 3, 4),
        _observed(date(year, 12, 25)),
        _observed(date(year + 1, 1, 1)),
    }
    return frozenset(day for day in holidays if day.year == year)


def us_market_session(now: datetime | None = None) -> MarketSession:
    current = (now or datetime.now(tz=NEW_YORK)).astimezone(NEW_YORK)
    if (
        current.weekday() >= 5
        or current.date() in standard_us_market_holidays(current.year)
    ):
        return MarketSession("closed", False, 60, current)

    current_time = current.time().replace(tzinfo=None)
    if time(9, 30) <= current_time < time(16, 0):
        return MarketSession("regular", True, 1, current)
    if time(4, 0) <= current_time < time(9, 30):
        return MarketSession("pre-market", True, 5, current)
    if time(16, 0) <= current_time < time(20, 0):
        return MarketSession("post-market", True, 5, current)
    return MarketSession("closed", False, 60, current)
