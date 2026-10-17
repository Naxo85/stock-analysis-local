from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch

from src.common.analysis_validator import validate_markdown
from src.local_runner import chatgpt_browser_generator


def test_request_start_accepts_stop_control_when_turn_counts_are_virtualized() -> None:
    driver = Mock()
    with patch.object(
        chatgpt_browser_generator,
        "_selenium_turn_snapshot",
        return_value=(3, "same-user", "same request"),
    ), patch.object(
        chatgpt_browser_generator,
        "_selenium_assistant_snapshot",
        return_value=(3, "same-assistant", "old report"),
    ), patch.object(
        chatgpt_browser_generator,
        "_selenium_agent_activity_snapshot",
        return_value=(2, "same-activity", "old activity"),
    ), patch.object(
        chatgpt_browser_generator,
        "_selenium_stop_button_visible",
        return_value=True,
    ):
        started = chatgpt_browser_generator._wait_for_selenium_request_started(
            driver,
            initial_user_snapshot=(3, "same-user", "same request"),
            initial_assistant_count=3,
            initial_assistant_snapshot=(3, "same-assistant", "old report"),
            initial_activity_snapshot=(2, "same-activity", "old activity"),
            timeout_seconds=1,
        )

    assert started


def test_new_assistant_accepts_agent_activity_before_final_turn() -> None:
    driver = Mock()
    with patch.object(
        chatgpt_browser_generator,
        "_selenium_assistant_snapshot",
        return_value=(0, "", ""),
    ), patch.object(
        chatgpt_browser_generator,
        "_selenium_agent_activity_snapshot",
        return_value=(1, "agent-run", "Pensando"),
    ), patch.object(
        chatgpt_browser_generator,
        "_selenium_stop_button_visible",
        return_value=False,
    ):
        visible = chatgpt_browser_generator._selenium_new_assistant_visible(
            driver,
            (0, "", ""),
            initial_activity_snapshot=(0, "", ""),
        )

    assert visible


def test_attachment_control_waits_for_page_hydration() -> None:
    file_input = Mock()
    add_context_button = Mock()
    add_context_button.is_displayed.return_value = True
    driver = Mock()
    state = {"clicked": False, "post_click_polls": 0}

    def find_elements(_by: object, selector: str) -> list[Mock]:
        if selector == chatgpt_browser_generator.ATTACHMENT_FILE_INPUT_SELECTOR:
            if not state["clicked"]:
                return []
            state["post_click_polls"] += 1
            return [file_input] if state["post_click_polls"] >= 3 else []
        if selector == 'button[data-composer-navigation-target="add-context"]':
            return [add_context_button]
        return []

    def click() -> None:
        state["clicked"] = True

    driver.find_elements.side_effect = find_elements
    add_context_button.click.side_effect = click

    with patch.object(chatgpt_browser_generator.time, "sleep"):
        chatgpt_browser_generator._open_attachment_menu_selenium(
            driver,
            timeout_seconds=1,
        )

    add_context_button.click.assert_called_once_with()
    assert state["post_click_polls"] == 3


def test_attachment_failure_restarts_browser_before_fallback() -> None:
    error = RuntimeError(
        "chatgpt_firefox_request_failed: stage=attach; type=RuntimeError; "
        "message=chatgpt_attachment_control_not_found"
    )

    assert chatgpt_browser_generator._is_browser_state_recovery_error(error)


def test_attachment_failure_restarts_same_worker_and_retries_locally() -> None:
    with TemporaryDirectory() as temporary:
        session = chatgpt_browser_generator.ChatGPTBrowserSession(
            Path(temporary),
            browser_engine="firefox",
        )
        session._driver = Mock()
        session._driver.current_url = "https://chatgpt.com/"
        hydration_error = RuntimeError(
            "chatgpt_firefox_request_failed: stage=attach; type=RuntimeError; "
            "message=chatgpt_attachment_control_not_found"
        )
        with patch.object(
            chatgpt_browser_generator,
            "_request_fresh_analysis_selenium",
            side_effect=(
                hydration_error,
                ("report", "https://chatgpt.com/c/ok"),
            ),
        ) as request, patch.object(
            session,
            "_restart_after_browser_state_failure",
        ) as restart, patch.object(
            chatgpt_browser_generator,
            "_write_browser_timeline_event",
        ):
            result = session.request_analysis(
                attachment_paths=(),
                symbol="LRCX",
                previous_errors=(),
                repair_previous_response=True,
                continuity_requirements="",
                timeout_seconds=1,
                response_inactivity_timeout_seconds=1,
                navigation_timeout_seconds=1,
                send_start_timeout_seconds=1,
                send_ready_stable_seconds=1,
                rate_limit_wait_seconds=1,
                diagnostic_dir=Path(temporary),
                attempt=1,
            )

        assert result == ("report", "https://chatgpt.com/c/ok")
        assert request.call_count == 2
        restart.assert_called_once_with()


def test_stale_composer_restarts_browser_before_fallback() -> None:
    error = RuntimeError(
        "chatgpt_firefox_request_failed: stage=locate_composer; "
        "type=StaleElementReferenceException; message=stale element reference"
    )

    assert chatgpt_browser_generator._is_browser_state_recovery_error(error)


def test_stale_dom_after_send_does_not_restart_and_duplicate_request() -> None:
    error = RuntimeError(
        "chatgpt_firefox_request_failed: stage=wait_response; "
        "type=StaleElementReferenceException; message=stale element reference"
    )

    assert not chatgpt_browser_generator._is_browser_state_recovery_error(error)


