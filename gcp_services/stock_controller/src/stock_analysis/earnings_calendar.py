"""Display-only earnings calendar. Dates are supplied data, never model prose."""
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

DISPLAY_ZONE = ZoneInfo('Europe/Madrid')
HOURS = {'bmo': 'antes de la apertura', 'amc': 'después del cierre',
         'dmh': 'durante la sesión'}


def calendar_from_reports(payloads):
    result = {}
    for symbol, report in payloads.items():
        if not isinstance(report, dict) or report.get('symbol') != symbol or report.get('analysis_status') != 'ok':
            continue
        summary = report.get('analyst_ratings_summary')
        if not isinstance(summary, dict) or summary.get('status') != 'ok':
            continue
        event_date = valid_date(summary.get('next_earnings_date'))
        if event_date is not None:
            result[symbol] = {'date': event_date.isoformat(), 'as_of': summary.get('as_of'),
                              'source': 'Finnhub · calendario publicado',
                              'hour': summary.get('next_earnings_hour') if summary.get('next_earnings_hour') in HOURS else None}
    return result


def valid_date(value):
    if not isinstance(value, str):
        return None
    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        return None
    return parsed if parsed.isoformat() == value else None


def earnings_alert(event, *, now=None):
    if not isinstance(event, dict):
        return None
    event_date = valid_date(event.get('date'))
    if event_date is None:
        return None
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        raise ValueError('earnings display requires an aware clock')
    days = (event_date - current.astimezone(DISPLAY_ZONE).date()).days
    if not 0 <= days <= 7:
        return None
    label = 'hoy' if days == 0 else 'mañana' if days == 1 else f'en {days} días'
    return {**event, 'days': days, 'label': label, 'severity': 'red' if days <= 1 else 'orange',
            'hour_label': HOURS.get(event.get('hour'))}
