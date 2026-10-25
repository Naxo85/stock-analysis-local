"""Pure NYSE cash-equity session calendar shared by acquisition and ITV.

Regular holiday rules extracted unchanged from adaptive_policy. Early closes:
https://www.nyse.com/markets/hours-calendars (cash equities 13:00 ET).
Exceptional closures remain explicitly configurable by callers.
"""
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

NY = ZoneInfo("America/New_York")

def _observed(day: date) -> date:
    return day + timedelta(days=1 if day.weekday() == 6 else -1 if day.weekday() == 5 else 0)


def _nth(year, month, weekday, n):
    start = date(year, month, 1)
    return start + timedelta(days=(weekday-start.weekday()) % 7 + (n-1)*7)


def _easter(year):
    a, b, c = year % 19, year // 100, year % 100
    d, e = b // 4, b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19*a + b-d-g+15) % 30
    i, k = c // 4, c % 4
    l = (32+2*e+2*i-h-k) % 7
    m = (a+11*h+22*l) // 451
    return date(year, (h+l-7*m+114)//31, (h+l-7*m+114)%31+1)


def market_session(day: date, extra=()) -> bool:
    """NYSE sessions; early closes count, exceptional closures configurable."""
    y = day.year
    holidays = {_nth(y, 1, 0, 3), _nth(y, 2, 0, 3), _easter(y)-timedelta(days=2),
                _nth(y, 9, 0, 1), _nth(y, 11, 3, 4), _observed(date(y, 7, 4)),
                _observed(date(y, 12, 25))}
    new_year = date(y, 1, 1)
    holidays.add(new_year + timedelta(days=1) if new_year.weekday() == 6 else new_year)
    holidays.add(date(y, 5, 31) - timedelta(days=date(y, 5, 31).weekday()))
    if y >= 2022:
        holidays.add(_observed(date(y, 6, 19)))
    return day.weekday() < 5 and day not in holidays and day.isoformat() not in extra



def session_close(day, extra=()):
    if not market_session(day, extra):
        return None
    early = (day == _nth(day.year, 11, 3, 4) + timedelta(days=1)
             or (day.month == 7 and day.day == 3)
             or (day.month == 12 and day.day == 24))
    return datetime.combine(day, time(13 if early else 16), NY)


def latest_completed_session(as_of, extra=()):
    if as_of.tzinfo is None:
        raise ValueError("snapshot_timezone_required")
    day = as_of.astimezone(NY).date()
    for _ in range(370):
        close = session_close(day, extra)
        if close is not None and as_of >= close:
            return day
        day -= timedelta(days=1)
    raise ValueError("market_calendar_unavailable")


def is_completed_session(day, as_of, extra=()):
    close = session_close(day, extra)
    return close is not None and as_of >= close