def test_missing_previous_level_allows_unrelated_historic_factor_reference() -> None:
    result = validate_markdown(
        """
Valoración: 4.9 / 10
Entrada: $60-$60.4
Motivo: Se conserva: la Entrada anterior exacta de $60-$60.4 sigue vigente.
Entrada ambiciosa: $58-$58.5
Motivo: Es el mejor soporte inferior actual dentro de dos ATR.
Factores de Entrada ambiciosa: el antiguo $55 es una referencia estructural remota, no una Entrada ambiciosa del plan anterior.
""",
        authoritative_context=(
            "entrada_anterior: 60-60.4\n"
            "entrada_ambiciosa_anterior: no extraída"
        ),
    )

    assert result.ok, result.errors


def test_strength_validation_tells_repair_request_about_factor_limit() -> None:
    result = validate_markdown(
        """
Valoración: 7.0 / 10
Entrada: $47-$47.4
Fortaleza de Entrada: 74/100 · sólido
Desglose de Entrada: estructura 19/25; volumen 12/20; opciones 20/25; confluencia 11/15; durabilidad 12/15
Factores de Entrada: pivote; defensas; HVN; put wall; distancia operativa
Entrada ambiciosa: Sin zona verificable
Fortaleza de Entrada ambiciosa: No aplicable
Desglose de Entrada ambiciosa: No aplicable
Factores de Entrada ambiciosa: No existe una zona defendible
""",
        require_support_strengths=True,
    )

    assert not result.ok
    assert any(
        "entry_strength" in error
        and "2-4 semicolon-separated concrete factors" in error
        for error in result.errors
    )


def test_missing_previous_level_rejects_explicit_invented_continuity() -> None:
    result = validate_markdown(
        """
Valoración: 4.9 / 10
Entrada: $60-$60.4
Motivo: Se conserva: la Entrada anterior exacta de $60-$60.4 sigue vigente.
Entrada ambiciosa: $58-$58.5
Motivo: Se reprioriza: la Entrada ambiciosa anterior exacta de $55-$56 sigue vigente, pero esta zona es mejor.
""",
        authoritative_context=(
            "entrada_anterior: 60-60.4\n"
            "entrada_ambiciosa_anterior: no extraída"
        ),
    )

    assert not result.ok
    assert any("invented_previous_level" in error for error in result.errors)


def test_prompt_forbids_continuity_claim_for_unextracted_level() -> None:
    request = chatgpt_browser_generator.build_analysis_request(
        "RKLB",
        continuity_requirements=(
            "entrada_anterior: 60-60.4\n"
            "entrada_ambiciosa_anterior: no extraída"
        ),
    )

    assert "no existe un valor anterior autoritativo" in request
    assert "sin atribuirlos al plan anterior" in request


def test_project_urls_match_when_chatgpt_drops_the_project_slug() -> None:
    stored = (
        "https://chatgpt.com/g/"
        "g-p-6aa00c49d1f08191b9f59c3d60bbd5f1-analisis/project"
    )
    current = (
        "https://chatgpt.com/g/"
        "g-p-6aa00c49d1f08191b9f59c3d60bbd5f1/c/chat-id"
    )

    assert chatgpt_browser_generator._same_chatgpt_project(current, stored)


def test_project_ready_accepts_project_url_without_aria_context_label() -> None:
    stored = (
        "https://chatgpt.com/g/"
        "g-p-6aa00c49d1f08191b9f59c3d60bbd5f1-analisis/project"
    )
    driver = Mock()
    driver.current_url = (
        "https://chatgpt.com/g/"
        "g-p-6aa00c49d1f08191b9f59c3d60bbd5f1/c/chat-id"
    )
    with patch.object(
        chatgpt_browser_generator,
        "_selenium_prompt_visible",
        return_value=True,
    ), patch.object(
        chatgpt_browser_generator,
        "_selenium_project_context_visible",
        return_value=False,
    ):
        assert chatgpt_browser_generator._selenium_project_ready(driver, stored)


def test_retry_button_accepts_current_retry_label() -> None:
    button = Mock()
    button.is_displayed.return_value = True
    button.is_enabled.return_value = True
    driver = Mock()
    driver.find_elements.return_value = [button]

    assert chatgpt_browser_generator._click_selenium_retry(driver)
    button.click.assert_called_once_with()


def test_navigation_state_failure_restarts_worker_and_uses_fresh_project_root() -> None:
    project_url = (
        "https://chatgpt.com/g/"
        "g-p-6aa00c49d1f08191b9f59c3d60bbd5f1-analisis/project"
    )
    browser_error = RuntimeError(
        "chatgpt_firefox_request_failed: stage=navigate; "
        "message=chatgpt_project_not_open: Analisis"
    )
    with TemporaryDirectory() as temporary:
        session = chatgpt_browser_generator.ChatGPTBrowserSession(
            Path(temporary),
            browser_engine="firefox",
        )
        session._driver = Mock()
        session._driver.current_url = project_url
        with patch.object(
            chatgpt_browser_generator,
            "_request_fresh_analysis_selenium",
            side_effect=(browser_error, ("report", project_url)),
        ) as request, patch.object(
            session,
            "_restart_after_browser_state_failure",
        ) as restart, patch.object(
            chatgpt_browser_generator,
            "_write_browser_timeline_event",
        ):
            result = session.request_analysis(
                attachment_paths=(),
                symbol="SNDK",
                previous_errors=(),
                repair_previous_response=False,
                continuity_requirements="",
                timeout_seconds=1,
                response_inactivity_timeout_seconds=1,
                navigation_timeout_seconds=1,
                send_start_timeout_seconds=1,
                send_ready_stable_seconds=1,
                rate_limit_wait_seconds=1,
                diagnostic_dir=Path(temporary),
                attempt=1,
                start_url=project_url,
            )

    assert result == ("report", project_url)
    assert request.call_count == 2
    restart.assert_called_once_with()
    assert request.call_args_list[1].kwargs["start_url"] == project_url
