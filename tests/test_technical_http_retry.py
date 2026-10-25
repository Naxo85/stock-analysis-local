import io
import json
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError, URLError
from urllib.request import Request

import pytest


def rejection(code=502, *, raw_status=429, headers=None, body=None):
    if body is None:
        body = json.dumps({'error': 'raw_endpoint_http_error',
            'details': f'{raw_status} '+('Client' if raw_status < 500 else 'Server')+' Error: Too Many Requests for url: https://raw.example/',
            'body': 'Rate exceeded.'})
    return HTTPError('https://slim.example/', code, 'rejected', headers or {}, io.BytesIO(body.encode()))


def test_fetch_slim_recovers_exact_rejected_capture_before_archiving(tmp_path):
    from src.local_runner import run_one
    payload = {'symbol': 'LRCX', 'as_of': '2026-10-19T14:00:00+00:00', 'latest_price': 280}
    requested = []
    def fetch(request, **kwargs):
        requested.append(request)
        if len(requested) == 1:
            raise rejection()
        return io.BytesIO(json.dumps(payload).encode())
    with patch.object(run_one, 'urlopen', side_effect=fetch), patch('time.sleep'), \
         patch('random.uniform', return_value=0):
        result = run_one._fetch_slim('LRCX', avwap_anchors=['2026-06-30'],
            option_origins=[('put', 260.0)], support_origins=[], archive_root=tmp_path)
    assert result == payload
    assert len(requested) == 2 and requested[0] is requested[1]
    assert 'avwap_anchors=2026-06-30' in requested[0].full_url
    assert 'option_origins=put%3A260.0' in requested[0].full_url
    assert 'support_origins=%5B%5D' in requested[0].full_url
    assert 'evaluation_archive=1' in requested[0].full_url
    assert len(list((tmp_path/'LRCX').glob('*.json'))) == 1


class Clock:
    def __init__(self): self.now = 0; self.sleeps = []
    def __call__(self): return self.now
    def sleep(self, duration): self.sleeps.append(duration); self.now += duration


def transport(outcomes, *, clock=None, events=None):
    from src.local_runner.technical_http import read_slim_response
    clock = clock or Clock()
    calls = []
    def opener(request, timeout):
        calls.append((request, timeout))
        value = outcomes.pop(0)
        if callable(value): value = value(clock)
        if isinstance(value, Exception): raise value
        return io.BytesIO(value.encode())
    result = read_slim_response(Request('https://slim.example/?symbol=LRCX'),
        opener=opener, request_timeout=120, clock=clock, sleep=clock.sleep,
        jitter=lambda: 0, emit=(events if events is not None else []).append)
    return result, calls, clock


@pytest.mark.parametrize('code', [429, 503])
def test_direct_capacity_status_retries_and_honors_retry_after(code):
    result, calls, clock = transport([rejection(code, headers={'Retry-After': '7'}), '{}'])
    assert result == '{}' and len(calls) == 2 and clock.sleeps == [7]


def test_legacy_wrapped_raw_503_recovers():
    assert transport([rejection(raw_status=503), '{}'])[0] == '{}'


@pytest.mark.parametrize('code', [400, 401, 403, 404, 500, 502])
def test_other_http_errors_do_not_retry(code):
    with pytest.raises(RuntimeError, match=f'slim_endpoint_http_error: HTTP {code}'):
        transport([rejection(code, body='nontransient error')])


def test_wrapper_must_identify_raw_http_error_and_exact_status_prefix():
    for body in ({'error': 'internal_error', 'details': '429 Client Error: nope'},
                 {'error': 'raw_endpoint_http_error', 'details': '404 Client Error: url=429'},
                 {'error': 'raw_endpoint_http_error', 'details': 'unexpected 429'},
                 ['429'], {'error': 'raw_endpoint_http_error', 'details': {'code': 429}}):
        with pytest.raises(RuntimeError, match='HTTP 502'):
            transport([rejection(body=json.dumps(body))])


def test_exhaustion_preserves_real_error_and_has_three_calls(caplog):
    events = []
    with pytest.raises(RuntimeError, match='HTTP 502.*raw_endpoint_http_error'):
        transport([rejection(), rejection(), rejection()], events=events)
    assert [e['attempt'] for e in events] == [1, 2, 3]
    assert [e['retrying'] for e in events] == [True, True, False]
    assert events[-1]['reason'] == 'attempt_limit'


def test_elapsed_budget_prevents_new_request():
    clock = Clock(); events = []
    def slow_rejection(clock): clock.now = 241; return rejection()
    with pytest.raises(RuntimeError, match='HTTP 502'):
        transport([slow_rejection], clock=clock, events=events)
    assert clock.sleeps == [] and events[-1]['reason'] == 'deadline'


def test_remaining_budget_caps_each_following_request_timeout():
    def slow_rejection(clock): clock.now += 100; return rejection()
    result, calls, clock = transport([slow_rejection, slow_rejection, '{}'])
    assert result == '{}' and [timeout for _, timeout in calls] == [120, 120, 34]
    assert clock.sleeps == [2, 4]


def test_retry_after_beyond_budget_does_not_retry_early():
    events = []
    with pytest.raises(RuntimeError, match='HTTP 429'):
        transport([rejection(429, headers={'Retry-After': '300'})], events=events)
    assert events[-1]['reason'] == 'retry_after_exceeds_budget'


def test_connection_errors_are_not_hidden_or_turned_into_empty_data():
    with pytest.raises(RuntimeError, match='slim_endpoint_url_error'):
        transport([URLError('offline')])


def test_invalid_success_json_is_not_retried():
    from src.local_runner import run_one
    with patch.object(run_one, 'urlopen', return_value=io.BytesIO(b'invalid')) as fetch:
        with pytest.raises(RuntimeError, match='slim_endpoint_invalid_json'):
            run_one._fetch_slim('LRCX')
    assert fetch.call_count == 1


def test_exact_recorded_lrcx_failures_are_recognized_as_capacity_errors():
    root = Path(__file__).resolve().parents[1]
    original = json.loads((root/'docs/audit_lrcx_capacity_20261019/original_attempts.json').read_text(encoding='utf-8'))
    for attempt in original['attempts'].values():
        message = attempt['stages']['prepare']['error_message']
        body = message.split('slim_endpoint_http_error: HTTP 502: ', 1)[1]
        result, calls, clock = transport([rejection(body=body), '{}'])
        assert result == '{}' and len(calls) == 2 and clock.sleeps == [2]


def test_retry_after_date_and_invalid_header():
    from email.utils import formatdate
    from src.local_runner import technical_http
    with patch.object(technical_http.time, 'time', return_value=1000):
        assert technical_http._retry_after({'Retry-After': formatdate(1010, usegmt=True)}) == 10
        assert technical_http._retry_after({'Retry-After': formatdate(990, usegmt=True)}) == 0
        assert technical_http._retry_after({'Retry-After': 'unparseable'}) == 0


def test_scheduler_overrun_cannot_submit_a_request_after_deadline():
    from src.local_runner.technical_http import read_slim_response
    clock = Clock()
    def overrun(delay): clock.now = 241
    with patch('urllib.request.urlopen', side_effect=rejection()) as opener:
        with pytest.raises(RuntimeError, match='HTTP 502'):
            read_slim_response(Request('https://slim.example/'), opener=opener,
                request_timeout=120, clock=clock, sleep=overrun, jitter=lambda:0)
    assert opener.call_count == 1
