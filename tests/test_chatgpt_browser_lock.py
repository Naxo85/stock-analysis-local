from __future__ import annotations

import json
import os
import concurrent.futures
import threading
import time
import unittest
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch

from src.local_runner import chatgpt_browser_generator


class ChatGPTBrowserLockTests(unittest.TestCase):
    def test_prompt_selector_accepts_current_contenteditable_composer(self) -> None:
        self.assertIn(
            'div[contenteditable="true"][role="textbox"][data-composer-markdown]',
            chatgpt_browser_generator.PROMPT_SELECTOR,
        )

    def test_attachment_selector_accepts_current_dynamic_file_input(self) -> None:
        self.assertIn(
            'input[type="file"][aria-label*="archivos" i]',
            chatgpt_browser_generator.ATTACHMENT_FILE_INPUT_SELECTOR,
        )

    def test_send_selector_accepts_current_spanish_submit_button(self) -> None:
        self.assertIn(
            'button[type="submit"][aria-label="Enviar"]',
            chatgpt_browser_generator.SEND_BUTTON_SELECTOR,
        )

    def test_turn_selectors_accept_current_chatgpt_markup(self) -> None:
        self.assertIn(
            '[data-content-search-unit-key$=":user"]',
            chatgpt_browser_generator.USER_SELECTOR,
        )
        self.assertIn(
            '[data-content-search-unit-key$=":assistant"]',
            chatgpt_browser_generator.ASSISTANT_SELECTOR,
        )
        self.assertIn(
            '[data-markdown-copy="code-block"] code',
            chatgpt_browser_generator.MARKDOWN_CODE_BLOCK_SELECTOR,
        )

    def test_latest_assistant_code_blocks_skips_nested_marker_without_code(self) -> None:
        report_block = Mock()
        outer_turn = Mock()
        inner_marker = Mock()
        outer_turn.find_elements.return_value = [report_block]
        inner_marker.find_elements.return_value = []
        driver = Mock()
        driver.find_elements.return_value = [outer_turn, inner_marker]

        blocks = chatgpt_browser_generator._selenium_latest_assistant_code_blocks(
            driver
        )

        self.assertEqual(blocks, [report_block])

    def test_latest_assistant_code_blocks_prefers_newest_completed_turn(self) -> None:
        old_block = Mock()
        new_block = Mock()
        old_turn = Mock()
        new_turn = Mock()
        old_turn.find_elements.return_value = [old_block]
        new_turn.find_elements.return_value = [new_block]
        driver = Mock()
        driver.find_elements.return_value = [old_turn, new_turn]

        blocks = chatgpt_browser_generator._selenium_latest_assistant_code_blocks(
            driver
        )

        self.assertEqual(blocks, [new_block])

    def test_reasoning_trigger_accepts_current_chatgpt_data_hooks(self) -> None:
        trigger = Mock()
        trigger.text = "Esfuerzo de razonamiento"
        trigger.is_displayed.return_value = True
        trigger.get_attribute.side_effect = {
            "data-selected-reasoning-effort": "medium",
            "data-codex-intelligence-trigger": "true",
            "data-composer-navigation-target": "reasoning",
        }.get

        self.assertTrue(
            chatgpt_browser_generator._is_selenium_reasoning_trigger(trigger)
        )

    def test_reasoning_high_uses_current_chatgpt_data_attribute(self) -> None:
        trigger = Mock()
        trigger.text = "Esfuerzo de razonamiento"
        trigger.get_attribute.side_effect = {
            "data-selected-reasoning-effort": "high",
        }.get

        self.assertTrue(
            chatgpt_browser_generator._selenium_reasoning_effort_is_high(trigger)
        )

    def test_orphan_cleanup_timeout_does_not_abort_browser_launch(self) -> None:
        with patch.object(
            chatgpt_browser_generator.os,
            "name",
            "nt",
        ), patch.object(
            chatgpt_browser_generator.subprocess,
            "run",
            side_effect=chatgpt_browser_generator.subprocess.TimeoutExpired(
                "powershell.exe",
                30,
            ),
        ), patch("builtins.print") as warning:
            chatgpt_browser_generator._stop_orphaned_firefox_profile_processes(
                Path("profile")
            )

        warning.assert_called_once_with(
            "WARNING: orphan ChatGPT Firefox cleanup timed out; continuing launch.",
            flush=True,
        )

    def test_discarded_window_is_a_transient_firefox_launch_error(self) -> None:
        self.assertTrue(
            chatgpt_browser_generator._is_transient_firefox_launch_error(
                RuntimeError("Browsing context has been discarded")
            )
        )

    def test_firefox_launch_closes_discarded_session_before_retry(self) -> None:
        driver = Mock()
        driver.set_window_size.side_effect = RuntimeError(
            "Browsing context has been discarded"
        )
        webdriver = Mock()
        webdriver.Firefox.return_value = driver
        options = Mock()
        with patch.dict(
            "sys.modules",
            {
                "selenium": Mock(webdriver=webdriver),
                "selenium.webdriver": webdriver,
                "selenium.webdriver.firefox.options": Mock(
                    Options=Mock(return_value=options)
                ),
            },
        ), patch.object(
            chatgpt_browser_generator,
            "_firefox_executable",
            return_value="firefox.exe",
        ):
            with self.assertRaisesRegex(
                RuntimeError,
                "chatgpt_firefox_launch_failed",
            ):
                chatgpt_browser_generator._launch_firefox(
                    Path("profile"),
                    headed=False,
                )

        driver.quit.assert_called_once_with()

    def test_windows_background_firefox_uses_hidden_native_window(self) -> None:
        driver = Mock()
        webdriver = Mock()
        webdriver.Firefox.return_value = driver
        options = Mock()
        with patch.dict(
            "sys.modules",
            {
                "selenium": Mock(webdriver=webdriver),
                "selenium.webdriver": webdriver,
                "selenium.webdriver.firefox.options": Mock(
                    Options=Mock(return_value=options)
                ),
            },
        ), patch.object(
            chatgpt_browser_generator.os,
            "name",
            "nt",
        ), patch.object(
            chatgpt_browser_generator,
            "_firefox_executable",
            return_value="firefox.exe",
        ), patch.object(
            chatgpt_browser_generator,
            "_hide_selenium_firefox_window",
            return_value=True,
        ) as hide:
            result = chatgpt_browser_generator._launch_firefox(
                Path("profile"),
                headed=False,
            )

        self.assertIs(result, driver)
        self.assertNotIn(
            unittest.mock.call("-headless"),
            options.add_argument.call_args_list,
        )
        hide.assert_called_once_with(driver)
        driver.minimize_window.assert_not_called()

    def test_headless_discarded_context_falls_back_to_minimized_firefox(self) -> None:
        driver = Mock()
        discarded = RuntimeError(
            "chatgpt_firefox_launch_failed: Browsing context has been discarded"
        )
        with patch.object(
            chatgpt_browser_generator,
            "_launch_firefox",
            side_effect=(discarded, driver),
        ) as launch, patch.object(
            chatgpt_browser_generator,
            "_stop_orphaned_firefox_profile_processes",
        ) as cleanup, patch.object(
            chatgpt_browser_generator.time,
            "sleep",
        ) as sleep, patch(
            "builtins.print"
        ) as warning:
            result = chatgpt_browser_generator._launch_firefox_with_retries(
                Path("profile"),
                headed=False,
            )

        self.assertIs(result, driver)
        self.assertEqual(
            [call.kwargs["headed"] for call in launch.call_args_list],
            [False, True],
        )
        cleanup.assert_called_once_with(Path("profile"), include_manual=True)
        sleep.assert_called_once_with(
            chatgpt_browser_generator.DEFAULT_TRANSIENT_OPEN_BACKOFF_SECONDS
        )
        driver.minimize_window.assert_called_once_with()
        warning.assert_called_once_with(
            "WARNING: Firefox headless is unavailable; using an isolated "
            "minimized window.",
            flush=True,
        )

    def test_firefox_runtime_lock_cleanup_preserves_profile_data(self) -> None:
        with TemporaryDirectory() as temporary:
            profile = Path(temporary)
            for name in ("parent.lock", "lock", ".parentlock"):
                (profile / name).write_text("stale", encoding="utf-8")
            cookie_store = profile / "cookies.sqlite"
            cookie_store.write_text("session", encoding="utf-8")

            chatgpt_browser_generator._clear_firefox_profile_runtime_locks(profile)

            for name in ("parent.lock", "lock", ".parentlock"):
                self.assertFalse((profile / name).exists())
            self.assertEqual(cookie_store.read_text(encoding="utf-8"), "session")

    def test_second_worker_uses_a_distinct_cloned_profile_and_lock(self) -> None:
        with TemporaryDirectory() as temporary, patch.dict(
            os.environ,
            {
                "CHATGPT_FIREFOX_PROFILE_DIR": "",
                "CHATGPT_FIREFOX_PROFILE_DIR_WORKER_1": "",
                "CHATGPT_FIREFOX_PROFILE_DIR_WORKER_2": "",
                "CHATGPT_BROWSER_LOCK_PATH": "",
                "CHATGPT_BROWSER_LOCK_PATH_WORKER_1": "",
                "CHATGPT_BROWSER_LOCK_PATH_WORKER_2": "",
            },
        ):
            root = Path(temporary)
            primary = chatgpt_browser_generator._profile_dir(
                root, engine="firefox", worker_id=1
            )
            (primary / "cookies.sqlite").write_text("session", encoding="utf-8")
            (primary / "parent.lock").write_text("runtime", encoding="utf-8")

            secondary = chatgpt_browser_generator._profile_dir(
                root, engine="firefox", worker_id=2
            )

            self.assertNotEqual(primary, secondary)
            self.assertEqual(
                (secondary / "cookies.sqlite").read_text(encoding="utf-8"),
                "session",
            )
            self.assertFalse((secondary / "parent.lock").exists())
            self.assertNotEqual(
                chatgpt_browser_generator._lock_path(root, worker_id=1),
                chatgpt_browser_generator._lock_path(root, worker_id=2),
            )

    def test_pool_leases_two_sessions_concurrently(self) -> None:
        class FakeSession:
            def __init__(self, root: Path, worker_id: int, barrier: threading.Barrier):
                self.cwd = root.resolve()
                self.engine = "firefox"
                self.worker_id = worker_id
                self.chat_group_size = 5
                self.barrier = barrier

            @contextmanager
            def generation(self, symbol: str = ""):
                self.barrier.wait(timeout=2)
                yield self

            def generation_timing(self, symbol: str):
                return {"queue_wait_seconds": 0.0, "execution_seconds": 0.1}

            def progress_status(self):
                return {
                    "worker_id": self.worker_id,
                    "chat_group_size": 5,
                    "chat_group_tickers": 0,
                    "rate_limit_count": 0,
                    "rate_limit_waiting": False,
                    "active_ticker": "",
                    "waiting_tickers": [],
                }

            def close(self):
                return None

        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            barrier = threading.Barrier(2)
            sessions = tuple(
                FakeSession(root, worker_id, barrier) for worker_id in (1, 2)
            )
            pool = chatgpt_browser_generator.ChatGPTBrowserSessionPool(
                root,
                worker_count=2,
                browser_engine="firefox",
                sessions=sessions,
            )
            leased_workers: list[int] = []
            leased_lock = threading.Lock()

            def generate(symbol: str) -> None:
                with pool.generation(symbol):
                    with leased_lock:
                        leased_workers.append(pool.current_worker_id())
                    time.sleep(0.05)

            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
                futures = [executor.submit(generate, symbol) for symbol in ("AAA", "BBB")]
                for future in futures:
                    future.result(timeout=3)

            self.assertEqual(sorted(leased_workers), [1, 2])
            self.assertEqual(pool.progress_status()["worker_count"], 2)

    def test_browser_failure_defaults_allow_one_retry_and_bound_inactivity(self) -> None:
        self.assertEqual(chatgpt_browser_generator.DEFAULT_MAX_ATTEMPTS, 2)
        self.assertEqual(
            chatgpt_browser_generator.DEFAULT_RESPONSE_INACTIVITY_TIMEOUT_SECONDS,
            300,
        )

    def test_failure_trace_captures_stage_page_and_exception(self) -> None:
        class FakeDriver:
            current_url = "https://chatgpt.com/c/test-chat"
            page_source = "<html><body>visible failure</body></html>"

            def save_screenshot(self, path: str) -> bool:
                Path(path).write_bytes(b"png")
                return True

            def execute_script(self, script: str) -> str:
                return "visible failure"

        with TemporaryDirectory() as temporary:
            metadata_path = chatgpt_browser_generator._write_selenium_trace(
                FakeDriver(),
                diagnostic_dir=Path(temporary),
                symbol="RKLB",
                attempt=2,
                status="failed",
                stage="wait_response",
                stage_timings={"navigate": 1.25, "wait_response": 300.0},
                error=TimeoutError(),
                capture_page=True,
            )
            payload = json.loads(
                metadata_path.read_text(encoding="utf-8")
            )

            self.assertEqual(payload["stage"], "wait_response")
            self.assertEqual(payload["error_type"], "TimeoutError")
            self.assertEqual(payload["error_message"], "<empty>")
            self.assertTrue(Path(payload["screenshot_path"]).exists())
            self.assertTrue(Path(payload["html_path"]).exists())
            self.assertTrue(Path(payload["visible_text_path"]).exists())

    def test_session_groups_five_tickers_per_chat_by_default(self) -> None:
        with TemporaryDirectory() as temporary:
            session = chatgpt_browser_generator.ChatGPTBrowserSession(
                Path(temporary),
                browser_engine="firefox",
            )
            first_url = "https://chatgpt.com/c/group-one"
            session._record_group_chat("T0", first_url, starts_new_group=True)
            for index in range(1, 5):
                target, starts_new = session._group_request_target(
                    f"T{index}",
                    chatgpt_browser_generator.CHATGPT_URL,
                )
                self.assertEqual(target, first_url)
                self.assertFalse(starts_new)
                session._record_group_chat(
                    f"T{index}",
                    first_url,
                    starts_new_group=False,
                )

            retry_target, retry_starts_new = session._group_request_target(
                "T4",
                chatgpt_browser_generator.CHATGPT_URL,
            )
            self.assertEqual(retry_target, first_url)
            self.assertFalse(retry_starts_new)

            next_target, next_starts_new = session._group_request_target(
                "T5",
                chatgpt_browser_generator.CHATGPT_URL,
            )
            self.assertEqual(next_target, chatgpt_browser_generator.CHATGPT_URL)
            self.assertTrue(next_starts_new)

    def test_session_groups_project_tickers_without_leaving_project_root(self) -> None:
        project_url = (
            "https://chatgpt.com/g/"
            "g-p-6aa00c49d1f08191b9f59c3d60bbd5f1-analisis/project"
        )
        with TemporaryDirectory() as temporary:
            session = chatgpt_browser_generator.ChatGPTBrowserSession(
                Path(temporary),
                browser_engine="firefox",
            )
            # Project chats currently keep the canonical root URL even after
            # ChatGPT has activated the conversation in its SPA state.
            chat_url = chatgpt_browser_generator.CHATGPT_URL
            session._record_group_chat(
                "AAA",
                chat_url,
                starts_new_group=True,
                group_start_url=project_url,
            )

            target, starts_new = session._group_request_target(
                "BBB",
                project_url,
            )
            self.assertEqual(target, chat_url)
            self.assertFalse(starts_new)

            normal_target, normal_starts_new = session._group_request_target(
                "CCC",
                chatgpt_browser_generator.CHATGPT_URL,
            )
            self.assertEqual(normal_target, chatgpt_browser_generator.CHATGPT_URL)
            self.assertTrue(normal_starts_new)

    def test_project_context_accepts_current_spanish_ui_labels(self) -> None:
        element = Mock()
        element.is_displayed.return_value = True
        element.get_attribute.return_value = "Cambiar proyecto: Analisis"
        driver = Mock()
        driver.find_elements.return_value = [element]

        self.assertTrue(
            chatgpt_browser_generator._selenium_project_context_visible(
                driver,
                "Analisis",
            )
        )
        driver.current_url = chatgpt_browser_generator.CHATGPT_URL
        with patch.object(
            chatgpt_browser_generator,
            "_selenium_prompt_visible",
            return_value=True,
        ):
            self.assertTrue(
                chatgpt_browser_generator._selenium_project_ready(
                    driver,
                    "https://chatgpt.com/g/g-p-project-analisis/project",
                )
            )

    def test_generator_uses_stored_project_as_group_root(self) -> None:
        project_url = (
            "https://chatgpt.com/g/"
            "g-p-6aa00c49d1f08191b9f59c3d60bbd5f1-analisis/project"
        )
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / ".local").mkdir()
            (root / ".local" / "chatgpt-project-url.txt").write_text(
                project_url + "\n",
                encoding="utf-8",
            )
            input_path = root / "chatgpt_input.md"
            input_path.write_text("authoritative input", encoding="utf-8")
            output_path = root / "analysis.md"
            session = Mock()
            session.cwd = root.resolve()
            session.engine = "firefox"
            session.chat_group_size = 5

            @contextmanager
            def generation(*, symbol: str = ""):
                yield session

            session.generation.side_effect = generation
            session.request_analysis.return_value = (
                "```markdown\n# Valid report\n```",
                "https://chatgpt.com/c/project-chat",
            )
            session.current_progress_status.return_value = {
                "model_policy_verified_at": "2026-09-21T00:00:00+00:00"
            }
            session.current_worker_id.return_value = 1
            session.generation_timing.return_value = {}

            with patch.object(
                chatgpt_browser_generator,
                "validate_markdown",
                return_value=Mock(ok=True, errors=()),
            ), patch.object(
                chatgpt_browser_generator,
                "_queue_chat_for_cleanup",
                return_value=None,
            ):
                chatgpt_browser_generator.generate_markdown_with_chatgpt_browser(
                    input_path,
                    output_path,
                    cwd=root,
                    symbol="TEST",
                    session=session,
                    max_attempts=1,
                )

            self.assertEqual(
                session.request_analysis.call_args.kwargs["start_url"],
                project_url,
            )
            metadata = json.loads(
                (root / "generation_metadata.json").read_text(encoding="utf-8")
            )
            self.assertEqual(metadata["chat_mode"], "project-grouped-5")
            self.assertEqual(metadata["chatgpt_project_url"], project_url)

    def test_rate_limit_status_counts_waits(self) -> None:
        with TemporaryDirectory() as temporary:
            session = chatgpt_browser_generator.ChatGPTBrowserSession(
                Path(temporary),
                browser_engine="firefox",
            )
            resume_at = datetime.now(timezone.utc) + timedelta(minutes=15)
            session._rate_limit_started(resume_at)

            waiting = session.progress_status()
            self.assertTrue(waiting["rate_limit_waiting"])
            self.assertEqual(waiting["rate_limit_count"], 1)
            self.assertEqual(waiting["rate_limit_resume_at"], resume_at.isoformat())

            session._rate_limit_finished()
            finished = session.progress_status()
            self.assertFalse(finished["rate_limit_waiting"])
            self.assertEqual(finished["rate_limit_count"], 1)

    def test_persistent_session_launches_and_authenticates_only_once(self) -> None:
        with TemporaryDirectory() as temporary:
            driver = Mock()
            driver.current_url = "https://chatgpt.com/"
            with patch.object(
                chatgpt_browser_generator,
                "_launch_firefox",
                return_value=driver,
            ) as launch, patch.object(
                chatgpt_browser_generator,
                "_ensure_selenium_authenticated",
            ) as authenticate:
                session = chatgpt_browser_generator.ChatGPTBrowserSession(
                    Path(temporary),
                    browser_engine="firefox",
                )
                session.open()
                session.open()
                session.close()

            launch.assert_called_once()
            authenticate.assert_called_once_with(
                driver,
                timeout_seconds=(
                    chatgpt_browser_generator.DEFAULT_NAVIGATION_TIMEOUT_SECONDS
                ),
            )
            driver.quit.assert_called_once_with()

    def test_stale_lock_recovery_cleans_orphaned_firefox_before_launch(self) -> None:
        with TemporaryDirectory() as temporary:
            driver = Mock()
            driver.current_url = "https://chatgpt.com/"
            lock_context = Mock()
            lock_context.__enter__ = Mock(return_value=True)
            lock_context.__exit__ = Mock(return_value=None)
            with patch.object(
                chatgpt_browser_generator,
                "_exclusive_browser_lock",
                return_value=lock_context,
            ), patch.object(
                chatgpt_browser_generator,
                "_stop_orphaned_firefox_profile_processes",
            ) as cleanup, patch.object(
                chatgpt_browser_generator,
                "_launch_firefox",
                return_value=driver,
            ), patch.object(
                chatgpt_browser_generator,
                "_ensure_selenium_authenticated",
            ):
                session = chatgpt_browser_generator.ChatGPTBrowserSession(
                    Path(temporary),
                    browser_engine="firefox",
                )
                session.open()
                session.close()

            cleanup.assert_called_once_with(session.profile_dir)
            driver.quit.assert_called_once_with()

    def test_invalidated_session_restarts_before_next_generation(self) -> None:
        with TemporaryDirectory() as temporary:
            first_driver = Mock()
            first_driver.current_url = "https://chatgpt.com/c/first"
            second_driver = Mock()
            second_driver.current_url = "https://chatgpt.com/"
            with patch.object(
                chatgpt_browser_generator,
                "_launch_firefox",
                side_effect=(first_driver, second_driver),
            ) as launch, patch.object(
                chatgpt_browser_generator,
                "_ensure_selenium_authenticated",
            ):
                session = chatgpt_browser_generator.ChatGPTBrowserSession(
                    Path(temporary),
                    browser_engine="firefox",
                )
                session.open()
                session.invalidate()
                with session.generation():
                    self.assertIs(session._driver, second_driver)
                session.close()

            self.assertEqual(launch.call_count, 2)
            first_driver.quit.assert_called_once_with()
            second_driver.quit.assert_called_once_with()

    def test_sol_high_failure_waits_and_retries_same_worker(self) -> None:
        with TemporaryDirectory() as temporary:
            session = chatgpt_browser_generator.ChatGPTBrowserSession(
                Path(temporary),
                browser_engine="firefox",
            )
            session._driver = Mock()
            session._driver.current_url = "https://chatgpt.com/"
            policy_error = RuntimeError(
                "chatgpt_sol_high_not_confirmed: reasoning_menu_not_opened"
            )
            with patch.object(
                chatgpt_browser_generator,
                "_request_fresh_analysis_selenium",
                side_effect=(policy_error, ("report", "https://chatgpt.com/c/ok")),
            ) as request, patch.object(
                chatgpt_browser_generator.time,
                "sleep",
            ) as sleep, patch.object(
                session,
                "_restart_after_browser_state_failure",
            ) as restart, patch.object(
                chatgpt_browser_generator,
                "_write_browser_timeline_event",
            ):
                result = session.request_analysis(
                    attachment_paths=(),
                    symbol="HOOD",
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

            self.assertEqual(result, ("report", "https://chatgpt.com/c/ok"))
            self.assertEqual(request.call_count, 2)
            sleep.assert_called_once_with(
                chatgpt_browser_generator.DEFAULT_MODEL_POLICY_RETRY_WAIT_SECONDS
            )
            restart.assert_not_called()

    def test_open_retries_login_then_restarts_only_its_firefox(self) -> None:
        with TemporaryDirectory() as temporary:
            first_driver = Mock()
            second_driver = Mock()
            login_error = RuntimeError("chatgpt_login_required")
            with patch.object(
                chatgpt_browser_generator,
                "_launch_firefox",
                side_effect=(first_driver, second_driver),
            ) as launch, patch.object(
                chatgpt_browser_generator,
                "_ensure_selenium_authenticated",
                side_effect=(login_error, login_error, None),
            ) as authenticate, patch.object(
                chatgpt_browser_generator.time,
                "sleep",
            ) as sleep:
                session = chatgpt_browser_generator.ChatGPTBrowserSession(
                    Path(temporary),
                    browser_engine="firefox",
                )
                session.open()
                self.assertIs(session._driver, second_driver)
                session.close()

            self.assertEqual(launch.call_count, 2)
            self.assertEqual(authenticate.call_count, 3)
            sleep.assert_called_once_with(
                chatgpt_browser_generator.DEFAULT_MODEL_POLICY_RETRY_WAIT_SECONDS
            )
            first_driver.quit.assert_called_once_with()
            second_driver.quit.assert_called_once_with()

    def test_open_restarts_firefox_after_navigation_read_timeout(self) -> None:
        with TemporaryDirectory() as temporary:
            first_driver = Mock()
            second_driver = Mock()
            third_driver = Mock()
            navigation_error = RuntimeError(
                "chatgpt_firefox_navigation_failed: "
                "HTTPConnectionPool(host='localhost', port=123): "
                "Read timed out. (read timeout=120)"
            )
            with patch.object(
                chatgpt_browser_generator,
                "_launch_firefox",
                side_effect=(first_driver, second_driver, third_driver),
            ) as launch, patch.object(
                chatgpt_browser_generator,
                "_ensure_selenium_authenticated",
                side_effect=(navigation_error, navigation_error, None),
            ) as authenticate, patch.object(
                chatgpt_browser_generator.time,
                "sleep",
            ) as sleep:
                session = chatgpt_browser_generator.ChatGPTBrowserSession(
                    Path(temporary),
                    browser_engine="firefox",
                )
                session.open()
                self.assertIs(session._driver, third_driver)
                session.close()

            self.assertEqual(launch.call_count, 3)
            self.assertEqual(authenticate.call_count, 3)
            self.assertEqual(
                [call.args[0] for call in sleep.call_args_list],
                [5, 10],
            )
            first_driver.quit.assert_called_once_with()
            second_driver.quit.assert_called_once_with()
            third_driver.quit.assert_called_once_with()

    def test_open_retries_transient_firefox_launch_timeout(self) -> None:
        with TemporaryDirectory() as temporary:
            driver = Mock()
            launch_error = RuntimeError(
                "chatgpt_firefox_launch_failed: "
                "HTTPConnectionPool(host='localhost', port=123): "
                "Read timed out. (read timeout=120)"
            )
            with patch.object(
                chatgpt_browser_generator,
                "_launch_firefox",
                side_effect=(launch_error, driver),
            ) as launch, patch.object(
                chatgpt_browser_generator,
                "_stop_orphaned_firefox_profile_processes",
            ) as cleanup, patch.object(
                chatgpt_browser_generator.time,
                "sleep",
            ) as sleep, patch.object(
                chatgpt_browser_generator,
                "_ensure_selenium_authenticated",
            ) as authenticate:
                session = chatgpt_browser_generator.ChatGPTBrowserSession(
                    Path(temporary),
                    browser_engine="firefox",
                )
                session.open()
                session.close()

            self.assertEqual(launch.call_count, 2)
            cleanup.assert_called_once_with(
                session.profile_dir,
                include_manual=True,
            )
            sleep.assert_called_once_with(5)
            authenticate.assert_called_once_with(
                driver,
                timeout_seconds=(
                    chatgpt_browser_generator.DEFAULT_NAVIGATION_TIMEOUT_SECONDS
                ),
            )
            driver.quit.assert_called_once_with()

    def test_transient_login_link_must_clear_before_prompt_is_authenticated(self) -> None:
        driver = Mock()
        with patch.object(
            chatgpt_browser_generator,
            "_selenium_prompt_visible",
            return_value=True,
        ), patch.object(
            chatgpt_browser_generator,
            "_selenium_login_visible",
            side_effect=(True, False),
        ), patch.object(
            chatgpt_browser_generator.time,
            "sleep",
        ):
            chatgpt_browser_generator._ensure_selenium_authenticated(
                driver,
                timeout_seconds=1,
            )

        driver.get.assert_called_once_with(chatgpt_browser_generator.CHATGPT_URL)

    def test_pool_preflight_excludes_logged_out_worker(self) -> None:
        with TemporaryDirectory() as temporary:
            healthy_one = Mock()
            healthy_one.cwd = Path(temporary).resolve()
            healthy_one.engine = "firefox"
            healthy_one.worker_id = 1
            healthy_one.chat_group_size = 5
            healthy_one.open.return_value = healthy_one
            logged_out = Mock()
            logged_out.cwd = Path(temporary).resolve()
            logged_out.engine = "firefox"
            logged_out.worker_id = 2
            logged_out.chat_group_size = 5
            logged_out.open.side_effect = RuntimeError("chatgpt_login_required")
            healthy_three = Mock()
            healthy_three.cwd = Path(temporary).resolve()
            healthy_three.engine = "firefox"
            healthy_three.worker_id = 3
            healthy_three.chat_group_size = 5
            healthy_three.open.return_value = healthy_three
            pool = chatgpt_browser_generator.ChatGPTBrowserSessionPool(
                Path(temporary),
                worker_count=3,
                browser_engine="firefox",
                sessions=(healthy_one, logged_out, healthy_three),
            )

            pool.preflight()

            self.assertEqual(pool.worker_count, 2)
            self.assertEqual(pool.disabled_worker_ids, (2,))
            self.assertEqual(
                tuple(session.worker_id for session in pool.sessions),
                (1, 3),
            )
            logged_out.close.assert_called_once_with()

    def test_pool_preflight_excludes_worker_with_dead_driver_transport(self) -> None:
        with TemporaryDirectory() as temporary:
            healthy = Mock()
            healthy.cwd = Path(temporary).resolve()
            healthy.engine = "firefox"
            healthy.worker_id = 1
            healthy.chat_group_size = 5
            healthy.open.return_value = healthy
            timed_out = Mock()
            timed_out.cwd = Path(temporary).resolve()
            timed_out.engine = "firefox"
            timed_out.worker_id = 2
            timed_out.chat_group_size = 5
            timed_out.open.side_effect = RuntimeError(
                "chatgpt_firefox_navigation_failed: "
                "HTTPConnectionPool(host='localhost', port=123): Read timed out."
            )
            pool = chatgpt_browser_generator.ChatGPTBrowserSessionPool(
                Path(temporary),
                worker_count=2,
                browser_engine="firefox",
                sessions=(healthy, timed_out),
            )

            pool.preflight()

            self.assertEqual(pool.worker_count, 1)
            self.assertEqual(pool.disabled_worker_ids, (2,))
            self.assertEqual(pool.sessions, (healthy,))
            timed_out.close.assert_called_once_with()

    def test_repeated_sol_high_failure_restarts_same_worker_and_ticker(self) -> None:
        with TemporaryDirectory() as temporary:
            session = chatgpt_browser_generator.ChatGPTBrowserSession(
                Path(temporary),
                browser_engine="firefox",
            )
            session._driver = Mock()
            session._driver.current_url = "https://chatgpt.com/"
            policy_error = RuntimeError(
                "chatgpt_sol_high_not_confirmed: reasoning_menu_not_opened"
            )
            with patch.object(
                chatgpt_browser_generator,
                "_request_fresh_analysis_selenium",
                side_effect=(
                    policy_error,
                    policy_error,
                    ("report", "https://chatgpt.com/c/ok"),
                ),
            ) as request, patch.object(
                chatgpt_browser_generator.time,
                "sleep",
            ), patch.object(
                session,
                "_restart_after_browser_state_failure",
            ) as restart, patch.object(
                chatgpt_browser_generator,
                "_write_browser_timeline_event",
            ):
                result = session.request_analysis(
                    attachment_paths=(),
                    symbol="HOOD",
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

            self.assertEqual(result, ("report", "https://chatgpt.com/c/ok"))
            self.assertEqual(request.call_count, 3)
            restart.assert_called_once_with()

    def test_login_required_retries_then_restarts_same_worker_and_ticker(self) -> None:
        with TemporaryDirectory() as temporary:
            session = chatgpt_browser_generator.ChatGPTBrowserSession(
                Path(temporary),
                browser_engine="firefox",
            )
            session._driver = Mock()
            session._driver.current_url = "https://chatgpt.com/"
            login_error = RuntimeError("chatgpt_login_required")
            with patch.object(
                chatgpt_browser_generator,
                "_request_fresh_analysis_selenium",
                side_effect=(
                    login_error,
                    login_error,
                    ("report", "https://chatgpt.com/c/ok"),
                ),
            ) as request, patch.object(
                chatgpt_browser_generator.time,
                "sleep",
            ), patch.object(
                session,
                "_restart_after_browser_state_failure",
            ) as restart, patch.object(
                chatgpt_browser_generator,
                "_write_browser_timeline_event",
            ):
                result = session.request_analysis(
                    attachment_paths=(),
                    symbol="NVDA",
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

            self.assertEqual(result, ("report", "https://chatgpt.com/c/ok"))
            self.assertEqual(request.call_count, 3)
            restart.assert_called_once_with()

    def test_duplicate_attachment_dialog_is_dismissed(self) -> None:
        button = Mock()
        button.text = "Aceptar"
        button.get_attribute.return_value = None
        dialog = Mock()
        dialog.is_displayed.return_value = True
        dialog.find_elements.return_value = [button]
        driver = Mock()
        driver.find_elements.return_value = [dialog]

        dismissed = (
            chatgpt_browser_generator._dismiss_duplicate_attachment_dialog_selenium(
                driver
            )
        )

        self.assertTrue(dismissed)
        driver.execute_script.assert_called_once_with(
            "arguments[0].click();",
            button,
        )

    def test_attachment_confirmation_uses_visible_composer_chips(self) -> None:
        driver = Mock()
        with patch.object(
            chatgpt_browser_generator,
            "_selenium_attachment_chip_visible",
            return_value=True,
        ) as chip_visible, patch.object(
            chatgpt_browser_generator,
            "_dismiss_duplicate_attachment_dialog_selenium",
            side_effect=(True, False),
        ) as dismiss:
            chatgpt_browser_generator._wait_for_selenium_attachment_chips(
                driver,
                ("chatgpt_input.md", "previous_analysis.md"),
                timeout_seconds=1,
            )

        self.assertEqual(chip_visible.call_count, 2)
        self.assertEqual(dismiss.call_count, 2)

    def test_attachment_chip_detection_accepts_current_global_chip_markup(self) -> None:
        chip = Mock()
        chip.is_displayed.return_value = True
        driver = Mock()
        driver.find_elements.return_value = [chip]

        visible = chatgpt_browser_generator._selenium_attachment_chip_visible(
            driver,
            "chatgpt_input__AMD__attempt-1.md",
        )

        self.assertTrue(visible)
        xpath = driver.find_elements.call_args.args[1]
        self.assertTrue(xpath.startswith("//*"))
        self.assertNotIn("data-composer-surface", xpath)

    def test_stale_composer_attachments_are_removed_before_upload(self) -> None:
        first = Mock()
        second = Mock()
        driver = Mock()
        driver.find_elements.side_effect = ([first, second], [second], [])

        with patch.object(chatgpt_browser_generator.time, "sleep"):
            chatgpt_browser_generator._clear_selenium_composer_attachments(driver)

        self.assertEqual(driver.execute_script.call_count, 2)
        self.assertEqual(
            [call.args[1] for call in driver.execute_script.call_args_list],
            [first, second],
        )

    def test_new_assistant_is_detected_when_virtualized_count_stays_constant(self) -> None:
        previous = Mock()
        previous.id = "reused-turn"
        previous.text = "Informe anterior"
        current = Mock()
        current.id = "reused-turn"
        current.text = "# ASML\n\nInforme nuevo completo"
        driver = Mock()
        driver.find_elements.return_value = [current]

        self.assertTrue(
            chatgpt_browser_generator._selenium_new_assistant_visible(
                driver,
                (1, previous.id, previous.text),
            )
        )

    def test_wait_for_new_assistant_recovers_from_transient_driver_read(self) -> None:
        driver = Mock()
        transient = RuntimeError(
            "HTTPConnectionPool(host='localhost', port=123): Read timed out."
        )
        with patch.object(
            chatgpt_browser_generator,
            "_selenium_new_assistant_visible",
            side_effect=(transient, True),
        ) as visible, patch.object(
            chatgpt_browser_generator.time,
            "sleep",
        ):
            chatgpt_browser_generator._wait_for_selenium_new_assistant(
                driver,
                (0, "", ""),
                timeout_seconds=2,
            )

        self.assertEqual(visible.call_count, 2)

    def test_response_poll_recovers_from_stale_dom_element(self) -> None:
        response = Mock()
        response.text = "complete report"
        driver = Mock()
        call_count = 0

        def find_elements(_by: object, selector: str) -> list[Mock]:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("stale element reference")
            if selector == chatgpt_browser_generator.ASSISTANT_SELECTOR:
                return [response]
            return []

        driver.find_elements.side_effect = find_elements
        with patch.object(
            chatgpt_browser_generator,
            "_selenium_live_status_text",
            return_value="",
        ), patch.object(chatgpt_browser_generator.time, "sleep"):
            chatgpt_browser_generator._wait_for_selenium_response_complete(
                driver,
                timeout_seconds=2,
                inactivity_timeout_seconds=2,
            )

        self.assertGreater(call_count, 1)

    def test_unchanged_assistant_is_not_detected_as_new(self) -> None:
        current = Mock()
        current.id = "same-turn"
        current.text = "Informe anterior"
        driver = Mock()
        driver.find_elements.return_value = [current]

        self.assertFalse(
            chatgpt_browser_generator._selenium_new_assistant_visible(
                driver,
                (1, current.id, current.text),
            )
        )

    def test_release_retries_windows_sharing_violation(self) -> None:
        lock_path = Mock()
        lock_path.unlink.side_effect = [PermissionError(32, "busy"), None]
        with patch.object(chatgpt_browser_generator.time, "sleep") as sleep:
            chatgpt_browser_generator._release_lock(lock_path)

        self.assertEqual(lock_path.unlink.call_count, 2)
        sleep.assert_called_once_with(0.1)

    def test_windows_process_probe_does_not_send_a_signal(self) -> None:
        with patch.object(
            chatgpt_browser_generator.ctypes.windll.kernel32,
            "OpenProcess",
            return_value=123,
        ) as open_process, patch.object(
            chatgpt_browser_generator.ctypes.windll.kernel32,
            "GetExitCodeProcess",
            side_effect=lambda _handle, pointer: (
                setattr(pointer._obj, "value", 259) or 1
            ),
        ) as get_exit_code, patch.object(
            chatgpt_browser_generator.ctypes.windll.kernel32,
            "CloseHandle",
        ) as close_handle, patch.object(
            chatgpt_browser_generator.os,
            "kill",
        ) as kill:
            self.assertTrue(chatgpt_browser_generator._process_exists(456))

        open_process.assert_called_once_with(0x1000, False, 456)
        get_exit_code.assert_called_once()
        close_handle.assert_called_once_with(123)
        kill.assert_not_called()

    def test_windows_process_probe_rejects_exited_process(self) -> None:
        with patch.object(
            chatgpt_browser_generator.ctypes.windll.kernel32,
            "OpenProcess",
            return_value=123,
        ), patch.object(
            chatgpt_browser_generator.ctypes.windll.kernel32,
            "GetExitCodeProcess",
            side_effect=lambda _handle, pointer: (
                setattr(pointer._obj, "value", 0) or 1
            ),
        ), patch.object(
            chatgpt_browser_generator.ctypes.windll.kernel32,
            "CloseHandle",
        ):
            self.assertFalse(chatgpt_browser_generator._process_exists(456))

    def test_fresh_incomplete_lock_is_not_removed(self) -> None:
        with TemporaryDirectory() as temporary:
            lock_path = Path(temporary) / "browser.lock"
            lock_path.write_text("", encoding="utf-8")

            self.assertFalse(
                chatgpt_browser_generator._remove_stale_lock(lock_path)
            )
            self.assertTrue(lock_path.exists())

    def test_old_incomplete_lock_is_removed(self) -> None:
        with TemporaryDirectory() as temporary, patch.object(
            chatgpt_browser_generator,
            "DEFAULT_LOCK_INITIALIZATION_GRACE_SECONDS",
            0,
        ):
            lock_path = Path(temporary) / "browser.lock"
            lock_path.write_text("", encoding="utf-8")
            os.utime(lock_path, (1, 1))

            self.assertTrue(
                chatgpt_browser_generator._remove_stale_lock(lock_path)
            )
            self.assertFalse(lock_path.exists())

    def test_browser_timeline_keeps_latest_state_and_history(self) -> None:
        with TemporaryDirectory() as temporary:
            diagnostic_dir = Path(temporary)
            chatgpt_browser_generator._write_browser_timeline_event(
                diagnostic_dir=diagnostic_dir,
                symbol="AAA",
                attempt=1,
                stage="attach",
                status="running",
                stage_timings={"navigate": 2.5},
            )
            chatgpt_browser_generator._write_browser_timeline_event(
                diagnostic_dir=diagnostic_dir,
                symbol="AAA",
                attempt=1,
                stage="confirm_attachments",
                status="running",
                stage_timings={"navigate": 2.5, "attach": 1.0},
            )

            latest = json.loads(
                (diagnostic_dir / "current.json").read_text(encoding="utf-8")
            )
            timeline = (diagnostic_dir / "timeline.jsonl").read_text(
                encoding="utf-8"
            ).splitlines()

            self.assertEqual(latest["stage"], "confirm_attachments")
            self.assertEqual(len(timeline), 2)

    def test_progress_status_distinguishes_active_and_waiting_tickers(self) -> None:
        with TemporaryDirectory() as temporary:
            session = chatgpt_browser_generator.ChatGPTBrowserSession(
                Path(temporary),
                browser_engine="firefox",
            )
            with session._status_lock:
                session._waiting_symbols["BBB"] = datetime.now(
                    timezone.utc
                ).isoformat()
            session._set_active_stage("AAA", 2, "wait_response")

            status = session.progress_status()

            self.assertEqual(status["active_ticker"], "AAA")
            self.assertEqual(status["active_attempt"], 2)
            self.assertEqual(status["active_stage"], "wait_response")
            self.assertEqual(status["waiting_tickers"], ["BBB"])
            self.assertFalse(status["active_stage_stalled"])

    def test_request_attachments_get_unique_names_and_keep_contents(self) -> None:
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            first = root / "chatgpt_input.md"
            second = root / "previous_analysis.md"
            first.write_text("current", encoding="utf-8")
            second.write_text("previous", encoding="utf-8")

            staged = chatgpt_browser_generator._stage_unique_request_attachments(
                (first, second),
                diagnostic_dir=root / "diagnostics",
                symbol="CCJ",
                attempt=2,
            )

            self.assertEqual([path.read_text() for path in staged], ["current", "previous"])
            self.assertIn("CCJ__attempt-2", staged[0].name)
            self.assertNotEqual(staged[0].name, first.name)
            request = chatgpt_browser_generator.build_analysis_request(
                "CCJ",
                input_attachment_name=staged[0].name,
                previous_attachment_name=staged[1].name,
            )
            self.assertIn(f"`{staged[0].name}`", request)
            self.assertIn(f"`{staged[1].name}`", request)

    def test_attachment_limit_parser_honors_spanish_retry_time(self) -> None:
        wait_seconds = chatgpt_browser_generator._attachment_limit_wait_seconds(
            "Te has quedado sin archivos adjuntos por ahora. "
            "Vuelve a intentarlo en 2 minutos."
        )

        self.assertEqual(wait_seconds, 135)

    def test_attachment_limit_parser_uses_safe_default_without_retry_time(self) -> None:
        wait_seconds = chatgpt_browser_generator._attachment_limit_wait_seconds(
            "You've reached your file upload limit."
        )

        self.assertEqual(wait_seconds, 195)

    def test_attachment_confirmation_surfaces_temporary_upload_limit(self) -> None:
        driver = Mock()
        with patch.object(
            chatgpt_browser_generator,
            "_selenium_attachment_limit_wait_seconds",
            return_value=135,
        ), patch.object(
            chatgpt_browser_generator,
            "_selenium_attachment_chip_visible",
        ) as chip_visible:
            with self.assertRaises(
                chatgpt_browser_generator._AttachmentUploadTemporarilyLimited
            ) as raised:
                chatgpt_browser_generator._wait_for_selenium_attachment_chips(
                    driver,
                    ("chatgpt_input.md", "previous_analysis.md"),
                    timeout_seconds=1,
                )

        self.assertEqual(raised.exception.wait_seconds, 135)
        chip_visible.assert_not_called()

    def test_attachment_limit_retries_same_upload_after_shared_cooldown(self) -> None:
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            first = root / "chatgpt_input.md"
            second = root / "previous_analysis.md"
            first.write_text("current", encoding="utf-8")
            second.write_text("previous", encoding="utf-8")
            file_input = Mock()
            driver = Mock()
            driver.find_elements.return_value = [file_input]
            cooldown = Mock()
            cooldown.status.return_value = {"waiting": False}
            cooldown.trigger.return_value = "2026-09-14T01:02:03+00:00"
            stages: list[str] = []

            with patch.object(
                chatgpt_browser_generator,
                "_wait_for_selenium_attachment_chips",
                side_effect=(
                    chatgpt_browser_generator._AttachmentUploadTemporarilyLimited(
                        135
                    ),
                    None,
                ),
            ) as confirm:
                chatgpt_browser_generator._attach_files_selenium_with_cooldown(
                    driver,
                    (first, second),
                    timeout_seconds=1,
                    cooldown=cooldown,
                    advance_stage=stages.append,
                )

            self.assertEqual(file_input.send_keys.call_count, 2)
            self.assertEqual(confirm.call_count, 2)
            cooldown.trigger.assert_called_once_with(135)
            cooldown.wait.assert_called_once_with()
            self.assertEqual(
                stages,
                [
                    "attach",
                    "confirm_attachments",
                    "attachment_limit_wait",
                    "attach",
                    "confirm_attachments",
                ],
            )

    def test_real_pool_shares_one_attachment_cooldown_across_workers(self) -> None:
        with TemporaryDirectory() as temporary:
            pool = chatgpt_browser_generator.ChatGPTBrowserSessionPool(
                Path(temporary),
                worker_count=3,
                browser_engine="firefox",
            )

            cooldown_ids = {
                id(session._attachment_cooldown) for session in pool.sessions
            }
            self.assertEqual(len(cooldown_ids), 1)
            self.assertIn(id(pool._attachment_cooldown), cooldown_ids)

            pool._attachment_cooldown.trigger(60)
            status = pool.progress_status()
            self.assertTrue(status["attachment_rate_limit_waiting"])
            self.assertEqual(status["attachment_rate_limit_count"], 1)
            self.assertEqual(status["rate_limit_count"], 1)


if __name__ == "__main__":
    unittest.main()
