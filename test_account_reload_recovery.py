from contextlib import ExitStack
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch

import pytest

from src.local_runner import chatgpt_browser_generator as browser
from src.local_runner import chatgpt_browser_network as network
from test_browser_access_observer import response


def run_auth(*, recover_on=None, challenge=False, api_block=True, timeout=60):
    driver = Mock()
    clock = [100.0]
    clicks = []
    driver._analysis_access_observer = network.BrowserAccessObserver()

    def click():
        clicks.append(clock[0])
        if len(clicks) == recover_on:
            driver._analysis_access_observer.record(response(200, challenge=False))
        return True

    def broken():
        return recover_on is None or len(clicks) < recover_on

    with ExitStack() as stack:
        stack.enter_context(patch.object(browser.time, 'monotonic', side_effect=lambda: clock[0]))
        stack.enter_context(patch.object(browser.time, 'sleep', side_effect=lambda n: clock.__setitem__(0, clock[0] + n)))
        for name, fn in {
            '_selenium_account_load_error_visible': broken,
            '_selenium_account_not_ready': broken,
            '_selenium_human_verification_visible': lambda: challenge,
            '_selenium_login_visible': lambda: False,
            '_selenium_prompt_visible': lambda: True,
            '_click_selenium_retry': click,
        }.items():
            stack.enter_context(patch.object(browser, name, side_effect=lambda *a, fn=fn: fn()))
        if api_block:
            driver._analysis_access_observer.record(response())
        error = None
        try:
            browser._ensure_selenium_authenticated(driver, timeout_seconds=timeout)
        except RuntimeError as exc:
            error = str(exc)
    return driver, clicks, error, clock[0]


@pytest.mark.parametrize('recover_on', [1, 2, 3])
def test_account_recovers_on_any_of_three_bounded_reloads(recover_on):
    driver, clicks, error, _ = run_auth(recover_on=recover_on)
    assert error is None
    assert len(clicks) == recover_on
    assert all(b - a >= 10 for a, b in zip(clicks, clicks[1:]))
    assert len(driver._analysis_account_reloads) == recover_on
    assert network.blocked_paths(driver) == []


def test_persistent_api_challenge_is_not_hidden_by_reloads():
    driver, clicks, error, end = run_auth()
    assert len(clicks) == 3
    assert end - clicks[-1] >= 10
    assert 'chatgpt_human_verification_required' in error
    assert network.blocked_paths(driver) == ['/backend-api/models']


def test_persistent_account_error_without_cloudflare_has_distinct_failure():
    _, clicks, error, _ = run_auth(api_block=False)
    assert len(clicks) == 3
    assert error == 'chatgpt_account_load_failed: reloads_exhausted=3'


def test_visible_human_challenge_never_gets_a_reload_click():
    _, clicks, error, _ = run_auth(challenge=True)
    assert clicks == []
    assert error == 'chatgpt_human_verification_required'


def test_reload_budget_does_not_extend_navigation_timeout():
    _, clicks, error, end = run_auth(timeout=7)
    assert len(clicks) == 1
    assert end == 107
    assert 'chatgpt_human_verification_required' in error


def test_network_history_preserves_failed_then_successful_requests_without_query():
    observer = network.BrowserAccessObserver()
    observer.record(response())
    observer.record(response(200, challenge=False))
    assert [item['status'] for item in observer.events()] == [403, 200]
    assert all(item['path'] == '/backend-api/models' for item in observer.events())
    assert observer.blocked_paths() == []


def test_exhausted_account_reloads_disable_only_the_affected_worker():
    with TemporaryDirectory() as temporary:
        root = Path(temporary)
        sessions = tuple(Mock(cwd=root.resolve(), engine='firefox', worker_id=i,
                              chat_group_size=5) for i in (1, 2))
        sessions[1].open.side_effect = RuntimeError('chatgpt_account_load_failed: reloads_exhausted=3')
        pool = browser.ChatGPTBrowserSessionPool(root, worker_count=2, sessions=sessions)
        pool.preflight()
        assert pool.worker_count == 1
        assert pool.disabled_worker_ids == (2,)
        assert pool.sessions == (sessions[0],)
        sessions[1].close.assert_called_once()


def test_account_failure_quarantines_worker_without_another_startup_retry():
    with TemporaryDirectory() as temporary:
        session = browser.ChatGPTBrowserSession(Path(temporary), browser_engine='firefox')
        error = RuntimeError('chatgpt_account_load_failed: reloads_exhausted=3')
        assert not browser._is_recoverable_browser_open_error(error)
        with patch.object(session, 'open', side_effect=error):
            with pytest.raises(RuntimeError, match='chatgpt_account_load_failed'):
                with session.generation(symbol='CCJ'):
                    pass
        assert session._quarantined
