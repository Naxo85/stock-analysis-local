"""Bounded compatibility adapter for IBKR's observed backward news cursor.

The service does not honor its documented date-range contract for this feed.
Only actual exhaustion (hasMore=False) completes acquisition. Crossing the
requested lower date is insufficient. Keep every raw row until local filtering.
"""
from datetime import datetime, timedelta, timezone
from time import monotonic
import math

DEFAULT_PAGE_TIMEOUT = 30.0
DEFAULT_MAX_PAGES = 16
DEFAULT_TOTAL_TIMEOUT = 180.0
# Surrounding source subprocesses must allow connection, collection and persistence.
DEFAULT_NEWS_PROCESS_TIMEOUT = 210
# One existing retry plus a possible 120s Gateway restart; no model clock changes.
DEFAULT_NEWS_BACKFILL_TIMEOUT = 600


def _timestamp(item):
    value = getattr(item, 'time', None)
    if not isinstance(value, datetime):
        raise RuntimeError('ibkr_news_pagination_invalid_timestamp')
    # Preserve the preexisting provider timestamp interpretation explicitly.
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def _identity(item):
    values = (getattr(item, 'providerCode', None), getattr(item, 'articleId', None))
    if not all(isinstance(v, str) and v.strip() for v in values):
        raise RuntimeError('ibkr_news_pagination_missing_identity')
    return values


def _fingerprint(item):
    headline = getattr(item, 'headline', None)
    if not isinstance(headline, str):
        raise RuntimeError('ibkr_news_pagination_invalid_headline')
    return _timestamp(item), headline


def collect_cached_headlines(fetch_page, *, start, end, limit, page_timeout=DEFAULT_PAGE_TIMEOUT,
                             max_pages=DEFAULT_MAX_PAGES, total_timeout=DEFAULT_TOTAL_TIMEOUT,
                             clock=monotonic):
    """Collect a provider's available cached prefix through actual terminal False.

    fetch_page(cursor, limit, timeout) returns rows and the exact page terminal.
    A one-second overlap retains all records sharing the boundary second. A
    saturated second, lost overlap, conflicting identity or no progress fails.
    No request increases the caller's per-page limit beyond the API maximum300.
    """
    if (type(limit) is not int or not 1 <= limit <= 300 or type(max_pages) is not int
            or max_pages < 1 or not math.isfinite(page_timeout) or page_timeout <= 0
            or not math.isfinite(total_timeout) or total_timeout <= 0):
        raise ValueError('ibkr_news_pagination_invalid_limits')
    if (not isinstance(start, datetime) or not isinstance(end, datetime)
            or start.tzinfo is None or end.tzinfo is None or start > end):
        raise ValueError('ibkr_news_pagination_invalid_window')
    start, end = start.astimezone(timezone.utc), end.astimezone(timezone.utc)
    cursor = end.replace(microsecond=0) + timedelta(seconds=1)
    began = clock()
    seen = {}
    boundary = set()
    pages = []
    duplicate_count = 0
    for number in range(1, max_pages + 1):
        remaining = total_timeout - (clock() - began)
        if remaining <= 0:
            raise RuntimeError('ibkr_news_pagination_total_timeout')
        page_began = clock()
        rows, coverage = fetch_page(cursor, limit, min(page_timeout, remaining))
        if clock() - began > total_timeout:
            raise RuntimeError('ibkr_news_pagination_total_timeout')
        if (not isinstance(rows, list) or coverage.get('terminal_received') is not True
                or type(coverage.get('has_more')) is not bool):
            raise RuntimeError('ibkr_news_pagination_terminal_unknown')
        if len(rows) > limit:
            raise RuntimeError('ibkr_news_pagination_page_exceeds_limit')
        times = [_timestamp(row) for row in rows]
        identities = [_identity(row) for row in rows]
        if any(t >= cursor for t in times):
            raise RuntimeError('ibkr_news_pagination_cursor_not_respected')
        if any(a < b for a, b in zip(times, times[1:])):
            raise RuntimeError('ibkr_news_pagination_not_descending')
        if not boundary <= set(identities):
            raise RuntimeError('ibkr_news_pagination_boundary_missing')
        duplicates = 0
        for row, key in zip(rows, identities):
            fingerprint = _fingerprint(row)
            if key in seen:
                if fingerprint != _fingerprint(seen[key]):
                    raise RuntimeError('ibkr_news_pagination_identity_conflict')
                duplicates += 1
            else:
                seen[key] = row
        duplicate_count += duplicates
        pages.append({'page':number,'request_id':coverage.get('request_id'),
                      'cursor_exclusive':cursor.isoformat(),'wire_start':cursor.strftime('%Y-%m-%d %H:%M:%S.0'),
                      'wire_end':'','returned_count':len(rows),'has_more':coverage['has_more'],
                      'terminal_received':True,'earliest':min(times).isoformat() if times else None,
                      'latest':max(times).isoformat() if times else None,
                      'duplicate_count':duplicates,'elapsed_seconds':round(clock()-page_began,6)})
        if coverage['has_more'] is False:
            values = sorted(seen.values(), key=lambda x:(_timestamp(x),_identity(x)), reverse=True)
            return values, {'status':'complete','terminal_received':True,'has_more':False,
                'requested_limit':limit,'returned_count':len(values),
                'method':'historicalNewsEnd_backward_cache_v1','scope':'available_provider_cache_before_rounded_end_cursor',
                'requested_window':{'start':start.isoformat(),'end':end.isoformat()},
                'lower_bound_applied':'local_filter_after_cache_exhaustion',
                'upper_bound_applied':'local_filter_exact_end_after_second_overlap',
                'initial_cursor_exclusive':pages[0]['cursor_exclusive'],
                'timestamp_basis':'provider_naive_interpreted_as_utc_existing_contract',
                'pagination_complete':True,'page_count':len(pages),'pages':pages,
                'duplicate_count':duplicate_count,'elapsed_seconds':round(clock()-began,6),
                'max_pages':max_pages,'total_timeout_seconds':total_timeout,
                'historical_response_timeout_seconds':page_timeout}
        if not times:
            raise RuntimeError('ibkr_news_pagination_empty_with_more')
        edge = min(times).replace(microsecond=0)
        next_cursor = edge + timedelta(seconds=1)
        if next_cursor >= cursor:
            raise RuntimeError('ibkr_news_pagination_no_progress_or_saturated_second')
        boundary = {key for key,t in zip(identities,times) if t.replace(microsecond=0)==edge}
        cursor = next_cursor
    raise RuntimeError('ibkr_news_pagination_page_limit')
