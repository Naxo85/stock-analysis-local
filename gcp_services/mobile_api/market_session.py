"""Match the Mercado refresh sessions and expose the next useful mobile poll."""
from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo


NEW_YORK = ZoneInfo('America/New_York')


def nth_weekday(year: int, month: int, weekday: int, occurrence: int) -> date:
    first = date(year, month, 1)
    return first + timedelta(days=(weekday - first.weekday()) % 7 + 7 * (occurrence - 1))


def last_weekday(year: int, month: int, weekday: int) -> date:
    last = (date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)) - timedelta(days=1)
    return last - timedelta(days=(last.weekday() - weekday) % 7)


def observed(day: date) -> date:
    return day - timedelta(days=1) if day.weekday() == 5 else day + timedelta(days=1) if day.weekday() == 6 else day


def easter_sunday(year: int) -> date:
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


def holidays(year: int) -> frozenset[date]:
    dates = {
        observed(date(year, 1, 1)), nth_weekday(year, 1, 0, 3), nth_weekday(year, 2, 0, 3),
        easter_sunday(year) - timedelta(days=2), last_weekday(year, 5, 0),
        observed(date(year, 6, 19)), observed(date(year, 7, 4)),
        nth_weekday(year, 9, 0, 1), nth_weekday(year, 11, 3, 4),
        observed(date(year, 12, 25)), observed(date(year + 1, 1, 1)),
    }
    return frozenset(d for d in dates if d.year == year)


def session_name(now: datetime) -> str:
    current = now.astimezone(NEW_YORK)
    if current.weekday() >= 5 or current.date() in holidays(current.year):
        return 'closed'
    clock = current.time().replace(tzinfo=None)
    if time(9, 30) <= clock < time(16):
        return 'regular'
    if time(4) <= clock < time(9, 30):
        return 'pre-market'
    if time(16) <= clock < time(20):
        return 'post-market'
    return 'closed'


def mobile_schedule(layout: dict, now: datetime | None = None) -> dict:
    current = (now or datetime.now(timezone.utc)).astimezone(NEW_YORK)
    session = session_name(current)
    configured = layout.get('data_refresh', {}).get('session_intervals_minutes', {})
    value = configured.get(session)
    try:
        interval = int(value)
        if not 1 <= interval <= 60:
            interval = None
    except (TypeError, ValueError):
        interval = None
    transition = None
    for day_offset in range(9):
        day = current.date() + timedelta(days=day_offset)
        for hour, minute in ((4, 0), (9, 30), (16, 0), (20, 0)):
            candidate = datetime.combine(day, time(hour, minute), NEW_YORK)
            if candidate <= current:
                continue
            if session_name(candidate - timedelta(seconds=1)) != session_name(candidate + timedelta(seconds=1)):
                transition = candidate
                break
        if transition is not None:
            break
    poll_seconds = interval * 60 if interval is not None else None
    if transition is not None and poll_seconds is not None:
        poll_seconds = min(poll_seconds, max(15, int((transition - current).total_seconds()) + 5))
    return {
        'session': session, 'refresh_interval_minutes': interval,
        'poll_after_seconds': poll_seconds,
        'next_session_at': transition.astimezone(timezone.utc).isoformat() if transition else None,
    }
