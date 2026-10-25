"""Bounded retries of rejected technical GETs, before model admission only.

No report, frozen input, model request or incomplete capture is retried here.
The slim service historically wraps a raw HTTP 429/503 inside HTTP 502.
"""
from email.utils import parsedate_to_datetime
import json
import logging
import random
import time
from urllib.error import HTTPError, URLError

MAX_ATTEMPTS = 3
RETRY_BUDGET_SECONDS = 240


def _capacity_status(code, detail):
    if code in (429, 503):
        return code
    if code != 502:
        return None
    try:
        payload = json.loads(detail)
    except (ValueError, TypeError):
        return None
    if not isinstance(payload, dict) or payload.get('error') != 'raw_endpoint_http_error':
        return None
    message = payload.get('details')
    if isinstance(message, str):
        for prefix, status in (('429 Client Error:', 429), ('503 Server Error:', 503)):
            if message.startswith(prefix):
                return status
    return None


def _retry_after(headers):
    value = headers.get('Retry-After') if headers else None
    if value is None:
        return 0
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        try:
            stamp = parsedate_to_datetime(value)
            if stamp.tzinfo is not None:
                return max(0, stamp.timestamp() - time.time())
        except (TypeError, ValueError, OverflowError):
            pass
    return 0


def _emit(event):
    logging.getLogger(__name__).warning('technical_source_capacity %s', json.dumps(event, sort_keys=True))


def read_slim_response(request, *, opener, request_timeout, clock=None,
                       sleep=None, jitter=None, emit=None):
    clock = clock or time.monotonic
    sleep = sleep or time.sleep
    jitter = jitter or (lambda: random.uniform(0, 1))
    emit = emit or _emit
    deadline = clock() + RETRY_BUDGET_SECONDS
    last_error, last_detail = None, ''
    for attempt in range(1, MAX_ATTEMPTS + 1):
        remaining = deadline - clock()
        if remaining <= 0:
            if last_error is not None:
                raise RuntimeError(f'slim_endpoint_http_error: HTTP {last_error.code}: {last_detail[:1000]}') from last_error
            raise RuntimeError('slim_endpoint_retry_budget_exhausted')
        try:
            with opener(request, timeout=min(request_timeout, remaining)) as response:
                return response.read().decode('utf-8')
        except HTTPError as exc:
            try:
                detail = exc.read().decode('utf-8', errors='replace')
            finally:
                exc.close()
            last_error, last_detail = exc, detail
            upstream = _capacity_status(exc.code, detail)
            remaining = deadline - clock()
            delay = max(2 ** attempt + jitter(), _retry_after(exc.headers)) if upstream else 0
            reason = ('not_capacity' if upstream is None else 'attempt_limit' if attempt == MAX_ATTEMPTS
                      else 'deadline' if remaining <= 0
                      else 'retry_after_exceeds_budget' if delay >= remaining else 'capacity')
            retrying = reason == 'capacity'
            if upstream:
                emit({'attempt': attempt, 'http_status': exc.code, 'upstream_status': upstream,
                      'retrying': retrying, 'reason': reason,
                      'delay_seconds': round(delay, 3) if retrying else 0,
                      'remaining_seconds': round(max(0, remaining), 3)})
            if not retrying:
                raise RuntimeError(f'slim_endpoint_http_error: HTTP {exc.code}: {detail[:1000]}') from exc
            sleep(delay)
            # Sleeping or scheduling may overrun the remaining wall budget.
            if clock() >= deadline:
                raise RuntimeError(f'slim_endpoint_http_error: HTTP {exc.code}: {detail[:1000]}') from exc
        except URLError as exc:
            raise RuntimeError(f'slim_endpoint_url_error: {exc}') from exc
