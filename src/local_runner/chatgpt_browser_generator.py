"""Generate validated analysis markdown through an authenticated ChatGPT browser."""

from __future__ import annotations

import argparse
import concurrent.futures
import ctypes
import getpass
import hashlib
import json
import os
import queue
import re
import shutil
import subprocess
import threading
import time
import unicodedata
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Iterator

from .chatgpt_browser_network import (
    access_events as _browser_access_events,
    blocked_paths as _blocked_browser_api_paths,
    install_access_observer,
    raise_if_access_blocked as _raise_if_browser_access_blocked,
)

from src.common.analysis_validator import validate_markdown


CHATGPT_URL = "https://chatgpt.com/"
CREDENTIAL_SERVICE = "stock-analysis-local/chatgpt"
CREDENTIAL_ACCOUNT_KEY = "account-email"
DEFAULT_TIMEOUT_SECONDS = 1800
DEFAULT_RESPONSE_INACTIVITY_TIMEOUT_SECONDS = 300
DEFAULT_NAVIGATION_TIMEOUT_SECONDS = 120
DEFAULT_SEND_START_TIMEOUT_SECONDS = 60
DEFAULT_SEND_READY_STABLE_SECONDS = 10
DEFAULT_RATE_LIMIT_WAIT_SECONDS = 300
DEFAULT_MODEL_POLICY_RETRY_WAIT_SECONDS = 10
DEFAULT_TRANSIENT_OPEN_RETRIES = 2
DEFAULT_TRANSIENT_OPEN_BACKOFF_SECONDS = 5
DEFAULT_CHAT_GROUP_SIZE = 5
DEFAULT_LOCK_TIMEOUT_SECONDS = 21600
DEFAULT_LOCK_INITIALIZATION_GRACE_SECONDS = 5
DEFAULT_MAX_ATTEMPTS = 2
DEFAULT_PROFILE_PATH = Path(".local") / "chatgpt-browser-profile"
DEFAULT_FIREFOX_PROFILE_PATH = Path(".local") / "chatgpt-firefox-profile"
DEFAULT_LOCK_PATH = Path(".local") / "chatgpt-browser.lock"
DEFAULT_PROJECT_NAME = "Analisis"
DEFAULT_PROJECT_URL_PATH = Path(".local") / "chatgpt-project-url.txt"
DEFAULT_CLEANUP_QUEUE_PATH = Path(".local") / "chatgpt-chat-cleanup-queue.json"
DEFAULT_CLEANUP_DELAY_SECONDS = 600
DEFAULT_CLEANUP_MAX_CHATS = 2
DEFAULT_CLEANUP_MIN_AGE_SECONDS = 21600
DEFAULT_ATTACHMENT_LIMIT_WAIT_SECONDS = 180
DEFAULT_ATTACHMENT_LIMIT_MARGIN_SECONDS = 15
DEFAULT_ATTACHMENT_LIMIT_RETRIES = 3
DEFAULT_ATTACHMENT_CONFIRMATION_RETRIES = 1
DEFAULT_ATTACHMENT_CONFIRMATION_RETRY_TIMEOUT_SECONDS = 30
DEFAULT_ATTACHMENT_CONFIRMATION_RETRY_WAIT_SECONDS = 2
DEFAULT_SEND_RECOVERY_TIMEOUT_SECONDS = 30
DEFAULT_ASSISTANT_VISIBILITY_RECOVERY_TIMEOUT_SECONDS = 60
CHATGPT_WEB_MODEL = "gpt-5.6-sol"
CHATGPT_WEB_REASONING_EFFORT = "high"
CHATGPT_WEB_REASONING_LABEL = "Alta"
CHATGPT_WEB_MODEL_LABEL = "GPT-5.6 Sol"
CHATGPT_WEB_HIGH_SLIDER_VALUE = "2"
CHATGPT_WEB_HIGH_LABELS = frozenset(("alta", "high"))
CHATGPT_WEB_REASONING_CONTROL_LABELS = frozenset(("esfuerzo de razonamiento", "reasoning effort"))
_CLEANUP_QUEUE_LOCK = threading.Lock()
CHATGPT_WEB_REASONING_LABELS = frozenset(
    (
        "instant",
        "instantanea",
        "medium",
        "medio",
        "media",
        "high",
        "alta",
        "extra high",
        "extra alta",
        "pro",
    )
)
WEB_STAGE_STALL_THRESHOLDS_SECONDS = {
    "open_browser": 120,
    "navigate": 120,
    "ensure_sol_high": 30,
    "model_policy_retry_wait": 20,
    "model_policy_restart": 120,
    "rate_limit_before_attach": 330,
    "locate_composer": 30,
    "attach": 60,
    "confirm_attachments": 120,
    "attachment_confirmation_retry": 45,
    "attachment_limit_wait": 600,
    "rate_limit_before_send": 330,
    "compose": 45,
    "wait_send_ready": 90,
    "recover_send_control": 45,
    "send": 20,
    "wait_request_start": 90,
    "wait_assistant": 180,
    "recover_assistant_visibility": 90,
    "wait_response": 480,
    "extract": 30,
}
LOGIN_REQUIRED_STABLE_SECONDS = 12
PROMPT_SELECTOR = (
    '#prompt-textarea, '
    'div[contenteditable="true"][role="textbox"][data-composer-markdown], '
    'div[contenteditable="true"][role="textbox"][aria-label*="ChatGPT"], '
    'textarea[aria-label*="ChatGPT"]:not(.wcDTda_fallbackTextarea), '
    'textarea[placeholder]:not(.wcDTda_fallbackTextarea)'
)
ATTACHMENT_FILE_INPUT_SELECTOR = (
    'input[type="file"][aria-label*="archivos" i], '
    'input[type="file"][aria-label*="files" i], '
    'input[type="file"]:not([accept]), '
    '#upload-files'
)
USER_SELECTOR = (
    '[data-message-author-role="user"], '
    '[data-content-search-unit-key$=":user"]'
)
ASSISTANT_SELECTOR = (
    '[data-message-author-role="assistant"], '
    '[data-content-search-unit-key$=":assistant"]'
)
AGENT_ACTIVITY_SELECTOR = '[data-chatgpt-agent-turn-start]'
STOP_BUTTON_SELECTOR = (
    '[data-testid="stop-button"], '
    'button[aria-label*="Stop"], '
    'button[aria-label*="Detener"]'
)
MARKDOWN_CODE_BLOCK_SELECTOR = (
    'pre code, [data-markdown-copy="code-block"] code'
)
SEND_BUTTON_SELECTOR = (
    'button[data-testid="send-button"], '
    'button[data-testid="composer-submit-button"], '
    'button#composer-submit-button, '
    'button[aria-label="Enviar prompt"], '
    'button[aria-label="Send prompt"], '
    'button[type="submit"][aria-label="Enviar"], '
    'button[type="submit"][aria-label="Send"]'
)


def _is_model_policy_confirmation_error(error: BaseException) -> bool:
    return "chatgpt_sol_high_not_confirmed" in str(error)


def _is_login_required_error(error: BaseException) -> bool:
    return "chatgpt_login_required" in str(error)


def _is_human_verification_error(error: BaseException) -> bool:
    return "chatgpt_human_verification_required" in str(error)


def _is_account_load_error(error: BaseException) -> bool:
    return "chatgpt_account_load_failed" in str(error)


def _selenium_human_verification_visible(driver: Any) -> bool:
    try:
        page_source = str(driver.page_source).casefold()
    except Exception:
        return False
    # ChatGPT also loads Cloudflare's invisible JavaScript detection on ordinary
    # application/error pages. A script URL alone is not a human challenge.
    if "_cf_chl_opt" in page_source and (
        "/cdn-cgi/challenge-platform/" in page_source
        or "challenges.cloudflare.com/turnstile" in page_source
    ):
        return True
    try:
        from selenium.webdriver.common.by import By

        return any(
            frame.is_displayed()
            for frame in driver.find_elements(
                By.CSS_SELECTOR, "iframe[src*='challenges.cloudflare.com']"
            )
        )
    except Exception:
        return False


def _is_browser_state_recovery_error(error: BaseException) -> bool:
    message = str(error).casefold()
    pre_send_stages = (
        "navigate", "ensure_sol_high", "rate_limit_before_attach",
        "locate_composer", "attach", "confirm_attachments",
        "rate_limit_before_send", "compose", "wait_send_ready",
        "recover_send_control",
    )
    stage = re.search(r"\bstage=([^;]+);", message)
    # Never restart/replay a transport or DOM failure once send has begun.
    if stage and stage.group(1) not in pre_send_stages:
        return False
    if any(
        marker in message
        for marker in (
            "chatgpt_project_not_open",
            "chatgpt_project_context_not_confirmed",
            "chatgpt_prompt_not_available",
            "chatgpt_firefox_navigation_failed: prompt_not_available",
            "chatgpt_attachment_control_not_found",
        )
    ):
        return True

    return bool(
        stage
        and (
            _is_transient_selenium_poll_error(error)
            or _is_transient_firefox_launch_error(error)
        )
    )


def _is_transient_selenium_poll_error(error: BaseException) -> bool:
    """Return whether a response poll can be repeated without resending."""

    error_type = type(error).__name__
    if error_type in {"StaleElementReferenceException", "ReadTimeoutError"}:
        return True
    message = str(error).lower()
    return (
        "stale element reference" in message
        or (
            "httpconnectionpool(host='localhost'" in message
            and "read timed out" in message
        )
    )


def _is_transient_firefox_launch_error(error: BaseException) -> bool:
    """Recognize Firefox/Marionette startup failures worth retrying."""

    # Selenium's native exceptions do not inherit RuntimeError. A dead session
    # needs a fresh browser, never another response poll on the same driver.
    if type(error).__name__ == "InvalidSessionIdException":
        return True
    if _is_transient_selenium_poll_error(error):
        return True
    message = str(error).casefold()
    return any(
        marker in message
        for marker in (
            "unexpectedly closed with status 0",
            "process unexpectedly closed",
            "browsing context has been discarded",
            "no such window",
            "failed to decode response from marionette",
            "invalidsessionidexception",
            "invalid session id",
            "tried to run command without establishing a connection",
            "connection refused",
            "connection aborted",
            "connectionreseterror",
            "10054",
        )
    )


def _is_recoverable_browser_open_error(error: BaseException) -> bool:
    return (
        _is_transient_selenium_poll_error(error)
        or _is_transient_firefox_launch_error(error)
        or _is_browser_state_recovery_error(error)
    )


def _is_discarded_browser_context_error(error: BaseException) -> bool:
    message = str(error).casefold()
    return (
        "browsing context has been discarded" in message
        or "no such window" in message
    )


@dataclass(frozen=True)
class ChatGPTBrowserGenerationResult:
    input_path: Path
    output_path: Path
    attempts: int
    chat_urls: tuple[str, ...]
    metadata_path: Path


class _AttachmentUploadTemporarilyLimited(RuntimeError):
    def __init__(self, wait_seconds: int) -> None:
        self.wait_seconds = max(1, int(wait_seconds))
        super().__init__(
            f"chatgpt_attachment_upload_temporarily_limited: "
            f"retry_after_seconds={self.wait_seconds}"
        )


