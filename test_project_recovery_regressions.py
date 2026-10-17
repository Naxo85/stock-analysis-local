"""Offline reproductions of the 2026-09-27 five-worker-cascade and score feedback."""

from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
from threading import Event
from unittest.mock import Mock, patch

import pytest
from selenium.common.exceptions import StaleElementReferenceException

from src.common.analysis_validator import validate_markdown
from src.local_runner import chatgpt_browser_generator as browser


PROJECT = "https://chatgpt.com/g/g-p-6aa00c49d1f08191b9f59c3d60bbd5f1-analisis/project"
PROJECT_ERROR = (
    "chatgpt_firefox_request_failed: stage=navigate; type=RuntimeError; "
    "message=chatgpt_project_context_not_confirmed: Analisis"
)
TRANSPORT = "HTTPConnectionPool(host='localhost', port=50807): Read timed out. (read timeout=120)"


def test_project_click_accepts_current_project_id_row():
    button = Mock()
    button.get_attribute.return_value = "Nuevo chat en Analisis"
    row = Mock()
    row.get_attribute.side_effect = {
        "data-app-action-sidebar-project-id":
            "g-p-6aa00c49d1f08191b9f59c3d60bbd5f1",
        "data-app-action-sidebar-project-label": "Analisis",
    }.get
    row.find_elements.return_value = [button]
    driver = Mock()
    driver.find_elements.return_value = [row]

    assert browser._click_selenium_project(
        driver, "Analisis", project_url=PROJECT, timeout_seconds=1
    )
    driver.execute_script.assert_called_once_with("arguments[0].click();", button)


def test_project_direct_navigation_waits_for_async_context():
    driver = Mock()
    with patch.object(browser, "_wait_for_selenium_prompt"), patch.object(
        browser, "_selenium_project_ready", return_value=False
    ), patch.object(
        browser, "_click_selenium_project", return_value=False
    ), patch.object(
        browser, "_wait_for_selenium_project_ready", return_value=True
    ) as wait_for_project:
        browser._open_project_selenium(
            driver, project_url=PROJECT, timeout_seconds=20
        )
    assert driver.get.call_count == 2
    wait_for_project.assert_called_once_with(driver, PROJECT, 20)


def test_account_load_retry_accepts_current_spanish_button():
    button = Mock()
    button.is_displayed.return_value = True
    button.is_enabled.return_value = True
    driver = Mock()
    driver.find_elements.return_value = [button]

    assert browser._click_selenium_retry(driver)
    assert "Volver a cargar" in driver.find_elements.call_args.args[1]
    button.click.assert_called_once_with()


def test_project_poll_skips_stale_composer_element():
    stale = Mock()
    stale.is_displayed.side_effect = StaleElementReferenceException("rerender")
    current = Mock()
    current.is_displayed.return_value = True
    driver = Mock()
    driver.find_elements.return_value = [stale, current]

    assert browser._visible_selenium_element(driver, "#prompt-textarea") is current


def session_at(root, worker_id=1):
    session = browser.ChatGPTBrowserSession(root, browser_engine="firefox", worker_id=worker_id)
    session._driver = Mock()
    session._driver.current_url = browser.CHATGPT_URL
    return session


def request(session, root, symbol="AUR", **overrides):
    options = dict(
        attachment_paths=(), symbol=symbol, previous_errors=(),
        repair_previous_response=False, continuity_requirements="",
        timeout_seconds=1, response_inactivity_timeout_seconds=1,
        navigation_timeout_seconds=1, send_start_timeout_seconds=1,
        send_ready_stable_seconds=1, rate_limit_wait_seconds=1,
        diagnostic_dir=root, attempt=1, start_url=PROJECT,
    )
    options.update(overrides)
    return session.request_analysis(**options)


