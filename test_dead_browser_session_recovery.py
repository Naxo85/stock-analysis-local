"""Offline reproductions of the 2026-09-29 invalid-session preflight failure."""

import json
from unittest.mock import MagicMock, Mock, PropertyMock, patch

import pytest
from selenium.common.exceptions import InvalidSessionIdException

from src.local_runner import chatgpt_browser_generator as browser


DEAD_SESSION = "Tried to run command without establishing a connection"


def dead_session():
    return InvalidSessionIdException(DEAD_SESSION)


@pytest.mark.parametrize("error", [
    InvalidSessionIdException(""),
    dead_session(),
    RuntimeError(f"chatgpt_firefox_navigation_failed: {DEAD_SESSION}"),
    RuntimeError("chatgpt_firefox_launch_failed: invalid session id"),
])
def test_dead_session_requires_restart_not_response_poll(error):
    assert browser._is_recoverable_browser_open_error(error)
    assert not browser._is_transient_selenium_poll_error(error)


def test_raw_invalid_session_during_composer_poll_restarts_only_that_profile(tmp_path):
    session = browser.ChatGPTBrowserSession(tmp_path, browser_engine="firefox", worker_id=2)
    drivers = [Mock(), Mock()]
    with patch.object(browser, "_launch_firefox_with_retries", side_effect=drivers) as launch, patch.object(
        browser, "_selenium_login_visible", return_value=False
    ), patch.object(browser, "_selenium_prompt_visible", side_effect=[dead_session(), True]), patch.object(
        browser, "_write_selenium_trace"
    ) as trace, patch.object(browser.time, "sleep"):
        try:
            assert session.open() is session
            assert session._driver is drivers[1]
            assert launch.call_count == 2
            assert all(call.args == (session.profile_dir,) for call in launch.call_args_list)
            assert all(call.kwargs == {"headed": False} for call in launch.call_args_list)
            trace.assert_called_once()
            assert isinstance(trace.call_args.kwargs["error"], InvalidSessionIdException)
            drivers[0].quit.assert_called_once_with()
        finally:
            session.close()


def test_persistent_dead_session_is_bounded_and_releases_profile_lock(tmp_path):
    session = browser.ChatGPTBrowserSession(tmp_path, browser_engine="firefox")
    drivers = [Mock() for _ in range(1 + browser.DEFAULT_TRANSIENT_OPEN_RETRIES)]
    error = dead_session()
    with patch.object(browser, "_launch_firefox_with_retries", side_effect=drivers) as launch, patch.object(
        browser, "_ensure_selenium_authenticated", side_effect=error
    ), patch.object(browser, "_write_selenium_trace") as trace, patch.object(browser.time, "sleep"):
        with pytest.raises(InvalidSessionIdException) as caught:
            session.open()
    assert caught.value is error
    assert launch.call_count == 1 + browser.DEFAULT_TRANSIENT_OPEN_RETRIES
    assert trace.call_count == launch.call_count
    assert [call.kwargs["attempt"] for call in trace.call_args_list] == [1, 2, 3]
    assert not session.is_open
    assert session._lock_context is None
    for driver in drivers:
        driver.quit.assert_called_once_with()


def test_quit_of_dead_driver_cannot_cancel_recovery_or_release_lock_early(tmp_path):
    session = browser.ChatGPTBrowserSession(tmp_path, browser_engine="firefox")
    broken, recovered = Mock(), Mock()
    broken.quit.side_effect = dead_session()
    lock = MagicMock()
    lock.__enter__.return_value = False
    with patch.object(browser, "_exclusive_browser_lock", return_value=lock), patch.object(
        browser, "_stop_orphaned_firefox_profile_processes"
    ), patch.object(browser, "_launch_firefox_with_retries", side_effect=[broken, recovered]), patch.object(
        browser, "_ensure_selenium_authenticated", side_effect=[dead_session(), None]
    ), patch.object(browser, "_write_selenium_trace"), patch.object(browser.time, "sleep"):
        try:
            session.open()
            assert session._driver is recovered
            lock.__exit__.assert_not_called()
        finally:
            session.close()
    lock.__exit__.assert_called_once_with(None, None, None)


def test_dead_session_on_replacement_launch_is_also_captured_and_retried(tmp_path):
    session = browser.ChatGPTBrowserSession(tmp_path, browser_engine="firefox")
    original, recovered = Mock(), Mock()
    with patch.object(browser, "_launch_firefox_with_retries", side_effect=[original, dead_session(), recovered]) as launch, patch.object(
        browser, "_ensure_selenium_authenticated", side_effect=[dead_session(), None]
    ), patch.object(browser, "_write_selenium_trace") as trace, patch.object(browser.time, "sleep"):
        try:
            session.open()
            assert session._driver is recovered
            assert launch.call_count == 3
            assert trace.call_count == 2
            assert trace.call_args_list[1].kwargs["stage"] == "launch"
        finally:
            session.close()