class _AttachmentUploadCooldown:
    """Coordinate ChatGPT's account-wide rolling upload limit across workers."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._resume_monotonic = 0.0
        self._resume_at: str | None = None
        self._count = 0

    def trigger(self, wait_seconds: int) -> str:
        pause_seconds = max(1, int(wait_seconds))
        now_monotonic = time.monotonic()
        proposed_monotonic = now_monotonic + pause_seconds
        proposed_at = _utc_now() + timedelta(seconds=pause_seconds)
        with self._lock:
            if self._resume_monotonic <= now_monotonic:
                self._count += 1
            if proposed_monotonic > self._resume_monotonic:
                self._resume_monotonic = proposed_monotonic
                self._resume_at = proposed_at.isoformat()
            return str(self._resume_at)

    def wait(self) -> bool:
        waited = False
        while True:
            with self._lock:
                remaining = self._resume_monotonic - time.monotonic()
                if remaining <= 0:
                    self._resume_monotonic = 0.0
                    self._resume_at = None
                    return waited
            waited = True
            time.sleep(min(remaining, 1.0))

    def status(self) -> dict[str, Any]:
        with self._lock:
            waiting = self._resume_monotonic > time.monotonic()
            return {
                "count": self._count,
                "waiting": waiting,
                "resume_at": self._resume_at if waiting else None,
            }


class ChatGPTBrowserSession:
    """Reusable authenticated browser session for a sequence of analyses."""

    def __init__(
        self,
        cwd: Path,
        *,
        headed: bool = False,
        browser_engine: str | None = None,
        chat_group_size: int | None = None,
        worker_id: int = 1,
        attachment_cooldown: _AttachmentUploadCooldown | None = None,
    ) -> None:
        if worker_id < 1:
            raise ValueError("worker_id_must_be_positive")
        self.cwd = cwd.resolve()
        self.headed = headed
        self.engine = _browser_engine(browser_engine)
        self.worker_id = int(worker_id)
        self._attachment_cooldown = (
            attachment_cooldown or _AttachmentUploadCooldown()
        )
        self.profile_dir = _profile_dir(
            self.cwd,
            engine=self.engine,
            worker_id=self.worker_id,
        )
        self.lock_path = _lock_path(self.cwd, worker_id=self.worker_id)
        self.navigation_timeout_seconds = _configured_timeout_seconds(
            "CHATGPT_NAVIGATION_TIMEOUT_SECONDS",
            DEFAULT_NAVIGATION_TIMEOUT_SECONDS,
        )
        self.lock_timeout_seconds = _configured_timeout_seconds(
            "CHATGPT_BROWSER_LOCK_TIMEOUT_SECONDS",
            DEFAULT_LOCK_TIMEOUT_SECONDS,
        )
        self.model_policy_retry_wait_seconds = _configured_timeout_seconds(
            "CHATGPT_MODEL_POLICY_RETRY_WAIT_SECONDS",
            DEFAULT_MODEL_POLICY_RETRY_WAIT_SECONDS,
        )
        self.chat_group_size = (
            int(chat_group_size)
            if chat_group_size is not None
            else _configured_timeout_seconds(
                "CHATGPT_CHAT_GROUP_SIZE",
                DEFAULT_CHAT_GROUP_SIZE,
            )
        )
        if self.chat_group_size < 1:
            raise ValueError("chat_group_size_must_be_positive")
        self._generation_lock = threading.RLock()
        self._status_lock = threading.Lock()
        self._lock_context: Any | None = None
        self._driver: Any | None = None
        self._playwright: Any | None = None
        self._context: Any | None = None
        self._page: Any | None = None
        self._group_chat_url = ""
        self._group_start_url = ""
        self._group_symbols: list[str] = []
        self._rate_limit_count = 0
        self._rate_limit_resume_at: str | None = None
        self._reset_required = False
        self._quarantined = False
        self._quarantine_reason = ""
        self._waiting_symbols: dict[str, str] = {}
        self._generation_timings: dict[str, dict[str, float]] = {}
        self._active_symbol = ""
        self._active_attempt: int | None = None
        self._active_stage = ""
        self._active_stage_started_at: str | None = None
        self._model_policy_verified_at: str | None = None

    @property
    def is_open(self) -> bool:
        return self._driver is not None or self._page is not None

    def open(self) -> ChatGPTBrowserSession:
        if self.is_open:
            return self

        lock_context = _exclusive_browser_lock(
            self.lock_path,
            timeout_seconds=self.lock_timeout_seconds,
        )
        recovered_stale_lock = bool(lock_context.__enter__())
        self._lock_context = lock_context
        try:
            if self.engine == "firefox":
                if recovered_stale_lock:
                    _stop_orphaned_firefox_profile_processes(self.profile_dir)
                self._open_firefox()
            else:
                try:
                    from playwright.sync_api import sync_playwright
                except ImportError as exc:
                    raise RuntimeError(
                        "chatgpt_browser_dependency_missing: "
                        "install requirements-chatgpt.txt"
                    ) from exc
                self._playwright = sync_playwright().start()
                self._context = self._playwright.chromium.launch_persistent_context(
                    user_data_dir=str(self.profile_dir),
                    executable_path=_browser_executable(),
                    headless=not self.headed,
                    viewport={"width": 1440, "height": 1000},
                    accept_downloads=False,
                    args=("--disable-background-timer-throttling", "--disable-extensions", "--disable-sync"),
                )
                self._page = (
                    self._context.pages[0]
                    if self._context.pages
                    else self._context.new_page()
                )
                _ensure_authenticated(
                    self._page,
                    timeout_seconds=self.navigation_timeout_seconds,
                )
        except BaseException:
            self.close()
            raise
        return self

    def _open_firefox(self) -> None:
        """Retry launch/authentication before any analysis request is sent."""

        login_retry_used = False
        login_restart_used = False
        self._model_policy_verified_at = None
        for attempt in range(1, DEFAULT_TRANSIENT_OPEN_RETRIES + 2):
            stage = "launch"
            try:
                self._driver = _launch_firefox_with_retries(
                    self.profile_dir, headed=self.headed,
                )
                stage = "authenticate"
                _ensure_selenium_authenticated(
                    self._driver, timeout_seconds=self.navigation_timeout_seconds,
                )
                return
            except Exception as error:
                self._capture_open_failure(error, attempt=attempt, stage=stage)
                if _is_login_required_error(error) and not login_retry_used:
                    login_retry_used = True
                    time.sleep(self.model_policy_retry_wait_seconds)
                    try:
                        _ensure_selenium_authenticated(
                            self._driver, timeout_seconds=self.navigation_timeout_seconds,
                        )
                        return
                    except Exception as login_error:
                        error = login_error
                        self._capture_open_failure(error, attempt=attempt, stage=stage)

                if _is_login_required_error(error):
                    retry = not login_restart_used
                    login_restart_used = True
                    backoff = 0
                else:
                    retry = _is_recoverable_browser_open_error(error)
                    backoff = DEFAULT_TRANSIENT_OPEN_BACKOFF_SECONDS * attempt
                if not retry or attempt > DEFAULT_TRANSIENT_OPEN_RETRIES:
                    raise error

                # Keep the profile lock during recovery. A crashed Marionette
                # session may raise even on quit; that must not cancel restart.
                driver, self._driver = self._driver, None
                if driver is not None:
                    try:
                        driver.quit()
                    except Exception:
                        pass
                if backoff:
                    time.sleep(backoff)

    def _capture_open_failure(
        self, error: Exception, *, attempt: int, stage: str = "authenticate",
    ) -> None:
        try:
            _write_selenium_trace(
                self._driver,
                diagnostic_dir=self.cwd / "logs" / "browser_startup" / f"worker-{self.worker_id}",
                symbol=f"worker-{self.worker_id}", attempt=attempt,
                status="failed", stage=stage, stage_timings={},
                error=error, capture_page=self._driver is not None,
            )
        except Exception as capture_error:
            print(f"WARNING: browser startup diagnostic failed: {capture_error}", flush=True)

    @contextmanager
    def generation(self, symbol: str = "") -> Iterator[ChatGPTBrowserSession]:
        """Keep one report generation atomic while sharing the browser."""

        queued_at = _utc_now().isoformat()
        queued_perf = time.perf_counter()
        if symbol:
            with self._status_lock:
                self._waiting_symbols[symbol] = queued_at
        try:
            with self._generation_lock:
                queue_wait_seconds = max(0.0, time.perf_counter() - queued_perf)
                with self._status_lock:
                    self._waiting_symbols.pop(symbol, None)
                    self._generation_timings[symbol] = {
                        "queue_wait_seconds": queue_wait_seconds,
                        "execution_seconds": 0.0,
                    }
                    self._active_symbol = symbol
                    self._active_attempt = None
                    self._active_stage = "open_browser"
                    self._active_stage_started_at = _utc_now().isoformat()
                try:
                    if self._quarantined:
                        raise RuntimeError(f"chatgpt_browser_worker_quarantined: {self._quarantine_reason}")
                    if self._reset_required:
                        self.close()
                        self._clear_group_chat()
                        self._reset_required = False
                    self.open()
                    yield self
                except BaseException as exc:
                    if _is_human_verification_error(exc) or _is_account_load_error(exc):
                        self._quarantine(exc)
                    self._reset_required = True
                    raise
                finally:
                    with self._status_lock:
                        if self._active_symbol == symbol:
                            self._active_symbol = ""
                            self._active_attempt = None
                            self._active_stage = ""
                            self._active_stage_started_at = None
        finally:
            if symbol:
                with self._status_lock:
                    self._waiting_symbols.pop(symbol, None)

    def invalidate(self) -> None:
        """Request a safe browser restart before the next Web generation."""

        self._reset_required = True
        self._clear_group_chat()

    def _clear_group_chat(self) -> None:
        self._group_chat_url = ""
        self._group_start_url = ""
        self._group_symbols = []

    def _quarantine(self, error: BaseException) -> None:
        self._quarantined = True
        self._quarantine_reason = str(error)
        self.invalidate()

    def _restart_after_browser_state_failure(self) -> None:
        """Restart only this worker before retrying the same ticker."""

        self.close()
        self._clear_group_chat()
        self._reset_required = False
        self.open()

    def request_analysis(
        self,
        *,
        attachment_paths: tuple[Path, ...],
        symbol: str,
        previous_errors: tuple[str, ...],
        repair_previous_response: bool,
        continuity_requirements: str,
        timeout_seconds: int,
        response_inactivity_timeout_seconds: int,
        navigation_timeout_seconds: int,
        send_start_timeout_seconds: int,
        send_ready_stable_seconds: int,
        rate_limit_wait_seconds: int,
        diagnostic_dir: Path,
        attempt: int,
        start_url: str = CHATGPT_URL,
    ) -> tuple[str, str]:
        if self._quarantined:
            raise RuntimeError(f"chatgpt_browser_worker_quarantined: {self._quarantine_reason}")
        request_started_perf = time.perf_counter()
        effective_url, starts_new_group = self._group_request_target(
            symbol,
            start_url,
        )
        request_attachment_paths = (
            _stage_unique_request_attachments(
                attachment_paths,
                diagnostic_dir=diagnostic_dir,
                symbol=symbol,
                attempt=attempt,
            )
            if not repair_previous_response
            else attachment_paths
        )
        def stage_changed(
            stage: str,
            stage_timings: dict[str, float],
            status: str,
            error: Exception | None,
        ) -> None:
            self._set_active_stage(symbol, attempt, stage)
            _write_browser_timeline_event(
                diagnostic_dir=diagnostic_dir,
                symbol=symbol,
                attempt=attempt,
                stage=stage,
                status=status,
                stage_timings=stage_timings,
                error=error,
            )

        ensure_model_policy = self._model_policy_verified_at is None

        def execute_once() -> tuple[str, str]:
            if self.engine == "firefox" and self._driver is not None:
                return _request_fresh_analysis_selenium(
                    self._driver,
                    attachment_paths=request_attachment_paths,
                    symbol=symbol,
                    previous_errors=previous_errors,
                    repair_previous_response=repair_previous_response,
                    continuity_requirements=continuity_requirements,
                    timeout_seconds=timeout_seconds,
                    response_inactivity_timeout_seconds=response_inactivity_timeout_seconds,
                    navigation_timeout_seconds=navigation_timeout_seconds,
                    send_start_timeout_seconds=send_start_timeout_seconds,
                    send_ready_stable_seconds=send_ready_stable_seconds,
                    rate_limit_wait_seconds=rate_limit_wait_seconds,
                    rate_limit_started=self._rate_limit_started,
                    rate_limit_finished=self._rate_limit_finished,
                    attachment_cooldown=self._attachment_cooldown,
                    diagnostic_dir=diagnostic_dir,
                    attempt=attempt,
                    start_url=effective_url,
                    expected_project_url=(
                        start_url if _valid_project_url(start_url) else None
                    ),
                    ensure_sol_high=ensure_model_policy,
                    stage_changed=stage_changed,
                )
            if self._page is not None:
                stage_changed("request", {}, "running", None)
                result = _request_fresh_analysis(
                    self._page,
                    attachment_paths=request_attachment_paths,
                    symbol=symbol,
                    previous_errors=previous_errors,
                    repair_previous_response=repair_previous_response,
                    continuity_requirements=continuity_requirements,
                    timeout_seconds=timeout_seconds,
                    navigation_timeout_seconds=navigation_timeout_seconds,
                    send_start_timeout_seconds=send_start_timeout_seconds,
                    send_ready_stable_seconds=send_ready_stable_seconds,
                    start_url=effective_url,
                    expected_project_url=(
                        start_url if _valid_project_url(start_url) else None
                    ),
                    ensure_sol_high=ensure_model_policy,
                )
                stage_changed("complete", {}, "ok", None)
                return result
            raise RuntimeError("chatgpt_browser_session_not_open")

        try:
            try:
                result = execute_once()
            except RuntimeError as first_error:
                if _is_browser_state_recovery_error(first_error):
                    stage_changed(
                        "browser_state_restart",
                        {},
                        "running",
                        first_error,
                    )
                    try:
                        self._restart_after_browser_state_failure()
                    except Exception as restart_error:
                        self._quarantine(restart_error)
                        raise
                    effective_url = start_url
                    starts_new_group = True
                    ensure_model_policy = True
                    # A fresh browser has no previous response to repair.
                    repair_previous_response = False
                    try:
                        result = execute_once()
                    except RuntimeError as retry_error:
                        if _is_browser_state_recovery_error(retry_error):
                            self._quarantine(retry_error)
                        raise
                else:
                    recoverable = _is_login_required_error(first_error) or (
                        ensure_model_policy
                        and _is_model_policy_confirmation_error(first_error)
                    )
                    if not recoverable:
                        raise
                    stage_changed("model_policy_retry_wait", {}, "waiting", first_error)
                    time.sleep(self.model_policy_retry_wait_seconds)
                    try:
                        result = execute_once()
                    except RuntimeError as retry_error:
                        recoverable_retry = _is_login_required_error(retry_error) or (
                            ensure_model_policy
                            and _is_model_policy_confirmation_error(retry_error)
                        )
                        if not recoverable_retry:
                            raise
                        stage_changed("model_policy_restart", {}, "running", retry_error)
                        self._restart_after_browser_state_failure()
                        effective_url = start_url
                        starts_new_group = True
                        ensure_model_policy = True
                        repair_previous_response = False
                        result = execute_once()
        except Exception as exc:
            self._record_web_execution(symbol, request_started_perf)
            if self.engine != "firefox":
                stage_changed("failed", {}, "failed", exc)
            if (
                self._quarantined
                or _is_browser_state_recovery_error(exc)
                or _normal_chat_id(self.current_url()) is None
            ):
                self._clear_group_chat()
            else:
                self._record_group_chat(
                    symbol,
                    self.current_url(),
                    starts_new_group=starts_new_group,
                    group_start_url=start_url,
                )
            raise
        self._record_group_chat(
            symbol,
            result[1],
            starts_new_group=starts_new_group,
            group_start_url=start_url,
        )
        self._model_policy_verified_at = _utc_now().isoformat()
        self._record_web_execution(symbol, request_started_perf)
        return result

    def generation_timing(self, symbol: str) -> dict[str, float]:
        with self._status_lock:
            return {
                key: round(float(value), 3)
                for key, value in self._generation_timings.get(symbol, {}).items()
            }

    def _record_web_execution(self, symbol: str, started_perf: float) -> None:
        elapsed = max(0.0, time.perf_counter() - started_perf)
        with self._status_lock:
            timing = self._generation_timings.setdefault(
                symbol,
                {"queue_wait_seconds": 0.0, "execution_seconds": 0.0},
            )
            timing["execution_seconds"] = (
                float(timing.get("execution_seconds") or 0.0) + elapsed
            )

    def progress_status(self) -> dict[str, Any]:
        attachment_limit = self._attachment_cooldown.status()
        with self._status_lock:
            stage_elapsed_seconds: float | None = None
            if self._active_stage_started_at:
                try:
                    stage_started = datetime.fromisoformat(
                        self._active_stage_started_at.replace("Z", "+00:00")
                    )
                    stage_elapsed_seconds = max(
                        0.0, (_utc_now() - stage_started).total_seconds()
                    )
                except ValueError:
                    stage_elapsed_seconds = None
            threshold = WEB_STAGE_STALL_THRESHOLDS_SECONDS.get(self._active_stage)
            return {
                "worker_id": self.worker_id,
                "quarantined": self._quarantined,
                "quarantine_reason": self._quarantine_reason or None,
                "chat_group_size": self.chat_group_size,
                "chat_group_tickers": len(self._group_symbols),
                "request_rate_limit_count": self._rate_limit_count,
                "attachment_rate_limit_count": attachment_limit["count"],
                "attachment_rate_limit_waiting": attachment_limit["waiting"],
                "rate_limit_count": (
                    self._rate_limit_count + int(attachment_limit["count"])
                ),
                "rate_limit_waiting": (
                    self._rate_limit_resume_at is not None
                    or bool(attachment_limit["waiting"])
                ),
                "rate_limit_resume_at": max(
                    filter(
                        None,
                        (
                            self._rate_limit_resume_at,
                            attachment_limit["resume_at"],
                        ),
                    ),
                    default=None,
                ),
                "active_ticker": self._active_symbol,
                "active_attempt": self._active_attempt,
                "active_stage": self._active_stage,
                "active_stage_started_at": self._active_stage_started_at,
                "active_stage_elapsed_seconds": (
                    round(stage_elapsed_seconds, 1)
                    if stage_elapsed_seconds is not None
                    else None
                ),
                "active_stage_stall_threshold_seconds": threshold,
                "active_stage_stalled": bool(
                    threshold is not None
                    and stage_elapsed_seconds is not None
                    and stage_elapsed_seconds >= threshold
                ),
                "waiting_tickers": list(self._waiting_symbols),
                "waiting_since": dict(self._waiting_symbols),
                "web_model": CHATGPT_WEB_MODEL,
                "web_reasoning_effort": CHATGPT_WEB_REASONING_EFFORT,
                "model_policy_verified_at": self._model_policy_verified_at,
            }

    def current_worker_id(self) -> int:
        return self.worker_id

    def current_progress_status(self) -> dict[str, Any]:
        return self.progress_status()

    def _set_active_stage(self, symbol: str, attempt: int, stage: str) -> None:
        with self._status_lock:
            if self._active_symbol != symbol or self._active_stage != stage:
                self._active_stage_started_at = _utc_now().isoformat()
            self._active_symbol = symbol
            self._active_attempt = attempt
            self._active_stage = stage

    def _group_request_target(self, symbol: str, start_url: str) -> tuple[str, bool]:
        same_group_root = (
            self._group_start_url.rstrip("/") == start_url.rstrip("/")
        )
        project_state_without_chat_url = (
            _valid_project_url(start_url)
            and self._group_chat_url.rstrip("/") == CHATGPT_URL.rstrip("/")
        )
        if not same_group_root or not (
            _normal_chat_id(self._group_chat_url)
            or project_state_without_chat_url
        ):
            return start_url, True
        if symbol in self._group_symbols or len(self._group_symbols) < self.chat_group_size:
            return self._group_chat_url, False
        return start_url, True

    def _record_group_chat(
        self,
        symbol: str,
        chat_url: str,
        *,
        starts_new_group: bool,
        group_start_url: str | None = None,
    ) -> None:
        # Root URLs are reusable only after a successful request confirmed the
        # project. The exception path must never record an unconfirmed root.
        project_state_without_chat_url = bool(
            group_start_url
            and _valid_project_url(group_start_url)
            and chat_url.rstrip("/") == CHATGPT_URL.rstrip("/")
        )
        if _normal_chat_id(chat_url) is None and not project_state_without_chat_url:
            return
        if starts_new_group or chat_url != self._group_chat_url:
            self._group_chat_url = chat_url
            self._group_start_url = group_start_url or CHATGPT_URL
            self._group_symbols = []
        if symbol not in self._group_symbols:
            self._group_symbols.append(symbol)

    def _rate_limit_started(self, resume_at: datetime) -> None:
        with self._status_lock:
            self._rate_limit_count += 1
            self._rate_limit_resume_at = resume_at.astimezone(timezone.utc).isoformat()

    def _rate_limit_finished(self) -> None:
        with self._status_lock:
            self._rate_limit_resume_at = None

    def current_url(self) -> str:
        try:
            if self._driver is not None:
                return str(self._driver.current_url or "")
            if self._page is not None:
                return str(self._page.url or "")
        except Exception:
            return ""
        return ""

    def close(self) -> None:
        try:
            if self._driver is not None:
                try:
                    self._driver.quit()
                except Exception:
                    pass
            if self._context is not None:
                try:
                    self._context.close()
                except Exception:
                    pass
            if self._playwright is not None:
                try:
                    self._playwright.stop()
                except Exception:
                    pass
        finally:
            self._driver = None
            self._page = None
            self._context = None
            self._playwright = None
            self._model_policy_verified_at = None
            lock_context = self._lock_context
            self._lock_context = None
            if lock_context is not None:
                lock_context.__exit__(None, None, None)

    def __enter__(self) -> ChatGPTBrowserSession:
        return self.open()

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        self.close()


class ChatGPTBrowserSessionPool:
    """Lease independent browser profiles to concurrent Web generations."""

    def __init__(
        self,
        cwd: Path,
        *,
        worker_count: int,
        headed: bool = False,
        browser_engine: str | None = None,
        chat_group_size: int | None = None,
        sessions: tuple[ChatGPTBrowserSession, ...] | None = None,
    ) -> None:
        if worker_count < 1:
            raise ValueError("worker_count_must_be_positive")
        self.cwd = cwd.resolve()
        self.engine = _browser_engine(browser_engine)
        self._attachment_cooldown = _AttachmentUploadCooldown()
        if sessions is None:
            sessions = tuple(
                ChatGPTBrowserSession(
                    self.cwd,
                    headed=headed,
                    browser_engine=self.engine,
                    chat_group_size=chat_group_size,
                    worker_id=index,
                    attachment_cooldown=self._attachment_cooldown,
                )
                for index in range(1, worker_count + 1)
            )
        if len(sessions) != worker_count:
            raise ValueError("browser_session_pool_size_mismatch")
        if any(session.cwd != self.cwd for session in sessions):
            raise ValueError("browser_session_pool_cwd_mismatch")
        if any(session.engine != self.engine for session in sessions):
            raise ValueError("browser_session_pool_engine_mismatch")
        self.sessions = sessions
        self.worker_count = len(sessions)
        self.chat_group_size = sessions[0].chat_group_size
        self._available: queue.Queue[ChatGPTBrowserSession] = queue.Queue()
        for session in sessions:
            self._available.put(session)
        self._local = threading.local()
        self._status_lock = threading.Lock()
        self._waiting_symbols: dict[str, str] = {}
        self._generation_timings: dict[str, dict[str, float | int]] = {}
        self.disabled_worker_ids: tuple[int, ...] = ()

    def preflight(self) -> None:
        """Exclude failed startup profiles without discarding healthy workers."""

        healthy: list[ChatGPTBrowserSession] = []
        disabled: list[int] = []
        last_startup_error: Exception | None = None
        with concurrent.futures.ThreadPoolExecutor(
            max_workers=len(self.sessions),
            thread_name_prefix="chatgpt-browser-preflight",
        ) as executor:
            checks = {
                executor.submit(session.open): session for session in self.sessions
            }
            for future, session in ((future, checks[future]) for future in checks):
                try:
                    future.result()
                except Exception as exc:
                    if not (
                        _is_login_required_error(exc)
                        or _is_human_verification_error(exc)
                        or _is_account_load_error(exc)
                        or _is_transient_selenium_poll_error(exc)
                        or _is_transient_firefox_launch_error(exc)
                        or _is_browser_state_recovery_error(exc)
                    ):
                        raise
                    session.close()
                    disabled.append(session.worker_id)
                    last_startup_error = exc
                else:
                    healthy.append(session)

        self.sessions = tuple(sorted(healthy, key=lambda item: item.worker_id))
        self.worker_count = len(self.sessions)
        self.disabled_worker_ids = tuple(sorted(disabled))
        self._available = queue.Queue()
        for session in self.sessions:
            self._available.put(session)
        if not healthy:
            raise RuntimeError("chatgpt_no_authenticated_browser_workers") from last_startup_error

    @contextmanager
    def generation(self, symbol: str = "") -> Iterator[ChatGPTBrowserSessionPool]:
        queued_perf = time.perf_counter()
        if symbol:
            with self._status_lock:
                self._waiting_symbols[symbol] = _utc_now().isoformat()
        try:
            session = self._lease_healthy_session()
        except BaseException:
            with self._status_lock:
                self._waiting_symbols.pop(symbol, None)
            raise
        pool_wait_seconds = max(0.0, time.perf_counter() - queued_perf)
        self._local.session = session
        self._local.pool_wait_seconds = pool_wait_seconds
        if symbol:
            with self._status_lock:
                self._waiting_symbols.pop(symbol, None)
        try:
            with session.generation(symbol=symbol):
                yield self
        finally:
            timing = session.generation_timing(symbol)
            timing["queue_wait_seconds"] = round(
                float(timing.get("queue_wait_seconds") or 0.0)
                + pool_wait_seconds,
                3,
            )
            timing["worker_id"] = session.worker_id
            with self._status_lock:
                self._generation_timings[symbol] = timing
                self._waiting_symbols.pop(symbol, None)
            self._local.session = None
            self._local.pool_wait_seconds = 0.0
            if getattr(session, "_quarantined", False) is True:
                with self._status_lock:
                    self.sessions = tuple(item for item in self.sessions if item is not session)
                    self.worker_count = len(self.sessions)
                    self.disabled_worker_ids = tuple(sorted({*self.disabled_worker_ids, session.worker_id}))
                session.close()
            else:
                self._available.put(session)

    def _lease_healthy_session(self) -> ChatGPTBrowserSession:
        # A blocking Queue.get() would strand waiting tickers if the last
        # in-flight worker is quarantined instead of returning to the queue.
        while True:
            with self._status_lock:
                if self.worker_count == 0:
                    raise RuntimeError("chatgpt_no_healthy_browser_workers")
            try:
                return self._available.get(timeout=0.25)
            except queue.Empty:
                continue

    def request_analysis(self, **kwargs: Any) -> tuple[str, str]:
        return self._active_session().request_analysis(**kwargs)

    def invalidate(self) -> None:
        self._active_session().invalidate()

    def current_url(self) -> str:
        return self._active_session().current_url()

    def current_worker_id(self) -> int:
        return self._active_session().worker_id

    def current_progress_status(self) -> dict[str, Any]:
        return self._active_session().progress_status()

    def generation_timing(self, symbol: str) -> dict[str, float | int]:
        active_session = getattr(self._local, "session", None)
        if active_session is not None:
            timing: dict[str, float | int] = active_session.generation_timing(symbol)
            timing["queue_wait_seconds"] = round(
                float(timing.get("queue_wait_seconds") or 0.0)
                + float(getattr(self._local, "pool_wait_seconds", 0.0)),
                3,
            )
            timing["worker_id"] = active_session.worker_id
            return timing
        with self._status_lock:
            return dict(self._generation_timings.get(symbol, {}))

    def progress_status(self) -> dict[str, Any]:
        workers = [session.progress_status() for session in self.sessions]
        active = [worker for worker in workers if worker.get("active_ticker")]
        rate_limited_worker_count = sum(
            1 for worker in workers if worker.get("rate_limit_waiting")
        )
        waiting = list(self._waiting_symbols)
        for worker in workers:
            waiting.extend(str(item) for item in worker.get("waiting_tickers", []))
        rate_limit_resume_values = [
            str(worker["rate_limit_resume_at"])
            for worker in workers
            if worker.get("rate_limit_resume_at")
        ]
        first_active = active[0] if active else {}
        attachment_limit = self._attachment_cooldown.status()
        request_rate_limit_count = sum(
            int(worker.get("request_rate_limit_count") or 0)
            for worker in workers
        )
        return {
            "worker_count": self.worker_count,
            "disabled_worker_ids": list(self.disabled_worker_ids),
            "workers": workers,
            "chat_group_size": self.chat_group_size * self.worker_count,
            "chat_group_tickers": sum(
                int(worker.get("chat_group_tickers") or 0) for worker in workers
            ),
            "request_rate_limit_count": request_rate_limit_count,
            "attachment_rate_limit_count": attachment_limit["count"],
            "attachment_rate_limit_waiting": attachment_limit["waiting"],
            "rate_limit_count": (
                request_rate_limit_count + int(attachment_limit["count"])
            ),
            "rate_limit_waiting": any(
                bool(worker.get("rate_limit_waiting")) for worker in workers
            ),
            "rate_limited_worker_count": rate_limited_worker_count,
            "all_workers_rate_limited": (
                self.worker_count > 0 and rate_limited_worker_count == self.worker_count
            ),
            "rate_limit_resume_at": (
                max(rate_limit_resume_values) if rate_limit_resume_values else None
            ),
            "active_ticker": ", ".join(
                str(worker.get("active_ticker")) for worker in active
            ),
            "active_attempt": first_active.get("active_attempt"),
            "active_stage": first_active.get("active_stage", ""),
            "active_stage_started_at": first_active.get("active_stage_started_at"),
            "active_stage_elapsed_seconds": first_active.get(
                "active_stage_elapsed_seconds"
            ),
            "active_stage_stall_threshold_seconds": first_active.get(
                "active_stage_stall_threshold_seconds"
            ),
            "active_stage_stalled": any(
                bool(worker.get("active_stage_stalled")) for worker in workers
            ),
            "waiting_tickers": list(dict.fromkeys(waiting)),
            "web_model": CHATGPT_WEB_MODEL,
            "web_reasoning_effort": CHATGPT_WEB_REASONING_EFFORT,
            "model_policy_verified_at": first_active.get(
                "model_policy_verified_at"
            ),
        }

    def close(self) -> None:
        for session in self.sessions:
            session.close()

    def _active_session(self) -> ChatGPTBrowserSession:
        session = getattr(self._local, "session", None)
        if session is None:
            raise RuntimeError("chatgpt_browser_pool_session_not_leased")
        return session


def generate_markdown_with_chatgpt_browser(
    input_path: Path,
    output_path: Path,
    *,
    cwd: Path,
    symbol: str,
    previous_analysis_path: Path | None = None,
    headed: bool = False,
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    browser_engine: str | None = None,
    session: ChatGPTBrowserSession | ChatGPTBrowserSessionPool | None = None,
) -> ChatGPTBrowserGenerationResult:
    """Ask ChatGPT to generate a fresh analysis and promote only valid markdown."""

    if not input_path.exists():
        raise RuntimeError(f"missing_chatgpt_input: {input_path}")
    if previous_analysis_path is not None and not previous_analysis_path.exists():
        raise RuntimeError(
            f"missing_chatgpt_previous_analysis: {previous_analysis_path}"
        )
    if max_attempts < 1:
        raise RuntimeError("chatgpt_browser_max_attempts_must_be_positive")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    engine = (
        session.engine
        if session is not None
        else _browser_engine(browser_engine)
    )
    if session is not None and session.cwd != cwd.resolve():
        raise RuntimeError("chatgpt_browser_session_cwd_mismatch")
    if browser_engine is not None and _browser_engine(browser_engine) != engine:
        raise RuntimeError("chatgpt_browser_session_engine_mismatch")
    authoritative_context = input_path.read_text(encoding="utf-8")
    input_sha256 = hashlib.sha256(input_path.read_bytes()).hexdigest()
    continuity_requirements = extract_level_continuity_requirements(
        authoritative_context
    )
    # The consolidated input already embeds the complete previous report. Keeping
    # one upload per ticker avoids exhausting ChatGPT's rolling file-upload quota.
    attachment_paths = (input_path,)
    attempts_log: list[dict[str, Any]] = []
    chat_urls: list[str] = []
    previous_errors: tuple[str, ...] = ()
    if output_path.exists():
        existing_validation = validate_markdown(
            output_path.read_text(encoding="utf-8"),
            require_support_strengths=True,
            require_resistance=True,
            require_separate_scores=True,
        )
        if not existing_validation.ok:
            previous_errors = existing_validation.errors
    started_at = _utc_now()
    response_timeout_seconds = _configured_timeout_seconds(
        "CHATGPT_RESPONSE_TIMEOUT_SECONDS",
        timeout_seconds,
    )
    response_inactivity_timeout_seconds = _configured_timeout_seconds(
        "CHATGPT_RESPONSE_INACTIVITY_TIMEOUT_SECONDS",
        DEFAULT_RESPONSE_INACTIVITY_TIMEOUT_SECONDS,
    )
    navigation_timeout_seconds = _configured_timeout_seconds(
        "CHATGPT_NAVIGATION_TIMEOUT_SECONDS",
        DEFAULT_NAVIGATION_TIMEOUT_SECONDS,
    )
    send_start_timeout_seconds = _configured_timeout_seconds(
        "CHATGPT_SEND_START_TIMEOUT_SECONDS",
        DEFAULT_SEND_START_TIMEOUT_SECONDS,
    )
    send_ready_stable_seconds = _configured_timeout_seconds(
        "CHATGPT_SEND_READY_STABLE_SECONDS",
        DEFAULT_SEND_READY_STABLE_SECONDS,
    )
    rate_limit_wait_seconds = _configured_timeout_seconds(
        "CHATGPT_RATE_LIMIT_WAIT_SECONDS",
        DEFAULT_RATE_LIMIT_WAIT_SECONDS,
    )
    lock_timeout_seconds = _configured_timeout_seconds(
        "CHATGPT_BROWSER_LOCK_TIMEOUT_SECONDS",
        DEFAULT_LOCK_TIMEOUT_SECONDS,
    )
    project_url = _stored_project_url(cwd)
    cleanup_warnings: list[str] = []

    browser_session = session or ChatGPTBrowserSession(
        cwd,
        headed=headed,
        browser_engine=engine,
    )
    chat_mode_prefix = "project" if project_url else "normal"
    chat_mode = f"{chat_mode_prefix}-grouped-{browser_session.chat_group_size}"
    owns_session = session is None
    repair_previous_response = False
    try:
        with browser_session.generation(symbol=symbol):
            request_analysis = lambda errors, attempt, repair: browser_session.request_analysis(
                attachment_paths=attachment_paths,
                symbol=symbol,
                previous_errors=errors,
                repair_previous_response=repair,
                continuity_requirements=continuity_requirements,
                timeout_seconds=response_timeout_seconds,
                response_inactivity_timeout_seconds=response_inactivity_timeout_seconds,
                navigation_timeout_seconds=navigation_timeout_seconds,
                send_start_timeout_seconds=send_start_timeout_seconds,
                send_ready_stable_seconds=send_ready_stable_seconds,
                rate_limit_wait_seconds=rate_limit_wait_seconds,
                diagnostic_dir=output_path.parent / "browser_diagnostics",
                attempt=attempt,
                start_url=project_url or CHATGPT_URL,
            )
            for attempt in range(1, max_attempts + 1):
                candidate_path = output_path.with_name(
                    f"chatgpt_attempt_{attempt}.md"
                )
                raw_path = output_path.with_name(
                    f"chatgpt_attempt_{attempt}.raw.txt"
                )
                attempt_started = _utc_now()
                errors: tuple[str, ...]
                chat_url = ""
                sanitized_markers = 0
                response_received = False

                try:
                    response_text, chat_url = request_analysis(
                        previous_errors,
                        attempt,
                        attempt > 1 and repair_previous_response,
                    )
                    response_received = True
                    raw_path.write_text(response_text, encoding="utf-8")
                    chat_urls.append(chat_url)
                    candidate = extract_single_markdown_block(response_text)
                    candidate, sanitized_markers = sanitize_internal_citation_markers(
                        candidate
                    )
                    candidate_path.write_text(candidate, encoding="utf-8")
                    validation = validate_markdown(
                        candidate,
                        authoritative_context=authoritative_context,
                        require_support_strengths=True,
                        require_resistance=True,
                        require_separate_scores=True,
                    )
                    errors = validation.errors
                    if validation.ok:
                        _atomic_write_text(output_path, candidate)
                        attempts_log.append(
                            _attempt_record(
                                attempt,
                                attempt_started,
                                chat_url,
                                candidate_path,
                                (),
                                sanitized_markers=sanitized_markers,
                            )
                        )
                        cleanup_warning = _queue_chat_for_cleanup(
                            cwd,
                            chat_url,
                            symbol=symbol,
                            attempt=attempt,
                        )
                        if cleanup_warning:
                            cleanup_warnings.append(cleanup_warning)
                        metadata_path = output_path.with_name(
                            "generation_metadata.json"
                        )
                        _write_metadata(
                            metadata_path,
                            {
                                "provider_requested": "chatgpt-browser",
                                "provider_used": "chatgpt-browser",
                                "browser_engine": engine,
                                "web_model": CHATGPT_WEB_MODEL,
                                "web_reasoning_effort": CHATGPT_WEB_REASONING_EFFORT,
                                "web_model_policy_verified_at": (
                                    browser_session.current_progress_status().get(
                                        "model_policy_verified_at"
                                    )
                                ),
                                "web_worker_id": browser_session.current_worker_id(),
                                "persistent_browser_session": not owns_session,
                                "chat_mode": chat_mode,
                                "chatgpt_project_url": project_url,
                                "response_timeout_seconds": response_timeout_seconds,
                                "response_inactivity_timeout_seconds": response_inactivity_timeout_seconds,
                                "navigation_timeout_seconds": navigation_timeout_seconds,
                                "send_start_timeout_seconds": send_start_timeout_seconds,
                                "send_ready_stable_seconds": send_ready_stable_seconds,
                                "rate_limit_wait_seconds": rate_limit_wait_seconds,
                                "lock_timeout_seconds": lock_timeout_seconds,
                                "web_timing_seconds": browser_session.generation_timing(symbol),
                                "symbol": symbol,
                                "started_at": started_at.isoformat(),
                                "finished_at": _utc_now().isoformat(),
                                "input_path": str(input_path),
                                "input_sha256": input_sha256,
                                "attachment_paths": [str(path) for path in attachment_paths],
                                "output_path": str(output_path),
                                "attempts": attempts_log,
                                "web_attempt_count": len(attempts_log),
                                "web_retry_count": max(0, len(attempts_log) - 1),
                                "chat_cleanup_warnings": cleanup_warnings,
                                "status": "ok",
                            },
                        )
                        return ChatGPTBrowserGenerationResult(
                            input_path=input_path,
                            output_path=output_path,
                            attempts=attempt,
                            chat_urls=tuple(chat_urls),
                            metadata_path=metadata_path,
                        )
                except RuntimeError as exc:
                    errors = (str(exc),)

                previous_errors = errors or ("unknown_validation_error",)
                repair_previous_response = response_received
                attempt_url = chat_url or browser_session.current_url()
                attempts_log.append(
                    _attempt_record(
                        attempt,
                        attempt_started,
                        attempt_url,
                        candidate_path,
                        previous_errors,
                        sanitized_markers=sanitized_markers,
                    )
                )
                cleanup_warning = _queue_chat_for_cleanup(
                    cwd,
                    attempt_url,
                    symbol=symbol,
                    attempt=attempt,
                )
                if cleanup_warning:
                    cleanup_warnings.append(cleanup_warning)
            if not owns_session:
                browser_session.invalidate()
    finally:
        if owns_session:
            browser_session.close()

    metadata_path = output_path.with_name("generation_metadata.json")
    _write_metadata(
        metadata_path,
        {
            "provider_requested": "chatgpt-browser",
            "provider_used": None,
            "browser_engine": engine,
            "persistent_browser_session": not owns_session,
            "chat_mode": chat_mode,
            "chatgpt_project_url": project_url,
            "web_timing_seconds": browser_session.generation_timing(symbol),
            "web_worker_id": browser_session.generation_timing(symbol).get(
                "worker_id"
            ),
            "symbol": symbol,
            "started_at": started_at.isoformat(),
            "finished_at": _utc_now().isoformat(),
            "input_path": str(input_path),
            "input_sha256": input_sha256,
            "attachment_paths": [str(path) for path in attachment_paths],
            "output_path": str(output_path),
            "attempts": attempts_log,
            "web_attempt_count": len(attempts_log),
            "web_retry_count": max(0, len(attempts_log) - 1),
            "chat_cleanup_warnings": cleanup_warnings,
            "status": "failed",
            "errors": list(previous_errors),
        },
    )
    detail = "; ".join(previous_errors) or "no valid response"
    raise RuntimeError(
        f"chatgpt_browser_validation_failed_after_{max_attempts}_attempts: {detail}"
    )


def build_analysis_request(
    symbol: str,
    *,
    previous_errors: tuple[str, ...] = (),
    continuity_requirements: str = "",
    repair_previous_response: bool = False,
    input_attachment_name: str = "chatgpt_input.md",
    previous_attachment_name: str | None = "previous_analysis.md",
) -> str:
    strength_contract = (
        "\nCONTROL OBLIGATORIO DE SELECCION DE SOPORTES:\n"
        "Puntua internamente todos los soportes candidatos antes de elegir. La "
        "Entrada principal debe estar normalmente dentro de 1 ATR10 o 1 "
        "expected_move_1w_abs desde el precio actual; la Entrada ambiciosa, "
        "dentro de 2 ATR10 o 2 expected_move_1w_abs. Un soporte mas remoto no "
        "gana solo por ser fuerte y queda como referencia estructural, salvo "
        "excepcion por evento cierto e inminente explicada expresamente. "
        "Dentro de cada ventana gana la Fortaleza; si dos candidatos difieren "
        "menos de 5 puntos, gana el mas cercano y operativo. No exijas categoria "
        "solida: selecciona la mejor zona alcanzable y puntuala honestamente. "
        "Entrada y Entrada ambiciosa deben ser bloques distintos; si se solapan "
        "o sus centros distan <=0,35 ATR10, tratalos como el mismo soporte salvo "
        "evidencia estructural independiente. Si no hay soporte inferior distinto "
        "dentro de 2 ATR10 o 2 movimientos esperados, usa Sin zona verificable; "
        "un soporte remoto no obliga a fabricar una Entrada ambiciosa.\n"
        "\nCONTROL FINAL OBLIGATORIO DE FORTALEZA (no omitas ninguna linea):\n"
        "Para Entrada incluye literalmente `Fortaleza de Entrada: N/100 · categoria`, "
        "`Desglose de Entrada: estructura A/25; volumen B/20; opciones C/25; "
        "confluencia D/15; durabilidad E/15` y `Factores de Entrada: ...`. "
        "A+B+C+D+E debe ser exactamente N.\n"
        "Puntua primero A, B, C, D y E de forma independiente segun su evidencia; "
        "suma despues los cinco valores y asigna la categoria solo al final. Esta "
        "prohibido elegir primero la categoria o ajustar la puntuacion para alcanzar "
        "40, 70, 85 o 95. Un total exactamente en un umbral solo es valido si surge "
        "naturalmente de la suma independiente.\n"
        "Un total de 70 o mas requiere estructura >=13 y ademas volumen >=10 u "
        "opciones >=12. Un total de 85 o mas requiere al menos dos pilares entre "
        "estructura >=18, volumen >=14 y opciones >=18; uno debe ser estructura o "
        "volumen, con confluencia >=10 y durabilidad >=9. Para 95 o mas exige "
        "estructura >=22, volumen >=17, confluencia >=13 y durabilidad >=12.\n"
        "Volumen/reaccion se calcula mecanicamente con los cinco tramos del prompt "
        "del sistema: POC/HVN 0-4, repeticion 0-5, tasa de defensa 0-4, magnitud "
        "0-4 y recencia 0-3. Sin POC/HVN a <=5% y al menos 3 tests con 2 defensas, "
        "no puede superar 12. Para superar 15 deben cumplirse todos los requisitos "
        "verificables del prompt. No conviertas tests en defensas ni reasignes a "
        "otros componentes los puntos eliminados por un limite.\n"
        "Para Entrada ambiciosa incluye las tres lineas equivalentes: "
        "`Fortaleza de Entrada ambiciosa`, `Desglose de Entrada ambiciosa` y "
        "`Factores de Entrada ambiciosa`. Si no existe esa zona, escribe "
        "`No aplicable` en Fortaleza y Desglose y explica la ausencia en Factores.\n"
        "Selecciona ademas `Resistencia estructural` por fuerza absoluta entre "
        "todas las zonas vigentes en o por encima del precio: no penalices que "
        "este al 1%, 20% o 50%, y usa la distancia solo para desempatar scores "
        "separados por menos de 5 puntos. No la confundas con la Salida operativa. "
        "Incluye `Fortaleza de Resistencia`, `Desglose de Resistencia` y "
        "`Factores de Resistencia` con la misma rubrica 25+20+25+15+15 adaptada "
        "a oferta, rechazos y call walls.\n"
        "Antes de responder, cuenta estas nueve etiquetas en el informe final. "
        "Si falta una sola o la suma no coincide, la respuesta es invalida.\n"
    )
    continuity = ""
    if continuity_requirements:
        continuity = (
            "\nCONTROL OBLIGATORIO DE CONTINUIDAD (duplicado aqui para que no "
            "pueda pasarse por alto):\n"
            f"{continuity_requirements.rstrip()}\n"
            "Para cada nivel anterior, el Motivo debe empezar con Se conserva, "
            "Se reprioriza, Se corrige o Se retira. Si se conserva, "
            "copia exactamente el precio anterior. Si se corrige o retira, "
            "menciona tambien en ese mismo Motivo todos los precios "
            "anteriores exactos y explica la evidencia concreta que justifica "
            "el cambio. Si se reprioriza, menciona tambien todos los precios "
            "anteriores exactos, confirma que el soporte anterior sigue vigente "
            "y demuestra por que una zona realmente distinta es materialmente "
            "mejor para esa funcion. Si es el mismo soporte o la misma estructura, "
            "esta prohibido cambiar sus numeros: usa Se conserva y copia el rango "
            "exacto. La continuidad no da prioridad al nivel antiguo: vuelve a "
            "ordenar todas las zonas vigentes y elige la mejor Entrada principal. "
            "Si el fundamento anterior ya no aplica, recalcula el "
            "nivel desde cero con la evidencia actual: esta prohibido mantener "
            "el rango mediante la formula Se sustituye fundamento. El nuevo "
            "calculo puede coincidir por casualidad, pero debe declararse como "
            "Se corrige y justificarse sin anclarse al numero anterior. No "
            "recalcules, redondees ni reemplaces silenciosamente ningun nivel "
            "anterior. Si un campo dice `no extraida`/`no extraido`, no existe "
            "un valor anterior autoritativo para esa funcion: no uses Se conserva, "
            "Se reprioriza, Se corrige o Se retira para fingir continuidad, ni "
            "llames anterior, antigua o previa a ninguna cifra para esa funcion. "
            "Elige el nivel actual desde cero; puedes mencionar otros niveles "
            "historicos solo como referencias tecnicas, sin atribuirlos al plan "
            "anterior. Comprueba estas cifras una por una antes de responder.\n"
        )
    error_details = ""
    if previous_errors:
        details = "\n".join(f"- {error}" for error in previous_errors)
        strength_retry = ""
        if any("strength" in error for error in previous_errors):
            strength_retry = (
                "Tu respuesta anterior omitio o construyo mal el bloque de "
                "fortaleza. Esta vez verifica expresamente las nueve etiquetas "
                "obligatorias y que cada desglose sume su N/100 antes de enviar.\n"
            )
        error_details = (
            "\nLa respuesta anterior fue invalida por estos errores exactos:\n"
            f"{details}\n"
            f"{strength_retry}"
            "Para cada error "
            "previous_level_mismatch, los numeros de expected son los precios "
            "anteriores exactos que debes mencionar en el Motivo del nivel "
            "indicado; verifica expresamente todos antes de entregar.\n"
        )
    if repair_previous_response:
        return (
            f"Repite completa tu respuesta inmediatamente anterior para {symbol}, "
            "corrigiendo los errores enumerados abajo. No vuelvas a investigar ni "
            "rehagas el analisis: conserva literalmente todo lo que ya era correcto "
            "y cambia solo los campos necesarios y cualquier cifra directamente "
            "dependiente de ellos. Los archivos y el informe anterior ya estan en "
            "este mismo chat; no afirmes que no puedes acceder a ellos."
            f"{error_details}"
            f"{continuity}"
            f"{strength_contract}\n"
            "Devuelve otra vez el informe Markdown final completo, exclusivamente "
            "dentro de un unico bloque de codigo etiquetado markdown. No escribas "
            "texto antes ni despues del bloque."
        )
    if previous_attachment_name:
        previous_context = (
            f" `{previous_attachment_name}` contiene el informe anterior completo: "
            "leelo entero, incluidos narrativa, catalizadores, proximo evento, plan "
            "y fuentes. "
            f"El unico informe anterior valido es `{previous_attachment_name}`, "
            f"respaldado por el bloque Previous Analysis Context de "
            f"`{input_attachment_name}`."
        )
    else:
        previous_context = (
            f" El informe anterior completo esta integrado dentro de "
            f"`{input_attachment_name}`, en el bloque Previous Analysis Context: "
            "leelo entero, incluidos narrativa, catalizadores, proximo evento, plan "
            "y fuentes. Ese bloque es la unica memoria valida del informe anterior."
        )
    return (
        f"Genera el analisis completo de {symbol} usando integramente los archivos "
        f"adjuntos como contexto e instrucciones autoritativas. `{input_attachment_name}` "
        "contiene las reglas y los datos actuales; `codex_input.md` queda "
        "reservado al fallback local y no forma parte de estos adjuntos."
        f"{previous_context} Sigue todas sus reglas, incluido el formato y la "
        "continuidad con el analisis anterior. Ignora "
        "cualquier informe antiguo que encuentres en la web "
        "y no inventes niveles anteriores. Usa la web para descubrir y verificar "
        "catalizadores recientes, nunca para reconstruir la memoria del informe. "
        "No incluyas marcadores internos como :contentReference, oaicite o "
        "identificadores internos de busqueda."
        f"{continuity}"
        f"{strength_contract}"
        f"{error_details}\n"
        "Devuelve exclusivamente un unico bloque de codigo etiquetado markdown. "
        "Dentro debe estar el informe Markdown final completo. No escribas texto "
        "antes ni despues del bloque."
    )


def extract_level_continuity_requirements(source_text: str) -> str:
    prefixes = (
        "nota_anterior:",
        "entrada_anterior:",
        "entrada_ambiciosa_anterior:",
        "stop_de_gestion_anterior:",
        "stop_estructural_anterior:",
        "resistencia_anterior:",
        "salida_anterior:",
    )
    lines = [
        line.strip()
        for line in str(source_text or "").splitlines()
        if line.strip().casefold().startswith(prefixes)
    ]
    return "\n".join(lines)


def build_chatgpt_web_input(source_text: str) -> str:
    omitted_prefixes = (
        "Slim JSON source:",
        "Output file to create:",
        "System prompt source:",
        "- Do not call Gemini, Vertex AI, gemini-stock-analyze, or stock-analyze-batch.",
        "- Do not upload anything to GCS.",
    )
    lines: list[str] = []
    for line in str(source_text or "").splitlines():
        if line.startswith(omitted_prefixes):
            continue
        if line == "# Local Codex Analysis Input":
            line = "# ChatGPT Web Analysis Input"
        lines.append(line)
    return "\n".join(lines).strip() + "\n"


def extract_single_markdown_block(response_text: str) -> str:
    blocks = re.findall(
        r"```markdown\s*\n(.*?)\n```",
        str(response_text or ""),
        flags=re.IGNORECASE | re.DOTALL,
    )
    if len(blocks) != 1:
        raise RuntimeError(
            f"expected_exactly_one_markdown_block: found={len(blocks)}"
        )
    candidate = blocks[0].strip()
    if not candidate:
        raise RuntimeError("markdown_block_empty")
    return candidate + "\n"


INTERNAL_CITATION_MARKER_RE = re.compile(
    r":contentReference\[[^\]\r\n]*\](?:\{[^}\r\n]*\})?"
    r"|\ue200cite\ue202[^\ue201\r\n]*\ue201",
    flags=re.IGNORECASE,
)


def sanitize_internal_citation_markers(markdown: str) -> tuple[str, int]:
    """Remove only ChatGPT UI citation artifacts, preserving report content."""
    sanitized, removed = INTERNAL_CITATION_MARKER_RE.subn("", markdown)
    if not removed:
        return markdown, 0
    return sanitized, removed


def _cleanup_queue_path(cwd: Path) -> Path:
    configured = os.environ.get("CHATGPT_CHAT_CLEANUP_QUEUE_FILE", "").strip()
    return Path(configured).expanduser() if configured else cwd / DEFAULT_CLEANUP_QUEUE_PATH


def _load_cleanup_queue(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"chatgpt_cleanup_queue_invalid: {path}") from exc
    if not isinstance(payload, list):
        raise RuntimeError(f"chatgpt_cleanup_queue_invalid: {path}")
    return [item for item in payload if isinstance(item, dict)]


def _queue_chat_for_cleanup(
    cwd: Path,
    chat_url: str,
    *,
    symbol: str,
    attempt: int,
) -> str | None:
    chat_id = _normal_chat_id(chat_url)
    if chat_id is None:
        return None
    try:
        path = _cleanup_queue_path(cwd)
        path.parent.mkdir(parents=True, exist_ok=True)
        with _CLEANUP_QUEUE_LOCK:
            cleanup_queue = _load_cleanup_queue(path)
            if any(
                str(item.get("chat_id")) == chat_id for item in cleanup_queue
            ):
                return None
            cleanup_queue.append(
                {
                    "chat_id": chat_id,
                    "chat_url": chat_url,
                    "symbol": symbol,
                    "analysis_attempt": int(attempt),
                    "queued_at": _utc_now().isoformat(),
                    "cleanup_attempts": 0,
                    "last_error": None,
                }
            )
            _atomic_write_text(
                path,
                json.dumps(cleanup_queue, ensure_ascii=False, indent=2) + "\n",
            )
    except Exception as exc:
        return f"chatgpt_chat_cleanup_queue_failed: {chat_url}: {exc}"
    return None


def cleanup_queued_chats(
    cwd: Path,
    *,
    headed: bool = False,
    browser_engine: str | None = None,
    delay_seconds: int = DEFAULT_CLEANUP_DELAY_SECONDS,
    max_chats: int | None = None,
    min_age_seconds: int = DEFAULT_CLEANUP_MIN_AGE_SECONDS,
) -> dict[str, Any]:
    queue_path = _cleanup_queue_path(cwd)
    queue = _load_cleanup_queue(queue_path)
    cleanup_limit = DEFAULT_CLEANUP_MAX_CHATS if max_chats is None else max_chats
    if cleanup_limit < 1:
        raise RuntimeError("chatgpt_cleanup_max_chats_must_be_positive")
    if min_age_seconds < 0:
        raise RuntimeError("chatgpt_cleanup_min_age_must_not_be_negative")
    selected = _eligible_cleanup_items(
        queue,
        max_chats=cleanup_limit,
        min_age_seconds=min_age_seconds,
    )
    if not selected:
        return {
            "deleted": 0,
            "remaining": len(queue),
            "failed": 0,
            "rate_limited": False,
        }

    engine = _browser_engine(browser_engine)
    profile_dir = _profile_dir(cwd, engine=engine)
    lock_path = _lock_path(cwd)
    navigation_timeout_seconds = _configured_timeout_seconds(
        "CHATGPT_NAVIGATION_TIMEOUT_SECONDS",
        DEFAULT_NAVIGATION_TIMEOUT_SECONDS,
    )
    rate_limit_wait_seconds = _configured_timeout_seconds(
        "CHATGPT_RATE_LIMIT_WAIT_SECONDS",
        DEFAULT_RATE_LIMIT_WAIT_SECONDS,
    )
    pause_seconds = max(0, int(delay_seconds))
    deleted_ids: set[str] = set()
    failures = 0
    rate_limited = False

    with _exclusive_browser_lock(lock_path, timeout_seconds=DEFAULT_LOCK_TIMEOUT_SECONDS):
        if engine == "firefox":
            browser = _launch_firefox(profile_dir, headed=headed)
            delete_chat = lambda url: _delete_chat_selenium(
                browser,
                chat_url=url,
                timeout_seconds=navigation_timeout_seconds,
            )
            dismiss_rate_limit = lambda: _pause_for_selenium_rate_limit_if_needed(
                browser,
                wait_seconds=rate_limit_wait_seconds,
            )
            ensure_authenticated = lambda: _ensure_selenium_authenticated(
                browser,
                timeout_seconds=navigation_timeout_seconds,
            )
            close_browser = browser.quit
        else:
            try:
                from playwright.sync_api import sync_playwright
            except ImportError as exc:
                raise RuntimeError(
                    "chatgpt_browser_dependency_missing: install requirements-chatgpt.txt"
                ) from exc
            manager = sync_playwright()
            playwright = manager.start()
            context = playwright.chromium.launch_persistent_context(
                user_data_dir=str(profile_dir),
                executable_path=_browser_executable(),
                headless=not headed,
                viewport={"width": 1440, "height": 1000},
                accept_downloads=False,
                args=("--disable-extensions", "--disable-sync"),
            )
            page = context.pages[0] if context.pages else context.new_page()
            delete_chat = lambda url: _delete_chat_playwright(
                page,
                chat_url=url,
                timeout_seconds=navigation_timeout_seconds,
            )
            dismiss_rate_limit = lambda: False
            ensure_authenticated = lambda: _ensure_authenticated(
                page,
                timeout_seconds=navigation_timeout_seconds,
            )
            close_browser = lambda: (context.close(), playwright.stop())

        try:
            ensure_authenticated()
            for index, item in enumerate(selected):
                chat_id = str(item.get("chat_id") or "")
                chat_url = str(item.get("chat_url") or "")
                if dismiss_rate_limit():
                    rate_limited = True
                    break
                try:
                    delete_chat(chat_url)
                    deleted_ids.add(chat_id)
                except Exception as exc:
                    failures += 1
                    item["cleanup_attempts"] = int(item.get("cleanup_attempts") or 0) + 1
                    item["last_error"] = str(exc)[:1000]
                    item["last_attempt_at"] = _utc_now().isoformat()
                    if dismiss_rate_limit():
                        rate_limited = True
                finally:
                    remaining = [
                        queued
                        for queued in queue
                        if str(queued.get("chat_id") or "") not in deleted_ids
                    ]
                    _atomic_write_text(
                        queue_path,
                        json.dumps(remaining, ensure_ascii=False, indent=2) + "\n",
                    )
                if rate_limited:
                    break
                if index + 1 < len(selected) and pause_seconds:
                    time.sleep(pause_seconds)
        finally:
            close_browser()

    remaining = _load_cleanup_queue(queue_path)
    return {
        "deleted": len(deleted_ids),
        "remaining": len(remaining),
        "failed": failures,
        "rate_limited": rate_limited,
    }


def _eligible_cleanup_items(
    queue: list[dict[str, Any]],
    *,
    max_chats: int,
    min_age_seconds: int,
    now: datetime | None = None,
) -> list[dict[str, Any]]:
    cutoff = (now or _utc_now()).timestamp() - min_age_seconds
    eligible = []
    for item in queue:
        try:
            queued_at = datetime.fromisoformat(
                str(item.get("queued_at") or "").replace("Z", "+00:00")
            )
        except ValueError:
            continue
        if queued_at.timestamp() <= cutoff:
            eligible.append(item)
        if len(eligible) >= max_chats:
            break
    return eligible


def _normal_chat_id(url: str) -> str | None:
    match = re.search(
        r"https://chatgpt\.com/(?:g/g-p-[^/?#]+/)?c/([^/?#]+)",
        str(url or ""),
    )
    return match.group(1) if match else None


def _delete_chat_selenium(
    driver: Any,
    *,
    chat_url: str,
    timeout_seconds: int,
) -> None:
    try:
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
    except ImportError as exc:
        raise RuntimeError(
            "chatgpt_browser_dependency_missing: install requirements-chatgpt.txt"
        ) from exc

    chat_id = _normal_chat_id(chat_url)
    if chat_id is None:
        return
    if _normal_chat_id(str(driver.current_url)) != chat_id:
        driver.get(chat_url)
        _wait_for_selenium_prompt(driver, timeout_seconds)

    menu_button = WebDriverWait(driver, timeout_seconds).until(
        lambda current: _visible_selenium_element(
            current,
            "button[data-testid='conversation-options-button']",
        )
    )
    menu_button.click()
    delete_item = WebDriverWait(driver, timeout_seconds).until(
        lambda current: _visible_selenium_element(
            current,
            "[data-testid='delete-chat-menu-item']",
        )
    )
    delete_item.click()
    confirm_button = WebDriverWait(driver, timeout_seconds).until(
        lambda current: _visible_selenium_element(
            current,
            "button[data-testid='delete-conversation-confirm-button']",
        )
    )
    confirm_button.click()
    WebDriverWait(driver, timeout_seconds).until(
        lambda current: _normal_chat_id(str(current.current_url)) != chat_id
    )


def _delete_chat_playwright(
    page: Any,
    *,
    chat_url: str,
    timeout_seconds: int,
) -> None:
    chat_id = _normal_chat_id(chat_url)
    if chat_id is None:
        return
    timeout_ms = timeout_seconds * 1000
    if _normal_chat_id(page.url) != chat_id:
        page.goto(chat_url, wait_until="domcontentloaded", timeout=timeout_ms)
        _wait_for_prompt(page, timeout_seconds)
    page.locator(
        "button[data-testid='conversation-options-button']"
    ).click(timeout=timeout_ms)
    page.locator("[data-testid='delete-chat-menu-item']").click(
        timeout=timeout_ms
    )
    page.locator(
        "button[data-testid='delete-conversation-confirm-button']"
    ).click(timeout=timeout_ms)
    page.wait_for_function(
        "chatId => !location.pathname.includes('/c/' + chatId)",
        arg=chat_id,
        timeout=timeout_ms,
    )


def set_stored_credentials(email: str, password: str) -> None:
    keyring = _require_keyring()
    normalized_email = str(email or "").strip()
    if not normalized_email or not password:
        raise RuntimeError("chatgpt_credentials_require_email_and_password")
    keyring.set_password(CREDENTIAL_SERVICE, CREDENTIAL_ACCOUNT_KEY, normalized_email)
    keyring.set_password(CREDENTIAL_SERVICE, normalized_email, password)


def get_stored_credentials() -> tuple[str, str] | None:
    keyring = _require_keyring()
    email = keyring.get_password(CREDENTIAL_SERVICE, CREDENTIAL_ACCOUNT_KEY)
    if not email:
        return None
    password = keyring.get_password(CREDENTIAL_SERVICE, email)
    if not password:
        return None
    return email, password


def delete_stored_credentials() -> None:
    keyring = _require_keyring()
    email = keyring.get_password(CREDENTIAL_SERVICE, CREDENTIAL_ACCOUNT_KEY)
    if email:
        try:
            keyring.delete_password(CREDENTIAL_SERVICE, email)
        except keyring.errors.PasswordDeleteError:
            pass
    try:
        keyring.delete_password(CREDENTIAL_SERVICE, CREDENTIAL_ACCOUNT_KEY)
    except keyring.errors.PasswordDeleteError:
        pass


def _request_fresh_analysis(
    page: Any,
    *,
    attachment_paths: tuple[Path, ...],
    symbol: str,
    previous_errors: tuple[str, ...],
    repair_previous_response: bool,
    continuity_requirements: str,
    timeout_seconds: int,
    navigation_timeout_seconds: int,
    send_start_timeout_seconds: int,
    send_ready_stable_seconds: int,
    start_url: str = CHATGPT_URL,
    expected_project_url: str | None = None,
    ensure_sol_high: bool = True,
) -> tuple[str, str]:
    timeout_ms = timeout_seconds * 1000
    navigation_timeout_ms = navigation_timeout_seconds * 1000
    if str(page.url).rstrip("/") != start_url.rstrip("/"):
        page.goto(
            start_url,
            wait_until="domcontentloaded",
            timeout=navigation_timeout_ms,
        )
    _wait_for_prompt(page, navigation_timeout_seconds)
    if expected_project_url:
        _wait_for_project_context_playwright(
            page,
            project_url=expected_project_url,
            timeout_seconds=navigation_timeout_seconds,
        )
    if ensure_sol_high:
        _ensure_playwright_sol_high(
            page,
            timeout_seconds=navigation_timeout_seconds,
        )
    initial_count = page.locator(ASSISTANT_SELECTOR).count()
    initial_user_count = page.locator(USER_SELECTOR).count()
    initial_activity_count = page.locator(AGENT_ACTIVITY_SELECTOR).count()

    if not repair_previous_response:
        file_input = page.locator(ATTACHMENT_FILE_INPUT_SELECTOR).first
        if file_input.count() == 0:
            _open_attachment_menu(
                page,
                timeout_seconds=min(navigation_timeout_seconds, 30),
            )
            file_input = page.locator(ATTACHMENT_FILE_INPUT_SELECTOR).first
        file_input.set_input_files(
            [str(path) for path in attachment_paths], timeout=timeout_ms
        )
        for attachment_path in attachment_paths:
            try:
                page.get_by_text(attachment_path.name, exact=False).first.wait_for(
                    state="visible", timeout=30_000
                )
            except Exception as exc:
                raise RuntimeError(
                    f"chatgpt_attachment_upload_not_confirmed: {attachment_path.name}"
                ) from exc
    page.wait_for_timeout(send_ready_stable_seconds * 1000)

    composer = page.locator(PROMPT_SELECTOR)
    composer.fill(
        build_analysis_request(
            symbol,
            previous_errors=previous_errors,
            continuity_requirements=continuity_requirements,
            repair_previous_response=repair_previous_response,
            input_attachment_name=(
                attachment_paths[0].name
                if attachment_paths
                else "chatgpt_input.md"
            ),
            previous_attachment_name=(
                attachment_paths[1].name
                if len(attachment_paths) > 1
                else None
            ),
        )
    )
    composer.press("Enter")

    page.wait_for_function(
        """initial => {
            const users = document.querySelectorAll(
                '[data-message-author-role="user"], [data-content-search-unit-key$=":user"]'
            );
            const assistants = document.querySelectorAll(
                '[data-message-author-role="assistant"], [data-content-search-unit-key$=":assistant"]'
            );
            const activities = document.querySelectorAll(
                '[data-chatgpt-agent-turn-start]'
            );
            const stop = [...document.querySelectorAll(
                '[data-testid="stop-button"], button[aria-label*="Stop"], button[aria-label*="Detener"]'
            )].some(element => element.getClientRects().length > 0);
            return users.length > initial.users
                || assistants.length > initial.assistants
                || activities.length > initial.activities
                || stop;
        }""",
        arg={
            "users": initial_user_count,
            "assistants": initial_count,
            "activities": initial_activity_count,
        },
        timeout=send_start_timeout_seconds * 1000,
    )
    page.wait_for_function(
        """initial => {
            const assistants = document.querySelectorAll(
                '[data-message-author-role="assistant"], [data-content-search-unit-key$=":assistant"]'
            );
            const activities = document.querySelectorAll(
                '[data-chatgpt-agent-turn-start]'
            );
            const stop = [...document.querySelectorAll(
                '[data-testid="stop-button"], button[aria-label*="Stop"], button[aria-label*="Detener"]'
            )].some(element => element.getClientRects().length > 0);
            return assistants.length > initial.assistants
                || activities.length > initial.activities
                || stop;
        }""",
        arg={
            "assistants": initial_count,
            "activities": initial_activity_count,
        },
        timeout=timeout_ms,
    )
    _wait_for_response_complete(page, timeout_seconds=timeout_seconds)

    last_response = page.locator(ASSISTANT_SELECTOR).last
    code_blocks = last_response.locator(MARKDOWN_CODE_BLOCK_SELECTOR)
    block_count = code_blocks.count()
    if block_count != 1:
        raise RuntimeError(
            f"expected_exactly_one_markdown_block: found={block_count}"
        )
    block_text = code_blocks.first.text_content(timeout=timeout_ms) or ""
    if not block_text.strip():
        raise RuntimeError("chatgpt_response_empty")
    response_text = f"```markdown\n{block_text.strip()}\n```"
    return response_text, page.url


def _launch_firefox(profile_dir: Path, *, headed: bool, enable_bidi: bool = True) -> Any:
    try:
        from selenium import webdriver
        from selenium.webdriver.firefox.options import Options
    except ImportError as exc:
        raise RuntimeError(
            "chatgpt_browser_dependency_missing: install requirements-chatgpt.txt"
        ) from exc

    os.environ.setdefault(
        "SE_CACHE_PATH",
        str((profile_dir.parent / "selenium-cache").resolve()),
    )
    options = Options()
    if enable_bidi:
        options.enable_bidi = True
    options.binary_location = _firefox_executable()
    # ChatGPT keeps loading nonessential resources after the interactive DOM is
    # ready. Waiting for the full load event can strand one profile in preflight.
    options.page_load_strategy = "eager"
    use_hidden_window = not headed and os.name == "nt"
    from .windows_desktop import private_desktop_enabled

    use_private_desktop = use_hidden_window and private_desktop_enabled("firefox", profile_dir.parent)
    if use_hidden_window:
        # Private desktops needed a software compositor. Firefox persists these
        # preferences in each worker profile, so restore the prior interactive-
        # desktop rendering values when switching back to hide-after-launch.
        software = use_private_desktop and os.environ.get(
            "ANALYSIS_FIREFOX_SOFTWARE_RENDERING", "1"
        ) != "0"
        options.set_preference("layers.acceleration.disabled", software)
        options.set_preference("layers.gpu-process.enabled", not software)
        options.set_preference("gfx.webrender.software", software)
        options.set_preference("gfx.webrender.software.d3d11", not software)
    if not headed and not use_hidden_window:
        options.add_argument("-headless")
    options.add_argument("-profile")
    options.add_argument(str(profile_dir))
    service = None
    try:
        if use_private_desktop:
            from .firefox_desktop import PrivateDesktopFirefoxService

            service_log = os.environ.get("ANALYSIS_FIREFOX_SERVICE_LOG")
            service = PrivateDesktopFirefoxService(**({"log_output": service_log} if service_log else {}))
            driver = webdriver.Firefox(options=options, service=service)
        else:
            driver = webdriver.Firefox(options=options)
    except Exception as exc:
        if service is not None:
            service.stop()
        raise RuntimeError(f"chatgpt_firefox_launch_failed: {exc}") from exc
    try:
        install_access_observer(driver)
    except Exception as exc:
        driver.quit()
        raise RuntimeError(f"chatgpt_network_observer_failed: {exc}") from exc
    try:
        driver.set_window_size(1440, 1000)
    except Exception as exc:
        # A discarded browsing context means Firefox died just after creating
        # the WebDriver session. Surface it as a launch failure so the normal
        # profile cleanup and retry path can recover it.
        if _is_transient_firefox_launch_error(exc):
            try:
                driver.quit()
            except Exception:
                pass
            raise RuntimeError(f"chatgpt_firefox_launch_failed: {exc}") from exc
        print(
            f"WARNING: unable to resize ChatGPT Firefox window; continuing: {exc}",
            flush=True,
        )
    if use_hidden_window and not use_private_desktop and not _hide_selenium_firefox_window(driver):
        try:
            driver.minimize_window()
        except Exception as exc:
            print(f"WARNING: unable to hide ChatGPT Firefox window: {exc}", flush=True)
    return driver


def _hide_selenium_firefox_window(driver: Any) -> bool:
    """Hide Firefox on Windows while native headless cannot create tabs."""

    if os.name != "nt":
        return False
    try:
        import ctypes
        from ctypes import wintypes

        process_id = int(driver.capabilities.get("moz:processID") or 0)
        if process_id <= 0:
            return False
        hidden = False
        enum_callback = ctypes.WINFUNCTYPE(
            wintypes.BOOL,
            wintypes.HWND,
            wintypes.LPARAM,
        )

        @enum_callback
        def hide_matching_window(window: int, _parameter: int) -> bool:
            nonlocal hidden
            owner = wintypes.DWORD()
            ctypes.windll.user32.GetWindowThreadProcessId(
                window,
                ctypes.byref(owner),
            )
            if owner.value == process_id:
                ctypes.windll.user32.ShowWindow(window, 0)
                hidden = True
            return True

        ctypes.windll.user32.EnumWindows(hide_matching_window, 0)
        return hidden
    except Exception:
        return False


def _launch_firefox_with_retries(profile_dir: Path, *, headed: bool) -> Any:
    """Recover a Firefox profile when Marionette stalls during session creation."""

    last_error: RuntimeError | None = None
    _clear_firefox_profile_runtime_locks(profile_dir)
    for attempt in range(DEFAULT_TRANSIENT_OPEN_RETRIES + 1):
        try:
            return _launch_firefox(profile_dir, headed=headed)
        except RuntimeError as exc:
            last_error = exc
            from .windows_desktop import private_desktop_enabled

            private_desktop = private_desktop_enabled("firefox", profile_dir.parent)
            if not headed and not private_desktop and _is_discarded_browser_context_error(exc):
                _stop_orphaned_firefox_profile_processes(
                    profile_dir,
                    include_manual=True,
                )
                _clear_firefox_profile_runtime_locks(profile_dir)
                time.sleep(DEFAULT_TRANSIENT_OPEN_BACKOFF_SECONDS)
                driver = _launch_firefox(profile_dir, headed=True)
                try:
                    driver.minimize_window()
                except Exception as minimize_error:
                    print(
                        "WARNING: Firefox headless is unavailable and its "
                        f"fallback window could not be minimized: {minimize_error}",
                        flush=True,
                    )
                else:
                    print(
                        "WARNING: Firefox headless is unavailable; using an "
                        "isolated minimized window.",
                        flush=True,
                    )
                return driver
            if (
                not _is_transient_firefox_launch_error(exc)
                or attempt >= DEFAULT_TRANSIENT_OPEN_RETRIES
            ):
                raise
            _stop_orphaned_firefox_profile_processes(
                profile_dir,
                include_manual=True,
            )
            _clear_firefox_profile_runtime_locks(profile_dir)
            time.sleep(DEFAULT_TRANSIENT_OPEN_BACKOFF_SECONDS * (attempt + 1))
    raise last_error or RuntimeError("chatgpt_firefox_launch_failed")


def _request_fresh_analysis_selenium(
    driver: Any,
    *,
    attachment_paths: tuple[Path, ...],
    symbol: str,
    previous_errors: tuple[str, ...],
    repair_previous_response: bool,
    continuity_requirements: str,
    timeout_seconds: int,
    response_inactivity_timeout_seconds: int,
    navigation_timeout_seconds: int,
    send_start_timeout_seconds: int,
    send_ready_stable_seconds: int,
    rate_limit_wait_seconds: int,
    rate_limit_started: Any | None = None,
    rate_limit_finished: Any | None = None,
    attachment_cooldown: _AttachmentUploadCooldown | None = None,
    diagnostic_dir: Path,
    attempt: int,
    start_url: str = CHATGPT_URL,
    expected_project_url: str | None = None,
    ensure_sol_high: bool = True,
    stage_changed: Callable[
        [str, dict[str, float], str, Exception | None], None
    ] | None = None,
) -> tuple[str, str]:
    try:
        from selenium.webdriver.common.by import By
    except ImportError as exc:
        raise RuntimeError(
            "chatgpt_browser_dependency_missing: install requirements-chatgpt.txt"
        ) from exc

    stage = "navigate"
    stage_started = time.monotonic()
    stage_timings: dict[str, float] = {}

    def emit(status: str = "running", error: Exception | None = None) -> None:
        if stage_changed is not None:
            stage_changed(stage, dict(stage_timings), status, error)

    def advance(next_stage: str) -> None:
        nonlocal stage, stage_started
        stage_timings[stage] = round(time.monotonic() - stage_started, 3)
        stage = next_stage
        stage_started = time.monotonic()
        emit()

    emit()
    try:
        driver.set_page_load_timeout(navigation_timeout_seconds)
        if _valid_project_url(start_url):
            _open_project_selenium(
                driver,
                project_url=start_url,
                timeout_seconds=navigation_timeout_seconds,
            )
        else:
            if str(driver.current_url).rstrip("/") != start_url.rstrip("/"):
                driver.get(start_url)
            _wait_for_selenium_prompt(driver, navigation_timeout_seconds)
        if expected_project_url and not _wait_for_selenium_project_context(
            driver,
            expected_project_url,
            navigation_timeout_seconds,
        ):
            raise RuntimeError(
                f"chatgpt_project_context_not_confirmed: {_project_name()}"
            )
        if ensure_sol_high:
            advance("ensure_sol_high")
            _ensure_selenium_sol_high(
                driver,
                timeout_seconds=navigation_timeout_seconds,
            )
        advance("rate_limit_before_attach")
        _pause_for_selenium_rate_limit_if_needed(
            driver,
            wait_seconds=rate_limit_wait_seconds,
            wait_started=rate_limit_started,
            wait_finished=rate_limit_finished,
        )
        advance("locate_composer")
        composer = _visible_selenium_element(driver, PROMPT_SELECTOR)
        if composer is None:
            raise RuntimeError("chatgpt_prompt_not_available")
        _clear_selenium_composer(driver, composer)
        initial_assistant_snapshot = _selenium_assistant_snapshot(driver)
        initial_activity_snapshot = _selenium_agent_activity_snapshot(driver)
        initial_count = initial_assistant_snapshot[0]
        initial_user_snapshot = _selenium_turn_snapshot(driver, USER_SELECTOR)

        if not repair_previous_response:
            _attach_files_selenium_with_cooldown(
                driver,
                attachment_paths,
                timeout_seconds=navigation_timeout_seconds,
                cooldown=(attachment_cooldown or _AttachmentUploadCooldown()),
                advance_stage=advance,
            )
        else:
            advance("confirm_attachments")

        advance("rate_limit_before_send")
        _raise_if_browser_access_blocked(driver, stable_seconds=0)
        _pause_for_selenium_rate_limit_if_needed(
            driver,
            wait_seconds=rate_limit_wait_seconds,
            wait_started=rate_limit_started,
            wait_finished=rate_limit_finished,
        )

        advance("compose")
        composer = _visible_selenium_element(driver, PROMPT_SELECTOR)
        if composer is None:
            raise RuntimeError("chatgpt_prompt_not_available")
        request_text = build_analysis_request(
            symbol,
            previous_errors=previous_errors,
            continuity_requirements=continuity_requirements,
            repair_previous_response=repair_previous_response,
            input_attachment_name=(
                attachment_paths[0].name
                if attachment_paths
                else "chatgpt_input.md"
            ),
            previous_attachment_name=(
                attachment_paths[1].name
                if len(attachment_paths) > 1
                else None
            ),
        ).replace("\n", " ")
        _set_selenium_composer_text(driver, composer, request_text)
        advance("wait_send_ready")
        try:
            send_button = _wait_for_selenium_send_button_stable(
                driver,
                timeout_seconds=navigation_timeout_seconds,
                stable_seconds=send_ready_stable_seconds,
            )
        except Exception:
            advance("recover_send_control")
            try:
                composer = _visible_selenium_element(driver, PROMPT_SELECTOR)
                if composer is None:
                    raise RuntimeError("chatgpt_prompt_not_available")
                _dismiss_duplicate_attachment_dialog_selenium(driver)
                _set_selenium_composer_text(driver, composer, request_text)
                send_button = _wait_for_selenium_send_button_stable(
                    driver,
                    timeout_seconds=min(
                        navigation_timeout_seconds,
                        DEFAULT_SEND_RECOVERY_TIMEOUT_SECONDS,
                    ),
                    stable_seconds=send_ready_stable_seconds,
                )
            except Exception as recovery_exc:
                raise RuntimeError(
                    "chatgpt_send_control_not_ready_after_local_recovery"
                ) from recovery_exc
        advance("send")
        driver.execute_script("arguments[0].click();", send_button)
        advance("wait_request_start")
        first_wait_seconds = min(15, send_start_timeout_seconds)
        request_started = _wait_for_selenium_request_started(
            driver,
            initial_user_snapshot=initial_user_snapshot,
            initial_assistant_count=initial_count,
            initial_assistant_snapshot=initial_assistant_snapshot,
            initial_activity_snapshot=initial_activity_snapshot,
            timeout_seconds=first_wait_seconds,
        )
        if not request_started and not _selenium_composer_has_text(driver):
            request_started = True
        if not request_started:
            _pause_for_selenium_rate_limit_if_needed(
                driver,
                wait_seconds=rate_limit_wait_seconds,
                wait_started=rate_limit_started,
                wait_finished=rate_limit_finished,
            )
            send_button = _selenium_ready_send_button(driver)
            if send_button is not None:
                driver.execute_script("arguments[0].click();", send_button)
            request_started = _wait_for_selenium_request_started(
                driver,
                initial_user_snapshot=initial_user_snapshot,
                initial_assistant_count=initial_count,
                initial_assistant_snapshot=initial_assistant_snapshot,
                initial_activity_snapshot=initial_activity_snapshot,
                timeout_seconds=max(
                    1,
                    send_start_timeout_seconds - first_wait_seconds,
                ),
            )
            if not request_started and not _selenium_composer_has_text(driver):
                request_started = True
        if not request_started:
            raise RuntimeError("chatgpt_send_not_started")

        advance("wait_assistant")
        try:
            _wait_for_selenium_new_assistant(
                driver,
                initial_assistant_snapshot,
                initial_activity_snapshot=initial_activity_snapshot,
                timeout_seconds=min(
                    timeout_seconds,
                    response_inactivity_timeout_seconds,
                ),
            )
        except RuntimeError as exc:
            if "chatgpt_assistant_response_not_started" not in str(exc):
                raise
            advance("recover_assistant_visibility")
            driver.refresh()
            _wait_for_selenium_prompt(driver, navigation_timeout_seconds)
            _wait_for_selenium_new_assistant(
                driver,
                initial_assistant_snapshot,
                initial_activity_snapshot=initial_activity_snapshot,
                timeout_seconds=min(
                    timeout_seconds,
                    DEFAULT_ASSISTANT_VISIBILITY_RECOVERY_TIMEOUT_SECONDS,
                ),
            )
        advance("wait_response")
        _wait_for_selenium_response_complete(
            driver,
            timeout_seconds=timeout_seconds,
            inactivity_timeout_seconds=response_inactivity_timeout_seconds,
        )

        advance("extract")
        code_blocks = _selenium_latest_assistant_code_blocks(driver)
        if len(code_blocks) != 1:
            raise RuntimeError(
                f"expected_exactly_one_markdown_block: found={len(code_blocks)}"
            )
        block_text = code_blocks[0].get_attribute("textContent") or ""
        if not block_text.strip():
            raise RuntimeError("chatgpt_response_empty")
        advance("complete")
        _write_selenium_trace(
            driver,
            diagnostic_dir=diagnostic_dir,
            symbol=symbol,
            attempt=attempt,
            status="ok",
            stage="complete",
            stage_timings=stage_timings,
        )
        emit("ok")
        return f"```markdown\n{block_text.strip()}\n```", driver.current_url
    except Exception as exc:
        stage_timings[stage] = round(time.monotonic() - stage_started, 3)
        emit("failed", exc)
        diagnostic_path = _write_selenium_trace(
            driver,
            diagnostic_dir=diagnostic_dir,
            symbol=symbol,
            attempt=attempt,
            status="failed",
            stage=stage,
            stage_timings=stage_timings,
            error=exc,
            capture_page=True,
        )
        message = str(exc).strip() or "<empty>"
        error_type = type(exc).__name__
        current_url = _safe_selenium_current_url(driver)
        raise RuntimeError(
            "chatgpt_firefox_request_failed: "
            f"stage={stage}; type={error_type}; message={message}; "
            f"url={current_url}; diagnostics={diagnostic_path}"
        ) from exc


def _ensure_selenium_authenticated(driver: Any, *, timeout_seconds: int) -> None:
    try:
        driver.set_page_load_timeout(timeout_seconds)
        driver.get(CHATGPT_URL)
    except Exception as exc:
        raise RuntimeError(f"chatgpt_firefox_navigation_failed: {exc}") from exc

    deadline = time.monotonic() + min(timeout_seconds, 60)
    login_visible_since: float | None = None
    # Retry only the application's account-load error, never a challenge or a
    # submitted prompt. Keep a finite budget and let each reload settle.
    account_reloads: list[dict[str, Any]] = []
    driver._analysis_account_reloads = account_reloads
    retry_after = 0.0
    while time.monotonic() < deadline:
        now = time.monotonic()
        account_error = _selenium_account_load_error_visible(driver)
        if account_error or account_reloads:
            if _selenium_human_verification_visible(driver):
                raise RuntimeError("chatgpt_human_verification_required")
        if account_error and now >= retry_after and len(account_reloads) < 3:
            blocked_before = _blocked_browser_api_paths(driver)
            if _click_selenium_retry(driver):
                account_reloads.append({
                    "attempt": len(account_reloads) + 1,
                    "clicked_at": _utc_now().isoformat(),
                    "blocked_api_paths_before": blocked_before,
                })
                retry_after = time.monotonic() + 10
        # Do not discard the network evidence during recovery. Readiness still
        # requires successful responses; persistent challenges fail after grace.
        if time.monotonic() >= retry_after:
            _raise_if_browser_access_blocked(driver)
            if account_error and len(account_reloads) >= 3:
                raise RuntimeError("chatgpt_account_load_failed: reloads_exhausted=3")
        # The composer shell can precede account hydration. Do not declare a
        # worker ready while its profile or essential backend requests fail.
        login_visible = _selenium_login_visible(driver)
        if (
            _selenium_prompt_visible(driver) and not login_visible
            and not _selenium_account_not_ready(driver)
            and not _blocked_browser_api_paths(driver)
        ):
            return
        now = time.monotonic()
        if login_visible:
            login_visible_since = login_visible_since or now
            if now - login_visible_since >= LOGIN_REQUIRED_STABLE_SECONDS:
                raise RuntimeError(
                    "chatgpt_login_required: run chatgpt_browser_generator login once"
                )
        else:
            login_visible_since = None
        time.sleep(0.5)
    _raise_if_browser_access_blocked(driver, stable_seconds=0)
    if _selenium_human_verification_visible(driver):
        raise RuntimeError("chatgpt_human_verification_required")
    raise RuntimeError("chatgpt_firefox_navigation_failed: prompt_not_available")


def _normalize_chatgpt_ui_label(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    ascii_text = "".join(char for char in text if not unicodedata.combining(char))
    return re.sub(r"\s+", " ", ascii_text).strip().casefold()


def _selenium_element_label(element: Any) -> str:
    text = str(element.text or "").strip()
    if not text:
        text = str(element.get_attribute("textContent") or "").strip()
    return _normalize_chatgpt_ui_label(text)


def _is_selenium_reasoning_trigger(element: Any) -> bool:
    label = _selenium_element_label(element)
    selected_effort = _normalize_chatgpt_ui_label(
        element.get_attribute("data-selected-reasoning-effort")
    )
    has_stable_hook = (
        element.get_attribute("data-codex-intelligence-trigger") == "true"
        or element.get_attribute("data-composer-navigation-target") == "reasoning"
    )
    return bool(
        element.is_displayed()
        and (
            has_stable_hook
            or selected_effort in CHATGPT_WEB_REASONING_LABELS
            or label in CHATGPT_WEB_REASONING_LABELS
            or label in CHATGPT_WEB_REASONING_CONTROL_LABELS
            or _normalize_chatgpt_ui_label(element.get_attribute("title"))
            in CHATGPT_WEB_REASONING_CONTROL_LABELS
        )
    )


def _selenium_reasoning_effort_is_high(element: Any) -> bool:
    selected_effort = _normalize_chatgpt_ui_label(
        element.get_attribute("data-selected-reasoning-effort")
    )
    return (
        selected_effort in CHATGPT_WEB_HIGH_LABELS
        or _selenium_element_label(element) in CHATGPT_WEB_HIGH_LABELS
    )


def _ensure_selenium_sol_high(driver: Any, *, timeout_seconds: int) -> None:
    """Force High reasoning; for paid ChatGPT accounts High is GPT-5.6 Sol."""

    try:
        from selenium.webdriver.common.by import By
        from selenium.webdriver.common.keys import Keys
        from selenium.webdriver.support.ui import WebDriverWait

        def reasoning_pill(current: Any) -> Any | None:
            # ChatGPT now renders the trigger text as "Esfuerzo de razonamiento"
            # and exposes the selected level through data attributes. Prefer those
            # stable hooks while retaining the old visible-label fallback.
            for button in current.find_elements(
                By.CSS_SELECTOR,
                (
                    "button[data-codex-intelligence-trigger='true'], "
                    "button[data-composer-navigation-target='reasoning'], "
                    "button[aria-haspopup='menu']"
                ),
            ):
                try:
                    if _is_selenium_reasoning_trigger(button):
                        return button
                except Exception:
                    continue
            return None

        def open_menu() -> Any:
            deadline = time.monotonic() + min(timeout_seconds, 30)
            last_error: Exception | None = None
            while time.monotonic() < deadline:
                current_pill = reasoning_pill(driver)
                if current_pill is None:
                    time.sleep(0.25)
                    continue
                visible_options = [
                    option
                    for option in driver.find_elements(
                        By.CSS_SELECTOR,
                        "[role='menuitemradio']",
                    )
                ]
                if visible_options or _visible_selenium_element(driver, "[data-model-reasoning-effort-slider]"):
                    return current_pill
                try:
                    if current_pill.get_attribute("aria-expanded") != "true":
                        current_pill.send_keys(Keys.ENTER)
                except Exception as exc:
                    last_error = exc
                    try:
                        current_pill = reasoning_pill(driver)
                        if current_pill is not None:
                            current_pill.send_keys(Keys.ENTER)
                    except Exception as retry_exc:
                        last_error = retry_exc
                menu_deadline = min(deadline, time.monotonic() + 3)
                while time.monotonic() < menu_deadline:
                    try:
                        if _visible_selenium_element(driver, "[data-model-reasoning-effort-slider]") or driver.find_elements(
                            By.CSS_SELECTOR,
                            "[role='menuitemradio']",
                        ):
                            return current_pill
                    except Exception as exc:
                        last_error = exc
                    time.sleep(0.25)
            detail = str(last_error).strip() if last_error is not None else ""
            raise RuntimeError(
                "reasoning_menu_not_opened"
                + (f": {detail}" if detail else "")
            )

        pill = open_menu()
        model_toggle_selector = (
            "[role='menuitem'][aria-label='Seleccionar modelo'], "
            "[role='menuitem'][aria-label='Select model']"
        )
        model_toggle = _visible_selenium_element(driver, model_toggle_selector)
        if model_toggle is not None and model_toggle.get_attribute("aria-expanded") != "true":
            model_toggle.click()
            WebDriverWait(driver, min(timeout_seconds, 15)).until(
                lambda current: _visible_selenium_element(current, "[role='menuitemradio']")
            )
        model_options = driver.find_elements(
            By.CSS_SELECTOR,
            "[role='menuitemradio']",
        )
        sol_option = next(
            (
                option
                for option in model_options
                if _selenium_element_label(option)
                == _normalize_chatgpt_ui_label(CHATGPT_WEB_MODEL_LABEL)
            ),
            None,
        )
        if sol_option is None:
            raise RuntimeError("gpt_5_6_sol_option_not_found")
        if sol_option.get_attribute("aria-checked") != "true":
            driver.execute_script("arguments[0].click();", sol_option)
            pill = open_menu()

        def sol_is_selected(current: Any) -> bool:
            return any(
                _selenium_element_label(option)
                == _normalize_chatgpt_ui_label(CHATGPT_WEB_MODEL_LABEL)
                and option.get_attribute("aria-checked") == "true"
                for option in current.find_elements(
                    By.CSS_SELECTOR,
                    "[role='menuitemradio']",
                )
            )

        WebDriverWait(driver, min(timeout_seconds, 15)).until(sol_is_selected)

        model_toggle = _visible_selenium_element(driver, model_toggle_selector)
        if model_toggle is not None and model_toggle.get_attribute("aria-expanded") == "true":
            model_toggle.click()

        keyboard_slider = _visible_selenium_element(
            driver, "[role='menuitem'][aria-keyshortcuts='ArrowLeft ArrowRight']"
        )
        if model_toggle is not None and keyboard_slider is None:
            keyboard_slider = WebDriverWait(driver, min(timeout_seconds, 15)).until(
                lambda current: _visible_selenium_element(
                    current, "[role='menuitem'][aria-keyshortcuts='ArrowLeft ArrowRight']"
                )
            )

        slider = WebDriverWait(driver, min(timeout_seconds, 15)).until(
            lambda current: next(
                iter(current.find_elements(By.CSS_SELECTOR, "[role='slider']")),
                None,
            )
        )
        if slider.get_attribute("aria-valuenow") != CHATGPT_WEB_HIGH_SLIDER_VALUE:
            if keyboard_slider is not None:
                # The September slider's ARIA thumb is hidden; its menuitem
                # handles the documented arrow-key interaction instead.
                keyboard_slider.send_keys(Keys.ARROW_LEFT * 4)
                keyboard_slider.send_keys(Keys.ARROW_RIGHT * 2)
            else:
                slider.send_keys(Keys.HOME)
                slider.send_keys(Keys.ARROW_RIGHT)
                slider.send_keys(Keys.ARROW_RIGHT)
            WebDriverWait(driver, min(timeout_seconds, 15)).until(
                lambda current: (
                    any(
                        item.get_attribute("aria-valuenow")
                        == CHATGPT_WEB_HIGH_SLIDER_VALUE
                        for item in current.find_elements(
                            By.CSS_SELECTOR,
                            "[role='slider']",
                        )
                    )
                )
            )

        driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)

        if keyboard_slider is not None:
            # Model and slider value were both verified above. The new closed
            # trigger only says "Reasoning effort", not the selected level.
            return

        def high_is_selected(current: Any) -> bool:
            selected = reasoning_pill(current)
            if selected is None:
                return False
            return _selenium_reasoning_effort_is_high(selected)

        WebDriverWait(driver, min(timeout_seconds, 15)).until(high_is_selected)
    except Exception as exc:
        raise RuntimeError(
            "chatgpt_sol_high_not_confirmed: expected reasoning=Alta/High; "
            f"detail={str(exc).strip() or type(exc).__name__}"
        ) from exc


def _ensure_playwright_sol_high(page: Any, *, timeout_seconds: int) -> None:
    """Playwright equivalent of the mandatory GPT-5.6 Sol High check."""

    timeout_ms = min(timeout_seconds, 30) * 1000
    try:
        buttons = page.locator("button[aria-haspopup='menu']")
        pill = None
        for index in range(buttons.count()):
            candidate = buttons.nth(index)
            if not candidate.is_visible():
                continue
            if (
                _normalize_chatgpt_ui_label(candidate.inner_text())
                in CHATGPT_WEB_REASONING_LABELS | CHATGPT_WEB_REASONING_CONTROL_LABELS
                or _normalize_chatgpt_ui_label(candidate.get_attribute("title"))
                in CHATGPT_WEB_REASONING_CONTROL_LABELS
            ):
                pill = candidate
                break
        if pill is None:
            raise RuntimeError("reasoning_control_not_found")
        pill.press("Enter")
        model_toggle = page.locator(
            "[role='menuitem'][aria-label='Seleccionar modelo'], "
            "[role='menuitem'][aria-label='Select model']"
        )
        if model_toggle.count() and model_toggle.first.is_visible():
            if model_toggle.first.get_attribute("aria-expanded") != "true":
                model_toggle.first.click(timeout=timeout_ms)
        sol_option = page.get_by_role(
            "menuitemradio",
            name=CHATGPT_WEB_MODEL_LABEL,
            exact=True,
        )
        sol_option.wait_for(state="visible", timeout=timeout_ms)
        if sol_option.get_attribute("aria-checked") != "true":
            sol_option.click(timeout=timeout_ms)
            if pill.get_attribute("aria-expanded") != "true":
                pill.press("Enter")
        page.wait_for_function(
            """label => [...document.querySelectorAll('[role="menuitemradio"]')]
                .some(item => (item.textContent || '').trim() === label &&
                    item.getAttribute('aria-checked') === 'true')""",
            arg=CHATGPT_WEB_MODEL_LABEL,
            timeout=timeout_ms,
        )

        # Advanced model choices and the simple effort slider share one menu.
        if model_toggle.count() and model_toggle.first.is_visible():
            if model_toggle.first.get_attribute("aria-expanded") == "true":
                model_toggle.first.click(timeout=timeout_ms)
        keyboard_slider = page.locator(
            "[role='menuitem'][aria-keyshortcuts='ArrowLeft ArrowRight']"
        )
        if model_toggle.count():
            keyboard_slider.first.wait_for(state="visible", timeout=timeout_ms)
        has_keyboard_slider = bool(keyboard_slider.count() and keyboard_slider.first.is_visible())

        slider = page.locator("[role='slider']").first
        slider.wait_for(state="attached" if has_keyboard_slider else "visible", timeout=timeout_ms)
        if slider.get_attribute("aria-valuenow") != CHATGPT_WEB_HIGH_SLIDER_VALUE:
            if has_keyboard_slider:
                for key in ["ArrowLeft"] * 4 + ["ArrowRight"] * 2:
                    keyboard_slider.first.press(key)
            else:
                slider.press("Home")
                slider.press("ArrowRight")
                slider.press("ArrowRight")
            page.wait_for_function(
                """target => document.querySelector(
                    "[role='slider']"
                )?.getAttribute('aria-valuenow') === target""",
                arg=CHATGPT_WEB_HIGH_SLIDER_VALUE,
                timeout=timeout_ms,
            )
        page.keyboard.press("Escape")
        if has_keyboard_slider:
            return
        page.wait_for_function(
            """labels => [...document.querySelectorAll(
                "button[aria-haspopup='menu']"
            )].some(button => button.offsetParent !== null &&
                labels.includes((button.innerText || '').trim().toLowerCase()))""",
            arg=list(CHATGPT_WEB_HIGH_LABELS),
            timeout=timeout_ms,
        )
    except Exception as exc:
        raise RuntimeError(
            "chatgpt_sol_high_not_confirmed: expected reasoning=Alta/High; "
            f"detail={str(exc).strip() or type(exc).__name__}"
        ) from exc


def _resolve_project_url_selenium(driver: Any, *, cwd: Path) -> str:
    stored = _stored_project_url(cwd)
    if stored:
        return stored

    from selenium.webdriver.common.by import By

    project_name = _project_name()
    for anchor in driver.find_elements(By.CSS_SELECTOR, "a[href]"):
        try:
            text = " ".join((anchor.text or "").split())
            href = str(anchor.get_attribute("href") or "").strip()
        except Exception:
            continue
        if text.casefold() == project_name.casefold() and _valid_project_url(href):
            return _save_project_url(cwd, href)
    raise RuntimeError(f"chatgpt_project_not_found: {project_name}")


def _open_project_selenium(
    driver: Any,
    *,
    project_url: str,
    timeout_seconds: int,
) -> None:
    """Open the configured project through the sidebar, with direct URL as fallback."""

    if str(driver.current_url).rstrip("/") != CHATGPT_URL.rstrip("/"):
        driver.get(CHATGPT_URL)
    _wait_for_selenium_prompt(driver, timeout_seconds)
    if _selenium_project_ready(driver, project_url):
        return

    if _click_selenium_project(
        driver,
        _project_name(),
        project_url=project_url,
        timeout_seconds=min(timeout_seconds, 30),
    ):
        if _wait_for_selenium_project_ready(driver, project_url, timeout_seconds):
            return

    driver.get(project_url)
    _wait_for_selenium_prompt(driver, timeout_seconds)
    if not _wait_for_selenium_project_ready(
        driver, project_url, min(timeout_seconds, 30)
    ):
        raise RuntimeError(f"chatgpt_project_not_open: {_project_name()}")


def _click_selenium_project(
    driver: Any,
    project_name: str,
    *,
    project_url: str,
    timeout_seconds: int = 30,
) -> bool:
    from selenium.webdriver.common.by import By

    normalized_name = " ".join(project_name.split()).casefold()
    expected_id = _chatgpt_project_id(project_url)
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        # Current ChatGPT sidebar uses a project-id row and an aria-labelled
        # compose button; the older data-fill/#compose markup is absent.
        for row in driver.find_elements(
            By.CSS_SELECTOR, "[data-app-action-sidebar-project-id]"
        ):
            try:
                row_id = row.get_attribute(
                    "data-app-action-sidebar-project-id"
                )
                row_name = row.get_attribute(
                    "data-app-action-sidebar-project-label"
                )
                if (
                    not expected_id
                    or row_id.casefold() != expected_id
                    or " ".join(row_name.split()).casefold() != normalized_name
                ):
                    continue
                for button in row.find_elements(By.CSS_SELECTOR, "button[aria-label]"):
                    label = _normalize_chatgpt_ui_label(
                        button.get_attribute("aria-label") or ""
                    )
                    if label in (
                        f"nuevo chat en {normalized_name}",
                        f"new chat in {normalized_name}",
                    ):
                        driver.execute_script("arguments[0].click();", button)
                        return True
            except Exception:
                continue
        rows = driver.find_elements(By.CSS_SELECTOR, "div[tabindex][data-fill]")
        for row in rows:
            try:
                text = " ".join((row.text or "").split()).casefold()
                if text != normalized_name:
                    continue
                compose_icons = row.find_elements(
                    By.CSS_SELECTOR,
                    "use[href*='#compose']",
                )
                if not compose_icons:
                    continue
                button = compose_icons[0].find_element(
                    By.XPATH,
                    "./ancestor::button[1]",
                )
                driver.execute_script(
                    "arguments[0].scrollIntoView({block: 'center'});",
                    button,
                )
                try:
                    button.click()
                except Exception:
                    driver.execute_script("arguments[0].click();", button)
                return True
            except Exception:
                continue
        time.sleep(1)
    return False


def _wait_for_selenium_project_ready(
    driver: Any,
    project_url: str,
    timeout_seconds: int,
) -> bool:
    deadline = time.monotonic() + timeout_seconds
    login_visible_since: float | None = None
    last_retry_click = 0.0
    while time.monotonic() < deadline:
        _raise_if_browser_access_blocked(driver)
        if _selenium_project_ready(driver, project_url):
            return True
        now = time.monotonic()
        if _selenium_login_visible(driver):
            login_visible_since = login_visible_since or now
            if now - login_visible_since >= LOGIN_REQUIRED_STABLE_SECONDS:
                raise RuntimeError("chatgpt_login_required")
        else:
            login_visible_since = None
        if now - last_retry_click >= 5 and _click_selenium_retry(driver):
            last_retry_click = now
        time.sleep(1)
    if _selenium_human_verification_visible(driver):
        raise RuntimeError("chatgpt_human_verification_required")
    return False


def _selenium_project_ready(driver: Any, project_url: str) -> bool:
    # ChatGPT currently activates the project but canonicalizes the address bar
    # back to https://chatgpt.com/. The exact project labels in the composer are
    # therefore the authoritative signal; the URL alone is not.
    return (
        not _blocked_browser_api_paths(driver)
        and not _selenium_account_not_ready(driver)
        and _selenium_prompt_visible(driver)
    ) and (
        _selenium_project_context_visible(driver, _project_name())
        or _same_chatgpt_project(str(driver.current_url), project_url)
    )


def _wait_for_selenium_project_context(
    driver: Any,
    project_url: str,
    timeout_seconds: int,
) -> bool:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        _raise_if_browser_access_blocked(driver)
        if _selenium_project_ready(driver, project_url):
            return True
        time.sleep(0.25)
    return False


def _selenium_project_context_visible(driver: Any, project_name: str) -> bool:
    from selenium.webdriver.common.by import By

    expected = _normalize_chatgpt_ui_label(project_name)
    # A sidebar shortcut labelled "New chat in X" does not mean the composer
    # is currently inside X. Exclude project rows from the context assertion.
    for element in driver.find_elements(
        By.XPATH,
        "//*[@aria-label and not(ancestor::*[@data-app-action-sidebar-project-id])]",
    ):
        try:
            if not element.is_displayed():
                continue
            label = _normalize_chatgpt_ui_label(
                element.get_attribute("aria-label")
            )
        except Exception:
            continue
        is_project_switch = label.startswith(
            ("cambiar proyecto:", "switch project:")
        )
        is_project_composer = label.startswith(
            ("nuevo chat en ", "new chat in ")
        )
        if label in (
            f"cambiar proyecto: {expected}", f"switch project: {expected}",
            f"nuevo chat en {expected}", f"new chat in {expected}",
        ) and (is_project_switch or is_project_composer):
            return True
    return False


def _same_chatgpt_project(current_url: str, project_url: str) -> bool:
    current_id = _chatgpt_project_id(current_url)
    expected_id = _chatgpt_project_id(project_url)
    return bool(current_id and expected_id and current_id == expected_id)


def _chatgpt_project_id(url: str) -> str | None:
    match = re.search(r"/g/(g-p-[^/?#]+)", url)
    if not match:
        return None
    raw_id = match.group(1)
    stable_id = re.match(r"(g-p-[0-9a-fA-F]{32})(?:-|$)", raw_id)
    return stable_id.group(1).casefold() if stable_id else raw_id.casefold()


def _wait_for_selenium_prompt(driver: Any, timeout_seconds: int) -> None:
    deadline = time.monotonic() + timeout_seconds
    next_reload = time.monotonic() + 30
    last_retry_click = 0.0
    login_visible_since: float | None = None
    while time.monotonic() < deadline:
        _raise_if_browser_access_blocked(driver)
        login_visible = _selenium_login_visible(driver)
        if (
            _selenium_prompt_visible(driver) and not login_visible
            and not _selenium_account_not_ready(driver)
            and not _blocked_browser_api_paths(driver)
        ):
            return

        now = time.monotonic()
        if login_visible:
            login_visible_since = login_visible_since or now
            if now - login_visible_since >= LOGIN_REQUIRED_STABLE_SECONDS:
                raise RuntimeError("chatgpt_login_required")
        else:
            login_visible_since = None
        if now - last_retry_click >= 5 and _click_selenium_retry(driver):
            last_retry_click = now
            next_reload = now + 30
            time.sleep(2)
            continue
        if now >= next_reload:
            try:
                driver.execute_script("window.location.reload()")
            except Exception:
                pass
            next_reload = now + 30
        time.sleep(1)
    _raise_if_browser_access_blocked(driver, stable_seconds=0)
    if _selenium_human_verification_visible(driver):
        raise RuntimeError("chatgpt_human_verification_required")
    raise RuntimeError("chatgpt_prompt_not_available")


def _click_selenium_retry(driver: Any) -> bool:
    from selenium.webdriver.common.by import By

    xpath = (
        "//button[normalize-space()='Retry' or "
        "normalize-space()='Try again' or "
        "normalize-space()='Reintentar' or "
        "normalize-space()='Volver a cargar']"
    )
    for button in driver.find_elements(By.XPATH, xpath):
        try:
            if button.is_displayed() and button.is_enabled():
                button.click()
                return True
        except Exception:
            continue
    return False


def _selenium_prompt_visible(driver: Any) -> bool:
    return _visible_selenium_element(driver, PROMPT_SELECTOR) is not None


def _selenium_account_not_ready(driver: Any) -> bool:
    text = _normalize_chatgpt_ui_label(driver.execute_script(
        "return document.body ? document.body.innerText : '';"
    ))
    return any(marker in text for marker in (
        "cargando perfil", "loading profile", "no hemos podido cargar tu cuenta",
        "unable to load your account", "we couldn't load your account",
    ))


def _selenium_account_load_error_visible(driver: Any) -> bool:
    text = _normalize_chatgpt_ui_label(driver.execute_script(
        "return document.body ? document.body.innerText : '';"
    ))
    return any(marker in text for marker in (
        "no hemos podido cargar tu cuenta", "unable to load your account",
        "we couldn't load your account",
    ))


def _selenium_login_visible(driver: Any) -> bool:
    try:
        from selenium.webdriver.common.by import By

        xpath = (
            "//*[self::button or self::a][normalize-space()='Log in' or "
            "normalize-space()='Iniciar sesión' or "
            "normalize-space()='Iniciar sesion']"
        )
        return any(
            element.is_displayed()
            for element in driver.find_elements(By.XPATH, xpath)
        )
    except Exception:
        return False


def _visible_selenium_element(driver: Any, selector: str) -> Any | None:
    from selenium.common.exceptions import StaleElementReferenceException
    from selenium.webdriver.common.by import By

    for element in driver.find_elements(By.CSS_SELECTOR, selector):
        try:
            if element.is_displayed():
                return element
        except StaleElementReferenceException:
            continue
    return None


def _clear_selenium_composer(driver: Any, composer: Any) -> None:
    _clear_selenium_composer_attachments(driver)
    _set_selenium_composer_text(driver, composer, "")
    if _selenium_composer_text(composer):
        raise RuntimeError("chatgpt_stale_draft_not_cleared")


def _clear_selenium_composer_attachments(driver: Any) -> None:
    from selenium.webdriver.common.by import By

    selector = (
        'button[aria-label^="Quitar " i], '
        'button[aria-label^="Remove " i]'
    )
    for _ in range(50):
        buttons = driver.find_elements(By.CSS_SELECTOR, selector)
        if not buttons:
            return
        driver.execute_script("arguments[0].click();", buttons[0])
        time.sleep(0.1)
    raise RuntimeError("chatgpt_stale_attachments_not_cleared")


def _set_selenium_composer_text(
    driver: Any,
    composer: Any,
    text: str,
) -> None:
    driver.execute_script(
        """
        const element = arguments[0];
        const text = arguments[1];
        element.focus();

        if (element instanceof HTMLTextAreaElement ||
            element instanceof HTMLInputElement) {
          const prototype = element instanceof HTMLTextAreaElement
            ? HTMLTextAreaElement.prototype
            : HTMLInputElement.prototype;
          const setter = Object.getOwnPropertyDescriptor(prototype, 'value').set;
          setter.call(element, text);
          element.dispatchEvent(new InputEvent('input', {
            bubbles: true,
            inputType: 'insertText',
            data: text,
          }));
          return;
        }

        const selection = window.getSelection();
        const range = document.createRange();
        range.selectNodeContents(element);
        selection.removeAllRanges();
        selection.addRange(range);
        document.execCommand('delete', false, null);
        if (text) {
          document.execCommand('insertText', false, text);
        }
        """,
        composer,
        text,
    )

    expected = _normalize_selenium_composer_text(text)
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        current = _visible_selenium_element(driver, PROMPT_SELECTOR) or composer
        actual = _normalize_selenium_composer_text(
            _selenium_composer_text(current)
        )
        if actual == expected:
            return
        time.sleep(0.1)
    raise RuntimeError(
        "chatgpt_composer_text_not_applied: "
        f"expected_length={len(expected)} actual_length={len(actual)}"
    )


def _selenium_composer_text(composer: Any) -> str:
    value = composer.get_attribute("value")
    text = value if value is not None else composer.get_attribute("textContent")
    return str(text or "").strip()


def _normalize_selenium_composer_text(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def _is_chatgpt_rate_limit_text(text: str) -> bool:
    normalized = _normalize_selenium_composer_text(text).casefold()
    return any(
        marker in normalized
        for marker in (
            "demasiadas solicitudes",
            "solicitudes demasiado rapido",
            "solicitudes demasiado r\u00e1pido",
            "too many requests",
            "requests too quickly",
        )
    )


def _visible_selenium_rate_limit_dialog(driver: Any) -> Any | None:
    from selenium.webdriver.common.by import By

    selectors = '[role="dialog"], [data-testid*="modal"], [data-testid*="dialog"]'
    for dialog in driver.find_elements(By.CSS_SELECTOR, selectors):
        try:
            if dialog.is_displayed() and _is_chatgpt_rate_limit_text(dialog.text):
                return dialog
        except Exception:
            continue
    for title in driver.find_elements(
        By.XPATH,
        "//*[normalize-space()='Demasiadas solicitudes' or "
        "normalize-space()='Too many requests']",
    ):
        try:
            if title.is_displayed():
                return title
        except Exception:
            continue
    return None


def _pause_for_selenium_rate_limit_if_needed(
    driver: Any,
    *,
    wait_seconds: int,
    wait_started: Any | None = None,
    wait_finished: Any | None = None,
) -> bool:
    from selenium.webdriver.common.by import By

    dialog = _visible_selenium_rate_limit_dialog(driver)
    if dialog is None:
        return False

    buttons = dialog.find_elements(By.CSS_SELECTOR, "button")
    if not buttons:
        buttons = driver.find_elements(By.CSS_SELECTOR, "button")
    for button in buttons:
        try:
            label = _normalize_selenium_composer_text(
                f"{button.text} {button.get_attribute('aria-label') or ''}"
            ).casefold()
            if any(action in label for action in ("entendido", "got it", "ok")):
                driver.execute_script("arguments[0].click();", button)
                break
        except Exception:
            continue

    pause_seconds = max(1, int(wait_seconds))
    resume_at = datetime.now().astimezone() + timedelta(seconds=pause_seconds)
    resume_label = resume_at.strftime("%H:%M:%S")
    if wait_started is not None:
        wait_started(resume_at)
    print(
        "ChatGPT Web rate limit detected; "
        f"waiting {pause_seconds}s before retrying (resume at {resume_label})."
    )
    try:
        time.sleep(pause_seconds)
    finally:
        if wait_finished is not None:
            wait_finished()
    return True


def _selenium_text_visible(driver: Any, text: str) -> bool:
    from selenium.webdriver.common.by import By

    literal = json.dumps(text)
    xpath = f"//*[contains(normalize-space(.), {literal})]"
    return any(
        element.is_displayed()
        for element in driver.find_elements(By.XPATH, xpath)
    )


def _selenium_attachment_chip_visible(driver: Any, filename: str) -> bool:
    from selenium.webdriver.common.by import By

    literal = json.dumps(filename)
    xpath = (
        "//*[("
        f"@role='group' and @aria-label={literal}) or "
        f"contains(@aria-label, {literal}) or "
        f"contains(@title, {literal}) or "
        f"contains(normalize-space(.), {literal})]"
    )
    for element in driver.find_elements(By.XPATH, xpath):
        try:
            if element.is_displayed():
                return True
        except Exception:
            continue
    return False


def _dismiss_duplicate_attachment_dialog_selenium(driver: Any) -> bool:
    from selenium.webdriver.common.by import By

    dialogs = driver.find_elements(
        By.CSS_SELECTOR,
        '[data-testid="modal-duplicate-file"] [role="dialog"], '
        '[data-testid="modal-duplicate-file"]',
    )
    for dialog in dialogs:
        try:
            if not dialog.is_displayed():
                continue
            for button in dialog.find_elements(By.CSS_SELECTOR, "button"):
                label = _normalize_selenium_composer_text(
                    f"{button.text} {button.get_attribute('aria-label') or ''}"
                ).casefold()
                if any(action in label for action in ("aceptar", "accept", "ok")):
                    driver.execute_script("arguments[0].click();", button)
                    return True
        except Exception:
            continue
    return False


def _attachment_limit_wait_seconds(
    text: str,
    *,
    default_wait_seconds: int = DEFAULT_ATTACHMENT_LIMIT_WAIT_SECONDS,
) -> int | None:
    normalized = _normalize_selenium_composer_text(text).casefold()
    markers = (
        "te has quedado sin archivos adjuntos",
        "limite de carga de archivos",
        "límite de carga de archivos",
        "file upload limit",
        "out of file uploads",
        "run out of file uploads",
    )
    if not any(marker in normalized for marker in markers):
        return None
    minute_match = re.search(
        r"(?:en|in)\s+(\d+)\s*(?:minuto|minutos|minute|minutes|min)\b",
        normalized,
    )
    second_match = re.search(
        r"(?:en|in)\s+(\d+)\s*(?:segundo|segundos|second|seconds|sec)\b",
        normalized,
    )
    if minute_match:
        wait_seconds = int(minute_match.group(1)) * 60
    elif second_match:
        wait_seconds = int(second_match.group(1))
    else:
        wait_seconds = max(1, int(default_wait_seconds))
    return wait_seconds + DEFAULT_ATTACHMENT_LIMIT_MARGIN_SECONDS


def _selenium_attachment_limit_wait_seconds(driver: Any) -> int | None:
    try:
        visible_text = driver.execute_script(
            "return document.body ? document.body.innerText : '';"
        )
    except Exception:
        return None
    return _attachment_limit_wait_seconds(str(visible_text or "")[-20_000:])


def _attach_files_selenium_with_cooldown(
    driver: Any,
    attachment_paths: tuple[Path, ...],
    *,
    timeout_seconds: int,
    cooldown: _AttachmentUploadCooldown,
    advance_stage: Callable[[str], None] | None = None,
) -> None:
    from selenium.webdriver.common.by import By

    filenames = tuple(path.name for path in attachment_paths)
    limit_retry = 0
    confirmation_retry = 0
    while True:
        if cooldown.status()["waiting"]:
            if advance_stage is not None:
                advance_stage("attachment_limit_wait")
            cooldown.wait()
        if advance_stage is not None:
            advance_stage("attach")
        file_inputs = driver.find_elements(
            By.CSS_SELECTOR,
            ATTACHMENT_FILE_INPUT_SELECTOR,
        )
        if not file_inputs:
            _open_attachment_menu_selenium(
                driver,
                timeout_seconds=min(timeout_seconds, 30),
            )
            file_inputs = driver.find_elements(
                By.CSS_SELECTOR,
                ATTACHMENT_FILE_INPUT_SELECTOR,
            )
        if not file_inputs:
            raise RuntimeError("chatgpt_attachment_control_not_found")
        driver.execute_script("arguments[0].value = '';", file_inputs[0])
        file_inputs[0].send_keys(
            "\n".join(str(path.resolve()) for path in attachment_paths)
        )
        if advance_stage is not None:
            advance_stage("confirm_attachments")
        try:
            _wait_for_selenium_attachment_chips(
                driver,
                filenames,
                timeout_seconds=(
                    timeout_seconds
                    if confirmation_retry == 0
                    else min(
                        timeout_seconds,
                        DEFAULT_ATTACHMENT_CONFIRMATION_RETRY_TIMEOUT_SECONDS,
                    )
                ),
            )
            return
        except _AttachmentUploadTemporarilyLimited as exc:
            if limit_retry >= DEFAULT_ATTACHMENT_LIMIT_RETRIES:
                raise RuntimeError(
                    "chatgpt_attachment_limit_persisted_after_"
                    f"{DEFAULT_ATTACHMENT_LIMIT_RETRIES + 1}_uploads"
                ) from exc
            limit_retry += 1
            resume_at = cooldown.trigger(exc.wait_seconds)
            if advance_stage is not None:
                advance_stage("attachment_limit_wait")
            print(
                "ChatGPT attachment limit detected; pausing all Web uploads "
                f"until {resume_at} before retrying the same ticker.",
                flush=True,
            )
            cooldown.wait()
        except RuntimeError as exc:
            if (
                "chatgpt_attachment_upload_not_confirmed" not in str(exc)
                or confirmation_retry >= DEFAULT_ATTACHMENT_CONFIRMATION_RETRIES
            ):
                raise
            confirmation_retry += 1
            if advance_stage is not None:
                advance_stage("attachment_confirmation_retry")
            print(
                "ChatGPT attachment confirmation was inconclusive; "
                "re-uploading once in the same chat before restarting the ticker.",
                flush=True,
            )
            time.sleep(DEFAULT_ATTACHMENT_CONFIRMATION_RETRY_WAIT_SECONDS)


def _wait_for_selenium_attachment_chips(
    driver: Any,
    filenames: tuple[str, ...],
    *,
    timeout_seconds: int,
) -> None:
    deadline = time.monotonic() + timeout_seconds
    missing = list(filenames)
    while time.monotonic() < deadline:
        attachment_wait_seconds = _selenium_attachment_limit_wait_seconds(driver)
        if attachment_wait_seconds is not None:
            raise _AttachmentUploadTemporarilyLimited(attachment_wait_seconds)
        _dismiss_duplicate_attachment_dialog_selenium(driver)
        missing = [
            name
            for name in filenames
            if not _selenium_attachment_chip_visible(driver, name)
        ]
        if not missing:
            # The duplicate warning can appear just after the existing chips render.
            time.sleep(0.25)
            _dismiss_duplicate_attachment_dialog_selenium(driver)
            return
        time.sleep(0.25)
    raise RuntimeError(
        "chatgpt_attachment_upload_not_confirmed: " + ", ".join(missing)
    )


def _selenium_ready_send_button(driver: Any) -> Any | None:
    from selenium.webdriver.common.by import By

    for button in driver.find_elements(By.CSS_SELECTOR, SEND_BUTTON_SELECTOR):
        try:
            if not button.is_displayed() or not button.is_enabled():
                continue
            if str(button.get_attribute("aria-disabled") or "").lower() == "true":
                continue
            if button.get_attribute("data-visually-disabled") is not None:
                continue
            return button
        except Exception:
            continue
    return None


def _selenium_composer_has_text(driver: Any) -> bool:
    composer = _visible_selenium_element(driver, PROMPT_SELECTOR)
    if composer is None:
        return False
    try:
        value = composer.get_attribute("value")
        text = value if value is not None else composer.get_attribute("textContent")
        return bool(_normalize_selenium_composer_text(text))
    except Exception:
        return False


def _wait_for_selenium_send_button_stable(
    driver: Any,
    *,
    timeout_seconds: int,
    stable_seconds: int,
) -> Any:
    deadline = time.monotonic() + timeout_seconds
    ready_since: float | None = None
    while time.monotonic() < deadline:
        button = _selenium_ready_send_button(driver)
        if button is None:
            ready_since = None
        else:
            now = time.monotonic()
            if ready_since is None:
                ready_since = now
            elif now - ready_since >= stable_seconds:
                return button
        time.sleep(0.5)
    raise RuntimeError("chatgpt_send_control_not_stable")


def _wait_for_selenium_request_started(
    driver: Any,
    *,
    initial_user_snapshot: tuple[int, str, str],
    initial_assistant_count: int,
    initial_assistant_snapshot: tuple[int, str, str] | None = None,
    initial_activity_snapshot: tuple[int, str, str] | None = None,
    timeout_seconds: int,
) -> bool:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        try:
            user_snapshot = _selenium_turn_snapshot(driver, USER_SELECTOR)
            assistant_snapshot = _selenium_assistant_snapshot(driver)
            activity_snapshot = _selenium_agent_activity_snapshot(driver)
            if _selenium_turn_changed(user_snapshot, initial_user_snapshot):
                return True
            if assistant_snapshot[0] > initial_assistant_count:
                return True
            if (
                initial_assistant_snapshot is not None
                and _selenium_turn_changed(
                    assistant_snapshot,
                    initial_assistant_snapshot,
                )
            ):
                return True
            if (
                initial_activity_snapshot is not None
                and _selenium_turn_changed(
                    activity_snapshot,
                    initial_activity_snapshot,
                )
            ):
                return True
            if _selenium_stop_button_visible(driver):
                return True
            if _selenium_latest_assistant_code_blocks(driver):
                return True
        except Exception as exc:
            if not _is_transient_selenium_poll_error(exc):
                raise
        time.sleep(0.5)
    return False


def _selenium_turn_snapshot(
    driver: Any,
    selector: str,
) -> tuple[int, str, str]:
    """Identify the newest matching turn despite list virtualization."""

    from selenium.webdriver.common.by import By

    turns = driver.find_elements(By.CSS_SELECTOR, selector)
    if not turns:
        return 0, "", ""
    last = turns[-1]
    try:
        element_id = str(getattr(last, "id", "") or "")
        text = str(last.text or "").strip()
    except Exception:
        return len(turns), "", ""
    return len(turns), element_id, text


def _selenium_turn_changed(
    current: tuple[int, str, str],
    initial: tuple[int, str, str],
) -> bool:
    if current[0] > initial[0]:
        return True
    return bool(
        current[2]
        and (current[1] != initial[1] or current[2] != initial[2])
    )


def _selenium_assistant_snapshot(driver: Any) -> tuple[int, str, str]:
    """Identify the last response even when ChatGPT virtualizes old turns."""

    return _selenium_turn_snapshot(driver, ASSISTANT_SELECTOR)


def _selenium_agent_activity_snapshot(driver: Any) -> tuple[int, str, str]:
    """Track Sol reasoning/tool activity before a final assistant turn exists."""

    from selenium.webdriver.common.by import By

    markers = driver.find_elements(By.CSS_SELECTOR, AGENT_ACTIVITY_SELECTOR)
    if not markers:
        return 0, "", ""
    last = markers[-1]
    try:
        element_id = str(getattr(last, "id", "") or "")
        text = str(
            driver.execute_script(
                "return arguments[0].parentElement?.innerText || '';",
                last,
            )
            or ""
        ).strip()
    except Exception:
        return len(markers), "", ""
    return len(markers), element_id, text


def _selenium_stop_button_visible(driver: Any) -> bool:
    from selenium.webdriver.common.by import By

    for element in driver.find_elements(By.CSS_SELECTOR, STOP_BUTTON_SELECTOR):
        try:
            if element.is_displayed() is True:
                return True
        except Exception:
            continue
    return False


def _selenium_latest_assistant_code_blocks(driver: Any) -> list[Any]:
    """Return code blocks from the newest assistant container that has one.

    ChatGPT's current markup nests an old ``data-message-author-role`` node
    inside the newer ``data-content-search-unit-key`` turn container.  A CSS
    union therefore returns both nodes and the last one can be an activity
    marker with no report, even though its parent contains the final Markdown.
    Walking backwards keeps legacy markup working while selecting the actual
    completed answer in the nested layout.
    """

    from selenium.webdriver.common.by import By

    responses = driver.find_elements(By.CSS_SELECTOR, ASSISTANT_SELECTOR)
    for response in reversed(responses):
        try:
            code_blocks = response.find_elements(
                By.CSS_SELECTOR,
                MARKDOWN_CODE_BLOCK_SELECTOR,
            )
        except Exception as exc:
            if _is_transient_selenium_poll_error(exc):
                continue
            raise
        if code_blocks:
            return code_blocks
    return []


def _selenium_new_assistant_visible(
    driver: Any,
    initial: tuple[int, str, str],
    *,
    initial_activity_snapshot: tuple[int, str, str] | None = None,
) -> bool:
    current = _selenium_assistant_snapshot(driver)
    if _selenium_turn_changed(current, initial):
        return True
    if initial_activity_snapshot is not None and _selenium_turn_changed(
        _selenium_agent_activity_snapshot(driver),
        initial_activity_snapshot,
    ):
        return True
    return _selenium_stop_button_visible(driver)


def _wait_for_selenium_new_assistant(
    driver: Any,
    initial: tuple[int, str, str],
    *,
    initial_activity_snapshot: tuple[int, str, str] | None = None,
    timeout_seconds: int,
) -> None:
    """Wait through harmless DOM replacements and transient Marionette reads."""

    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        try:
            if _selenium_new_assistant_visible(
                driver,
                initial,
                initial_activity_snapshot=initial_activity_snapshot,
            ):
                return
        except Exception as exc:
            if not _is_transient_selenium_poll_error(exc):
                raise
        time.sleep(1)
    raise RuntimeError("chatgpt_assistant_response_not_started")


def _open_attachment_menu_selenium(
    driver: Any,
    *,
    timeout_seconds: int = 10,
) -> None:
    from selenium.webdriver.common.by import By

    selectors = (
        'button[aria-label*="Attach"]',
        'button[aria-label*="adjuntar" i]',
        'button[aria-label*="añadir archivos" i]',
        'button[data-composer-navigation-target="add-context"]',
        'button[data-testid="composer-plus-btn"]',
    )
    deadline = time.monotonic() + timeout_seconds
    menu_clicked = False
    while time.monotonic() < deadline:
        try:
            if driver.find_elements(By.CSS_SELECTOR, ATTACHMENT_FILE_INPUT_SELECTOR):
                return
        except Exception as exc:
            if not _is_transient_selenium_poll_error(exc):
                raise
            time.sleep(0.25)
            continue

        # ChatGPT can expose the '+' button while the profile/chat is still
        # hydrating.  Clicking it schedules the file input asynchronously.  Do
        # not return merely because the click succeeded: wait until the input
        # is actually attached to the current DOM.
        if menu_clicked:
            time.sleep(0.25)
            continue

        for selector in selectors:
            try:
                buttons = driver.find_elements(By.CSS_SELECTOR, selector)
            except Exception as exc:
                if _is_transient_selenium_poll_error(exc):
                    continue
                raise
            for button in buttons:
                try:
                    if button.is_displayed():
                        button.click()
                        menu_clicked = True
                        break
                except Exception as exc:
                    if not _is_transient_selenium_poll_error(exc):
                        raise
            if menu_clicked:
                break
        time.sleep(0.25)
    raise RuntimeError("chatgpt_attachment_control_not_found")


def _wait_for_selenium_response_complete(
    driver: Any,
    *,
    timeout_seconds: int,
    inactivity_timeout_seconds: int,
) -> None:
    from selenium.webdriver.common.by import By

    deadline = time.monotonic() + timeout_seconds
    stable_count = 0
    previous = ""
    previous_status = ""
    last_activity_at = time.monotonic()
    while time.monotonic() < deadline:
        try:
            responses = driver.find_elements(By.CSS_SELECTOR, ASSISTANT_SELECTOR)
            response = responses[-1].text if responses else ""
            status_text = _selenium_live_status_text(driver)
            stop_visible = _selenium_stop_button_visible(driver)
        except Exception as exc:
            if not _is_transient_selenium_poll_error(exc):
                raise
            if time.monotonic() - last_activity_at >= inactivity_timeout_seconds:
                raise RuntimeError(
                    "chatgpt_response_stalled_after_selenium_poll_errors: "
                    f"type={type(exc).__name__}"
                ) from exc
            time.sleep(1)
            continue
        if response != previous or status_text != previous_status:
            last_activity_at = time.monotonic()

        if response and response == previous and not stop_visible:
            stable_count += 1
            if stable_count >= 3:
                return
        else:
            stable_count = 0
        previous = response
        previous_status = status_text
        inactive_seconds = time.monotonic() - last_activity_at
        if inactive_seconds >= inactivity_timeout_seconds and not stop_visible:
            raise RuntimeError(
                "chatgpt_response_stalled: "
                f"inactive_seconds={int(inactive_seconds)}; "
                f"response_chars={len(response)}; stop_visible={stop_visible}"
            )
        time.sleep(2)
    raise RuntimeError("chatgpt_response_timeout")


def _selenium_live_status_text(driver: Any) -> str:
    from selenium.webdriver.common.by import By

    values: list[str] = []
    for element in driver.find_elements(
        By.CSS_SELECTOR,
        '[role="status"], [aria-live="polite"]',
    ):
        try:
            if element.is_displayed() and element.text.strip():
                values.append(element.text.strip())
        except Exception:
            continue
    return "\n".join(values)


def _safe_selenium_current_url(driver: Any) -> str:
    try:
        return str(driver.current_url or "")
    except Exception:
        return ""


def _write_selenium_trace(
    driver: Any,
    *,
    diagnostic_dir: Path,
    symbol: str,
    attempt: int,
    status: str,
    stage: str,
    stage_timings: dict[str, float],
    error: Exception | None = None,
    capture_page: bool = False,
) -> Path:
    diagnostic_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    safe_symbol = re.sub(r"[^A-Za-z0-9_.-]+", "_", symbol).strip("_") or "ticker"
    base = diagnostic_dir / f"{stamp}-{safe_symbol}-attempt-{attempt}"
    capture_errors: list[str] = []
    screenshot_path: Path | None = None
    html_path: Path | None = None
    visible_text_path: Path | None = None

    if capture_page:
        screenshot_path = base.with_suffix(".png")
        try:
            driver.save_screenshot(str(screenshot_path))
        except Exception as exc:
            screenshot_path = None
            capture_errors.append(f"screenshot:{type(exc).__name__}:{exc}")

        html_path = base.with_suffix(".html")
        try:
            html_path.write_text(str(driver.page_source or ""), encoding="utf-8")
        except Exception as exc:
            html_path = None
            capture_errors.append(f"html:{type(exc).__name__}:{exc}")

        visible_text_path = base.with_suffix(".txt")
        try:
            visible_text = driver.execute_script(
                "return document.body ? document.body.innerText : '';"
            )
            visible_text_path.write_text(
                str(visible_text or "")[:200_000],
                encoding="utf-8",
            )
        except Exception as exc:
            visible_text_path = None
            capture_errors.append(f"visible_text:{type(exc).__name__}:{exc}")

    metadata_path = base.with_suffix(".json")
    payload = {
        "status": status,
        "symbol": symbol,
        "attempt": attempt,
        "stage": stage,
        "url": _safe_selenium_current_url(driver),
        "captured_at": _utc_now().isoformat(),
        "stage_timings_seconds": stage_timings,
        "error_type": type(error).__name__ if error is not None else None,
        "error_message": (str(error).strip() or "<empty>") if error is not None else None,
        "screenshot_path": str(screenshot_path) if screenshot_path else None,
        "html_path": str(html_path) if html_path else None,
        "visible_text_path": str(visible_text_path) if visible_text_path else None,
        "capture_errors": capture_errors,
        "cloudflare_api_challenges": _blocked_browser_api_paths(driver),
        "account_api_events": _browser_access_events(driver),
        "account_reload_attempts": (
            driver._analysis_account_reloads
            if isinstance(getattr(driver, "_analysis_account_reloads", None), list)
            else []
        ),
    }
    metadata_path.write_text(
        json.dumps(payload, ensure_ascii=True, indent=2) + "\n",
        encoding="utf-8",
    )
    return metadata_path


def _write_browser_timeline_event(
    *,
    diagnostic_dir: Path,
    symbol: str,
    attempt: int,
    stage: str,
    status: str,
    stage_timings: dict[str, float],
    error: Exception | None = None,
) -> None:
    """Persist each browser transition for live and post-run diagnosis."""

    diagnostic_dir.mkdir(parents=True, exist_ok=True)
    captured_at = _utc_now().isoformat()
    payload = {
        "captured_at": captured_at,
        "symbol": symbol,
        "attempt": attempt,
        "stage": stage,
        "status": status,
        "stage_timings_seconds": stage_timings,
        "error_type": type(error).__name__ if error is not None else None,
        "error_message": (
            (str(error).strip() or "<empty>") if error is not None else None
        ),
    }
    latest_path = diagnostic_dir / "current.json"
    temporary = latest_path.with_suffix(".json.tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=True, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(latest_path)
    timeline_path = diagnostic_dir / "timeline.jsonl"
    with timeline_path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(payload, ensure_ascii=True) + "\n")


def _stage_unique_request_attachments(
    attachment_paths: tuple[Path, ...],
    *,
    diagnostic_dir: Path,
    symbol: str,
    attempt: int,
) -> tuple[Path, ...]:
    """Give each grouped-chat upload a unique name and retain it as evidence."""

    if not attachment_paths:
        return ()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    safe_symbol = re.sub(r"[^A-Za-z0-9_.-]+", "_", symbol).strip("_") or "ticker"
    staged_dir = diagnostic_dir / "request_attachments"
    staged_dir.mkdir(parents=True, exist_ok=True)
    staged: list[Path] = []
    for source in attachment_paths:
        destination = staged_dir / (
            f"{source.stem}__{safe_symbol}__attempt-{attempt}__{stamp}{source.suffix}"
        )
        shutil.copy2(source, destination)
        staged.append(destination)
    return tuple(staged)


def _ensure_authenticated(page: Any, *, timeout_seconds: int) -> None:
    timeout_ms = timeout_seconds * 1000
    page.goto(CHATGPT_URL, wait_until="domcontentloaded", timeout=timeout_ms)
    if _prompt_visible(page):
        return

    credentials = get_stored_credentials()
    if credentials is None:
        raise RuntimeError(
            "chatgpt_credentials_missing: run credentials set or login once visibly"
        )
    email, password = credentials

    _click_first_named(page, ("Log in", "Iniciar sesion", "Iniciar sesión"))
    email_input = page.locator('input[type="email"], input[name="email"]').first
    email_input.wait_for(state="visible", timeout=timeout_ms)
    email_input.fill(email)
    _click_first_named(page, ("Continue", "Continuar"))

    password_input = page.locator('input[type="password"]').first
    password_input.wait_for(state="visible", timeout=timeout_ms)
    password_input.fill(password)
    _click_first_named(page, ("Continue", "Continuar", "Log in", "Iniciar sesion", "Iniciar sesión"))

    try:
        _wait_for_prompt(page, timeout_seconds)
    except RuntimeError as exc:
        raise RuntimeError(
            "chatgpt_login_challenge: automatic credential login did not reach ChatGPT"
        ) from exc


def _resolve_project_url_playwright(page: Any, *, cwd: Path) -> str:
    stored = _stored_project_url(cwd)
    if stored:
        return stored

    project_name = _project_name()
    links = page.get_by_role("link", name=project_name, exact=True)
    for index in range(links.count()):
        link = links.nth(index)
        if not link.is_visible():
            continue
        href = str(link.get_attribute("href") or "").strip()
        if _valid_project_url(href):
            if href.startswith("/"):
                href = f"https://chatgpt.com{href}"
            return _save_project_url(cwd, href)
    raise RuntimeError(f"chatgpt_project_not_found: {project_name}")


def _wait_for_project_context_playwright(
    page: Any,
    *,
    project_url: str,
    timeout_seconds: int,
) -> None:
    expected = _normalize_chatgpt_ui_label(_project_name())
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        labels = page.locator("[aria-label]")
        for index in range(labels.count()):
            element = labels.nth(index)
            try:
                if not element.is_visible():
                    continue
                label = _normalize_chatgpt_ui_label(
                    element.get_attribute("aria-label")
                )
            except Exception:
                continue
            if expected in label and label.startswith(
                (
                    "cambiar proyecto:",
                    "switch project:",
                    "nuevo chat en ",
                    "new chat in ",
                )
            ):
                return
        page.wait_for_timeout(250)
    raise RuntimeError(
        f"chatgpt_project_context_not_confirmed: {_project_name()}"
    )


def _project_name() -> str:
    return os.environ.get("CHATGPT_PROJECT_NAME", DEFAULT_PROJECT_NAME).strip()


def _project_url_path(cwd: Path) -> Path:
    configured = os.environ.get("CHATGPT_PROJECT_URL_FILE")
    return Path(configured).expanduser() if configured else cwd / DEFAULT_PROJECT_URL_PATH


def _stored_project_url(cwd: Path) -> str | None:
    configured = os.environ.get("CHATGPT_PROJECT_URL", "").strip()
    if configured:
        if not _valid_project_url(configured):
            raise RuntimeError("chatgpt_project_url_invalid")
        return configured
    path = _project_url_path(cwd)
    if not path.exists():
        return None
    value = path.read_text(encoding="utf-8").strip()
    if not _valid_project_url(value):
        raise RuntimeError("chatgpt_project_url_invalid")
    return value


def _save_project_url(cwd: Path, url: str) -> str:
    path = _project_url_path(cwd)
    path.parent.mkdir(parents=True, exist_ok=True)
    _atomic_write_text(path, url.strip() + "\n")
    return url.strip()


def _valid_project_url(url: str) -> bool:
    return url.startswith("https://chatgpt.com/") and (
        "/project" in url or "/g/" in url
    )


def _open_attachment_menu(page: Any, *, timeout_seconds: int = 10) -> None:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        file_input = page.locator(ATTACHMENT_FILE_INPUT_SELECTOR).first
        if file_input.count():
            return
        for selector in (
            'button[aria-label*="Attach"]',
            'button[aria-label*="adjuntar" i]',
            'button[aria-label*="añadir archivos" i]',
            'button[data-composer-navigation-target="add-context"]',
            'button[data-testid="composer-plus-btn"]',
        ):
            button = page.locator(selector).first
            if button.count() and button.is_visible():
                button.click()
                page.locator(ATTACHMENT_FILE_INPUT_SELECTOR).first.wait_for(
                    state="attached",
                    timeout=min(10_000, max(1, int(timeout_seconds * 1000))),
                )
                return
        page.wait_for_timeout(250)
    raise RuntimeError("chatgpt_attachment_control_not_found")


def _wait_for_response_complete(page: Any, *, timeout_seconds: int) -> None:
    deadline = time.monotonic() + timeout_seconds
    stable_count = 0
    previous = ""
    while time.monotonic() < deadline:
        responses = page.locator(ASSISTANT_SELECTOR)
        response = (
            responses.last.inner_text(timeout=10_000)
            if responses.count()
            else ""
        )
        stop_visible = page.locator(
            STOP_BUTTON_SELECTOR
        ).count() > 0
        if response and response == previous and not stop_visible:
            stable_count += 1
            if stable_count >= 3:
                return
        else:
            stable_count = 0
        previous = response
        page.wait_for_timeout(2_000)
    raise RuntimeError("chatgpt_response_timeout")


def _wait_for_prompt(page: Any, timeout_seconds: int) -> None:
    try:
        page.locator(PROMPT_SELECTOR).wait_for(
            state="visible", timeout=timeout_seconds * 1000
        )
    except Exception as exc:
        raise RuntimeError("chatgpt_prompt_not_available") from exc


def _prompt_visible(page: Any) -> bool:
    prompt = page.locator(PROMPT_SELECTOR)
    return bool(prompt.count() and prompt.first.is_visible())


def _click_first_named(page: Any, names: tuple[str, ...]) -> None:
    for name in names:
        button = page.get_by_role("button", name=name, exact=True)
        if button.count() and button.first.is_visible():
            button.first.click()
            return
        link = page.get_by_role("link", name=name, exact=True)
        if link.count() and link.first.is_visible():
            link.first.click()
            return
    raise RuntimeError(f"chatgpt_login_control_not_found: {names[0]}")


def _browser_executable() -> str:
    configured = os.environ.get("CHATGPT_BROWSER_EXECUTABLE")
    if configured:
        path = Path(configured).expanduser()
        if path.exists():
            return str(path)
        raise RuntimeError(f"chatgpt_browser_executable_not_found: {path}")

    candidates = (
        Path(os.environ.get("PROGRAMFILES(X86)", ""))
        / "Google/Chrome/Application/chrome.exe",
        Path(os.environ.get("PROGRAMFILES", ""))
        / "Google/Chrome/Application/chrome.exe",
        Path(os.environ.get("PROGRAMFILES(X86)", ""))
        / "Microsoft/Edge/Application/msedge.exe",
        Path(os.environ.get("PROGRAMFILES", ""))
        / "Microsoft/Edge/Application/msedge.exe",
    )
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    raise RuntimeError("chatgpt_browser_executable_not_found")


def _firefox_executable() -> str:
    configured = os.environ.get("CHATGPT_FIREFOX_EXECUTABLE")
    if configured:
        path = Path(configured).expanduser()
        if path.exists():
            return str(path)
        raise RuntimeError(f"chatgpt_firefox_executable_not_found: {path}")

    candidates = (
        Path(os.environ.get("PROGRAMFILES", "")) / "Mozilla Firefox/firefox.exe",
        Path(os.environ.get("PROGRAMFILES(X86)", ""))
        / "Mozilla Firefox/firefox.exe",
    )
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    raise RuntimeError("chatgpt_firefox_executable_not_found")


def _browser_engine(configured: str | None = None) -> str:
    engine = str(
        configured or os.environ.get("CHATGPT_BROWSER_ENGINE") or "firefox"
    ).strip().lower()
    if engine not in {"firefox", "chromium"}:
        raise RuntimeError(f"chatgpt_browser_engine_invalid: {engine}")
    return engine


def _configured_timeout_seconds(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise RuntimeError(f"{name.lower()}_invalid: {raw}") from exc
    if value < 1:
        raise RuntimeError(f"{name.lower()}_must_be_positive")
    return value


def _profile_dir(cwd: Path, *, engine: str, worker_id: int = 1) -> Path:
    if worker_id < 1:
        raise ValueError("worker_id_must_be_positive")
    base_env_name = (
        "CHATGPT_FIREFOX_PROFILE_DIR"
        if engine == "firefox"
        else "CHATGPT_BROWSER_PROFILE_DIR"
    )
    worker_env_name = f"{base_env_name}_WORKER_{worker_id}"
    configured = os.environ.get(worker_env_name) or os.environ.get(base_env_name)
    default_path = (
        DEFAULT_FIREFOX_PROFILE_PATH
        if engine == "firefox"
        else DEFAULT_PROFILE_PATH
    )
    path = Path(configured).expanduser() if configured else cwd / default_path
    if worker_id > 1 and not os.environ.get(worker_env_name):
        path = path.with_name(f"{path.name}-worker-{worker_id}")
    if worker_id > 1 and not path.exists():
        primary = _profile_dir(cwd, engine=engine, worker_id=1)
        if any(primary.iterdir()):
            shutil.copytree(
                primary,
                path,
                ignore=_ignore_browser_profile_runtime_files,
            )
    path.mkdir(parents=True, exist_ok=True)
    return path.resolve()


def _ignore_browser_profile_runtime_files(
    _directory: str,
    names: list[str],
) -> set[str]:
    runtime_names = {
        ".parentlock",
        "lock",
        "parent.lock",
        "SingletonCookie",
        "SingletonLock",
        "SingletonSocket",
    }
    return {name for name in names if name in runtime_names}


def _clear_firefox_profile_runtime_locks(profile_dir: Path) -> None:
    """Remove Firefox lock files after the owning automation process has ended."""

    for name in ("parent.lock", "lock", ".parentlock"):
        path = profile_dir / name
        try:
            path.unlink(missing_ok=True)
        except OSError as exc:
            print(
                f"WARNING: unable to clear stale Firefox profile lock {path}: {exc}",
                flush=True,
            )


def _lock_path(cwd: Path, *, worker_id: int = 1) -> Path:
    if worker_id < 1:
        raise ValueError("worker_id_must_be_positive")
    worker_env_name = f"CHATGPT_BROWSER_LOCK_PATH_WORKER_{worker_id}"
    configured = os.environ.get(worker_env_name) or os.environ.get(
        "CHATGPT_BROWSER_LOCK_PATH"
    )
    path = Path(configured).expanduser() if configured else cwd / DEFAULT_LOCK_PATH
    if worker_id > 1 and not os.environ.get(worker_env_name):
        path = path.with_name(f"{path.stem}-worker-{worker_id}{path.suffix}")
    path.parent.mkdir(parents=True, exist_ok=True)
    return path.resolve()


@contextmanager
def _exclusive_browser_lock(lock_path: Path, *, timeout_seconds: int) -> Iterator[bool]:
    deadline = time.monotonic() + timeout_seconds
    recovered_stale_lock = False
    while True:
        try:
            fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump({"pid": os.getpid(), "created_at": _utc_now().isoformat()}, handle)
            break
        except FileExistsError:
            if _remove_stale_lock(lock_path):
                recovered_stale_lock = True
                continue
            if time.monotonic() >= deadline:
                raise RuntimeError("chatgpt_browser_lock_timeout")
            time.sleep(2)
    try:
        yield recovered_stale_lock
    finally:
        _release_lock(lock_path)


def _stop_orphaned_firefox_profile_processes(
    profile_dir: Path,
    *,
    include_manual: bool = False,
) -> None:
    """Stop Firefox descendants left behind after their lock owner died."""

    if os.name != "nt":
        return
    profile = str(profile_dir.resolve()).replace("'", "''")
    launch_filter = "" if include_manual else "-and $_.CommandLine -like '*--marionette*'"
    script = (
        "$all=@(Get-CimInstance Win32_Process);"
        f"$profile='{profile}';"
        "$roots=@($all | Where-Object {"
        "$_.Name -ieq 'firefox.exe' -and "
        "$_.CommandLine -like ('*' + $profile + '*') -and "
        f"$true {launch_filter}}});"
        "if($roots.Count -eq 0){exit 0};"
        "$ids=@($roots | Select-Object -ExpandProperty ProcessId);"
        "$front=@($ids);"
        "while($front.Count -gt 0){"
        "$next=@($all | Where-Object {$front -contains $_.ParentProcessId} | "
        "Select-Object -ExpandProperty ProcessId);"
        "$ids+=@($next);$front=@($next)};"
        "$parents=@($all | Where-Object {"
        "$ids -contains $_.ProcessId} | Select-Object -ExpandProperty ParentProcessId);"
        "$ids+=@($all | Where-Object {"
        "$_.Name -ieq 'geckodriver.exe' -and $parents -contains $_.ProcessId} | "
        "Select-Object -ExpandProperty ProcessId);"
        "$ids=@($ids | Sort-Object -Unique -Descending);"
        "Stop-Process -Id $ids -Force -ErrorAction SilentlyContinue;"
        "Write-Output $ids.Count"
    )
    try:
        completed = subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=subprocess.CREATE_NO_WINDOW,
            timeout=30,
        )
    except subprocess.TimeoutExpired:
        # WMI can become very slow while several Firefox trees are shutting down.
        # Cleanup is best-effort and must never abort a new analysis before launch.
        print(
            "WARNING: orphan ChatGPT Firefox cleanup timed out; continuing launch.",
            flush=True,
        )
        return
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout).strip()
        print(
            "WARNING: orphan ChatGPT Firefox cleanup failed: "
            + (detail[:240] or f"exit_code={completed.returncode}"),
            flush=True,
        )
        return
    if completed.stdout.strip() not in {"", "0"}:
        print(
            "Recovered orphaned ChatGPT Firefox processes before relaunch.",
            flush=True,
        )


def _release_lock(lock_path: Path) -> None:
    """Best-effort release; Windows readers can briefly deny deletion."""
    for attempt in range(10):
        try:
            lock_path.unlink()
            return
        except FileNotFoundError:
            return
        except OSError:
            if attempt < 9:
                time.sleep(0.1)


def _remove_stale_lock(lock_path: Path) -> bool:
    try:
        payload = json.loads(lock_path.read_text(encoding="utf-8"))
        pid = int(payload.get("pid"))
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        try:
            age = time.time() - lock_path.stat().st_mtime
        except FileNotFoundError:
            return True
        if age < DEFAULT_LOCK_INITIALIZATION_GRACE_SECONDS:
            return False
        pid = -1
    if pid > 0 and _process_exists(pid):
        return False
    try:
        lock_path.unlink()
        return True
    except OSError:
        return False


def _process_exists(pid: int) -> bool:
    if os.name == "nt":
        process_query_limited_information = 0x1000
        still_active = 259
        handle = ctypes.windll.kernel32.OpenProcess(
            process_query_limited_information,
            False,
            pid,
        )
        if not handle:
            return False
        try:
            exit_code = ctypes.c_ulong()
            if not ctypes.windll.kernel32.GetExitCodeProcess(
                handle,
                ctypes.byref(exit_code),
            ):
                return False
            return exit_code.value == still_active
        finally:
            ctypes.windll.kernel32.CloseHandle(handle)

    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _attempt_record(
    attempt: int,
    started_at: datetime,
    chat_url: str,
    candidate_path: Path,
    errors: tuple[str, ...],
    *,
    sanitized_markers: int = 0,
) -> dict[str, Any]:
    return {
        "attempt": attempt,
        "started_at": started_at.isoformat(),
        "finished_at": _utc_now().isoformat(),
        "chat_url": chat_url,
        "candidate_path": str(candidate_path),
        "status": "failed" if errors else "ok",
        "errors": list(errors),
        "sanitized_internal_citation_markers": sanitized_markers,
    }


def _atomic_write_text(path: Path, content: str) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(content, encoding="utf-8")
    os.replace(temporary, path)


def _write_metadata(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _require_keyring() -> Any:
    try:
        import keyring
    except ImportError as exc:
        raise RuntimeError(
            "chatgpt_credential_dependency_missing: install requirements.txt"
        ) from exc
    return keyring


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_cli(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Manage the ChatGPT browser session.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    credentials = subparsers.add_parser("credentials")
    credential_actions = credentials.add_subparsers(dest="action", required=True)
    credential_actions.add_parser("set")
    credential_actions.add_parser("status")
    credential_actions.add_parser("delete")
    login = subparsers.add_parser("login")
    login.add_argument(
        "--browser",
        choices=("firefox", "chromium"),
        default="firefox",
    )
    login.add_argument(
        "--worker-id",
        type=int,
        choices=(1, 2, 3),
        default=1,
        help="Dedicated browser profile to authenticate manually.",
    )
    cleanup = subparsers.add_parser("cleanup")
    cleanup.add_argument(
        "--browser",
        choices=("firefox", "chromium"),
        default="firefox",
    )
    cleanup.add_argument(
        "--delay-seconds",
        type=int,
        default=DEFAULT_CLEANUP_DELAY_SECONDS,
    )
    cleanup.add_argument("--max-chats", type=int)
    cleanup.add_argument(
        "--min-age-seconds",
        type=int,
        default=DEFAULT_CLEANUP_MIN_AGE_SECONDS,
    )
    cleanup.add_argument("--headed", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_cli(argv)
    if args.command == "credentials":
        if args.action == "set":
            email = input("ChatGPT email: ").strip()
            password = getpass.getpass("ChatGPT password: ")
            set_stored_credentials(email, password)
            print("ChatGPT credentials stored in Windows Credential Manager.")
            return 0
        if args.action == "status":
            print("configured" if get_stored_credentials() else "not configured")
            return 0
        delete_stored_credentials()
        print("ChatGPT credentials removed from Windows Credential Manager.")
        return 0

    repo_root = Path.cwd().resolve()
    if args.command == "cleanup":
        result = cleanup_queued_chats(
            repo_root,
            headed=args.headed,
            browser_engine=args.browser,
            delay_seconds=args.delay_seconds,
            max_chats=args.max_chats,
            min_age_seconds=args.min_age_seconds,
        )
        print(json.dumps(result, ensure_ascii=False))
        return 0 if result["failed"] == 0 else 1

    engine = _browser_engine(args.browser)
    profile_dir = _profile_dir(repo_root, engine=engine, worker_id=args.worker_id)
    if engine == "firefox":
        command = [
            _firefox_executable(),
            "-no-remote",
            "-profile",
            str(profile_dir),
            CHATGPT_URL,
        ]
    else:
        command = [
            _browser_executable(),
            f"--user-data-dir={profile_dir}",
            "--disable-background-mode",
            # This legacy dedicated profile may contain synced extensions.
            # Suppress their startup pages and browser sync for this process;
            # do not uninstall extensions or alter the personal Chrome profile.
            "--disable-extensions",
            "--disable-sync",
            "--no-first-run",
            CHATGPT_URL,
        ]
    # Manual verification must use the same profile as the chosen worker, but
    # never at the same time as an automated run using that profile.
    with _exclusive_browser_lock(
        _lock_path(repo_root, worker_id=args.worker_id), timeout_seconds=0,
    ):
        completed = subprocess.run(command, check=False)
    if completed.returncode != 0:
        raise RuntimeError(
            f"chatgpt_manual_login_browser_failed: exit_code={completed.returncode}"
        )
    print(
        f"Manual browser for worker {args.worker_id} launched; "
        "close it before an automated run. Its profile persists between runs."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