@pytest.mark.parametrize("error", [
    PROJECT_ERROR,
    f"chatgpt_firefox_request_failed: stage=navigate; type=ReadTimeoutError; message={TRANSPORT}",
    "chatgpt_firefox_request_failed: stage=attach; type=WebDriverException; message=connection refused",
])
def test_pre_send_failure_recovers_once_at_project_root_and_rechecks_model(tmp_path, error):
    session = session_at(tmp_path)
    session._model_policy_verified_at = "previous-verification"
    session._record_group_chat("AMD", "https://chatgpt.com/c/old-chat",
                               starts_new_group=True, group_start_url=PROJECT)
    with patch.object(browser, "_request_fresh_analysis_selenium", side_effect=[
        RuntimeError(error), ("report", "https://chatgpt.com/c/recovered")
    ]) as send, patch.object(session, "_restart_after_browser_state_failure") as restart:
        assert request(session, tmp_path, repair_previous_response=True)[0] == "report"
    restart.assert_called_once_with()
    assert send.call_count == 2
    first, second = send.call_args_list
    assert first.kwargs["start_url"].endswith("/old-chat")
    assert first.kwargs["ensure_sol_high"] is False
    assert second.kwargs["start_url"] == PROJECT
    assert second.kwargs["ensure_sol_high"] is True
    assert second.kwargs["repair_previous_response"] is False
    assert not session._quarantined


@pytest.mark.parametrize("stage", ["send", "wait_request_start", "wait_assistant", "wait_response", "extract"])
def test_post_send_transport_error_never_restarts_or_replays(tmp_path, stage):
    session = session_at(tmp_path)
    error = RuntimeError(f"chatgpt_firefox_request_failed: stage={stage}; message={TRANSPORT}")
    with patch.object(browser, "_request_fresh_analysis_selenium", side_effect=error) as send, patch.object(
        session, "_restart_after_browser_state_failure"
    ) as restart:
        with pytest.raises(RuntimeError, match="Read timed out"):
            request(session, tmp_path)
    send.assert_called_once()
    restart.assert_not_called()
    assert not session._quarantined


def test_failed_recovery_quarantines_worker_instead_of_poisoning_five_tickers(tmp_path):
    session = session_at(tmp_path)
    with patch.object(browser, "_request_fresh_analysis_selenium", side_effect=RuntimeError(PROJECT_ERROR)) as send, patch.object(
        session, "_restart_after_browser_state_failure"
    ) as restart:
        with pytest.raises(RuntimeError, match="project_context_not_confirmed"):
            request(session, tmp_path)
        for symbol in ("CAT", "CLS", "GEV", "HIMS"):
            with pytest.raises(RuntimeError, match="worker_quarantined"):
                request(session, tmp_path, symbol)
    assert send.call_count == 2
    restart.assert_called_once_with()
    assert session._quarantined
    assert not session._group_chat_url
    assert not session._group_symbols


def test_restart_failure_also_quarantines_worker(tmp_path):
    session = session_at(tmp_path)
    with patch.object(browser, "_request_fresh_analysis_selenium", side_effect=RuntimeError(PROJECT_ERROR)), patch.object(
        session, "_restart_after_browser_state_failure", side_effect=RuntimeError("launch failed")
    ):
        with pytest.raises(RuntimeError, match="launch failed"):
            request(session, tmp_path)
    assert session._quarantined
    assert session._quarantine_reason == "launch failed"


def test_unconfirmed_homepage_is_not_saved_on_other_request_errors(tmp_path):
    session = session_at(tmp_path)
    session._record_group_chat("AMD", browser.CHATGPT_URL, starts_new_group=True, group_start_url=PROJECT)
    with patch.object(browser, "_request_fresh_analysis_selenium", side_effect=RuntimeError("unexpected navigation error")):
        with pytest.raises(RuntimeError):
            request(session, tmp_path)
    assert session._group_request_target("CAT", PROJECT) == (PROJECT, True)
    assert not session._group_symbols


def test_invalidation_forces_project_reentry_even_after_browser_reopens(tmp_path):
    session = session_at(tmp_path)
    session._record_group_chat("AMD", browser.CHATGPT_URL, starts_new_group=True, group_start_url=PROJECT)
    session.invalidate()
    with patch.object(session, "open"), patch.object(session, "close"):
        with session.generation("CAT"):
            assert session._group_request_target("CAT", PROJECT) == (PROJECT, True)