def test_session_dying_while_retrying_login_gets_browser_recovery(tmp_path):
    session = browser.ChatGPTBrowserSession(tmp_path, browser_engine="firefox")
    with patch.object(browser, "_launch_firefox_with_retries", side_effect=lambda *a, **k: Mock()) as launch, patch.object(
        browser, "_ensure_selenium_authenticated", side_effect=[RuntimeError("chatgpt_login_required"), dead_session(), None]
    ), patch.object(browser, "_write_selenium_trace"), patch.object(browser.time, "sleep"):
        try:
            session.open()
            assert launch.call_count == 2
        finally:
            session.close()


def test_dead_browser_still_writes_exact_failure_json_when_page_capture_fails(tmp_path):
    session = browser.ChatGPTBrowserSession(tmp_path, browser_engine="firefox", worker_id=3)
    driver = Mock()
    driver.save_screenshot.side_effect = dead_session()
    driver.execute_script.side_effect = dead_session()
    type(driver).page_source = PropertyMock(side_effect=dead_session())
    type(driver).current_url = PropertyMock(side_effect=dead_session())
    with patch.object(browser, "_launch_firefox_with_retries", return_value=driver), patch.object(
        browser, "_ensure_selenium_authenticated", side_effect=dead_session()
    ), patch.object(browser.time, "sleep"):
        with pytest.raises(InvalidSessionIdException):
            session.open()
    paths = sorted((tmp_path / "logs/browser_startup/worker-3").glob("*.json"))
    assert len(paths) == 3
    for path in paths:
        diagnostic = json.loads(path.read_text(encoding="utf-8"))
        assert diagnostic["error_type"] == "InvalidSessionIdException"
        assert DEAD_SESSION in diagnostic["error_message"]
        assert diagnostic["stage"] == "authenticate"
        assert len(diagnostic["capture_errors"]) == 3
        assert diagnostic["screenshot_path"] is None


def mocked_sessions(root, count=3):
    return tuple(Mock(cwd=root.resolve(), engine="firefox", worker_id=i, chat_group_size=5)
                 for i in range(1, count + 1))


def test_pool_excludes_raw_invalid_session_and_rebuilds_healthy_queue(tmp_path):
    sessions = mocked_sessions(tmp_path)
    sessions[1].open.side_effect = dead_session()
    pool = browser.ChatGPTBrowserSessionPool(tmp_path, worker_count=3, browser_engine="firefox", sessions=sessions)
    pool.preflight()
    assert pool.worker_count == 2
    assert pool.disabled_worker_ids == (2,)
    assert pool.sessions == (sessions[0], sessions[2])
    assert [pool._available.get_nowait(), pool._available.get_nowait()] == list(pool.sessions)
    sessions[1].close.assert_called_once_with()
    sessions[0].close.assert_not_called()
    sessions[2].close.assert_not_called()


def test_no_healthy_workers_fails_visibly_with_no_dead_sessions_available(tmp_path):
    sessions = mocked_sessions(tmp_path)
    for session in sessions:
        session.open.side_effect = dead_session()
    pool = browser.ChatGPTBrowserSessionPool(tmp_path, worker_count=3, browser_engine="firefox", sessions=sessions)
    with pytest.raises(RuntimeError, match="chatgpt_no_authenticated_browser_workers") as caught:
        pool.preflight()
    assert isinstance(caught.value.__cause__, InvalidSessionIdException)
    assert pool.worker_count == 0
    assert pool.sessions == ()
    assert pool.disabled_worker_ids == (1, 2, 3)
    assert pool._available.empty()
    with pytest.raises(RuntimeError, match="no_healthy_browser_workers"):
        pool._lease_healthy_session()


def test_unknown_preflight_error_is_not_masked_as_a_bad_profile(tmp_path):
    sessions = mocked_sessions(tmp_path, count=2)
    error = ValueError("unexpected programming error")
    sessions[1].open.side_effect = error
    pool = browser.ChatGPTBrowserSessionPool(tmp_path, worker_count=2, browser_engine="firefox", sessions=sessions)
    with pytest.raises(ValueError) as caught:
        pool.preflight()
    assert caught.value is error


@pytest.mark.parametrize("stage", ["send", "wait_request_start", "wait_assistant", "wait_response", "extract"])
def test_invalid_session_after_send_never_authorizes_replay(stage):
    error = RuntimeError(f"chatgpt_firefox_request_failed: stage={stage}; type=InvalidSessionIdException; message={DEAD_SESSION}")
    assert not browser._is_browser_state_recovery_error(error)


@pytest.mark.parametrize("stage", ["navigate", "ensure_sol_high", "attach", "wait_send_ready"])
def test_invalid_session_before_send_can_recover(stage):
    error = RuntimeError(f"chatgpt_firefox_request_failed: stage={stage}; type=InvalidSessionIdException; message={DEAD_SESSION}")
    assert browser._is_browser_state_recovery_error(error)