def test_pool_removes_failed_worker_and_routes_subsequent_tickers_to_healthy_worker(tmp_path):
    failed, healthy = session_at(tmp_path, 1), session_at(tmp_path, 2)
    pool = browser.ChatGPTBrowserSessionPool(tmp_path, worker_count=2, sessions=(failed, healthy))
    with ExitStack() as mocks:
        for session in (failed, healthy):
            mocks.enter_context(patch.object(session, "open"))
            mocks.enter_context(patch.object(session, "close"))
        with pool.generation("AUR"):
            assert pool.current_worker_id() == 1
            failed._quarantine(RuntimeError(PROJECT_ERROR))
        for symbol in ("CAT", "CLS", "GEV", "HIMS"):
            with pool.generation(symbol):
                assert pool.current_worker_id() == 2
        failed.close.assert_called_once_with()
        assert pool.worker_count == 1
        assert pool.disabled_worker_ids == (1,)
        assert pool.progress_status()["disabled_worker_ids"] == [1]


def test_waiting_ticker_unblocks_if_last_worker_is_quarantined(tmp_path):
    session = session_at(tmp_path)
    pool = browser.ChatGPTBrowserSessionPool(tmp_path, worker_count=1, sessions=(session,))
    waiting = Event()

    def wait_for_worker():
        waiting.set()
        with pytest.raises(RuntimeError, match="no_healthy_browser_workers"):
            with pool.generation("CAT"):
                pytest.fail("No healthy worker should be leased")

    with patch.object(session, "open"), patch.object(session, "close"), ThreadPoolExecutor(max_workers=1) as executor:
        with pool.generation("AUR"):
            future = executor.submit(wait_for_worker)
            assert waiting.wait(timeout=1)
            session._quarantine(RuntimeError(PROJECT_ERROR))
        future.result(timeout=2)
    assert pool.worker_count == 0
    assert pool.progress_status()["waiting_tickers"] == []
    assert pool.progress_status()["all_workers_rate_limited"] is False


def test_missing_new_scores_feedback_never_requests_legacy_score():
    result = validate_markdown(
        "# ASML\nInforme no generado: falta la fuente autoritativa actual.",
        require_separate_scores=True,
    )
    assert not result.ok
    assert any("missing_or_invalid_tesis_score" in item for item in result.errors)
    assert any("missing_or_invalid_setup_score" in item for item in result.errors)
    assert not any("Valoración" in item for item in result.errors)


@pytest.mark.parametrize("scores,expected", [
    ("Tesis: 6.7 / 10\nMotivo de Tesis: negocio\nSetup: 6.7 / 10\nMotivo de Setup: entrada", None),
    ("Tesis: 6.7 / 10\nMotivo de Tesis: negocio\nSetup: 6.7 / 10\nMotivo de Setup: entrada\nValoración: 6.7 / 10", "mixed_score_contract"),
    ("Tesis: 11 / 10\nMotivo de Tesis: negocio\nSetup: 6.7 / 10\nMotivo de Setup: entrada", "missing_or_invalid_tesis_score"),
])
def test_new_score_contract_accepts_repair_but_still_rejects_mixing_and_bad_scores(scores, expected):
    result = validate_markdown(scores + "\nEntrada: $10 - $11\nEntrada ambiciosa: $8 - $9", require_separate_scores=True)
    if expected:
        assert any(expected in item for item in result.errors)
    else:
        assert result.ok, result.errors


def test_legacy_reports_still_validate_and_get_legacy_feedback():
    assert validate_markdown("Valoración: 6.7 / 10\nEntrada: $10 - $11\nEntrada ambiciosa: $8 - $9").ok
    result = validate_markdown("Entrada: $10 - $11\nEntrada ambiciosa: $8 - $9")
    assert "missing_or_invalid_score: expected 'Valoración: X / 10'" in result.errors
