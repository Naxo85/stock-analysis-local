from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch

import pytest

from src.local_runner import chatgpt_browser_generator as browser
from src.local_runner import run_one


def test_authentication_reports_human_verification() -> None:
    driver = Mock()
    driver.page_source = '<script>window._cf_chl_opt={}</script><script src="/cdn-cgi/challenge-platform/x">'
    with pytest.raises(RuntimeError, match="chatgpt_human_verification_required"):
        browser._ensure_selenium_authenticated(driver, timeout_seconds=0)


def test_invisible_cloudflare_javascript_is_not_a_human_challenge() -> None:
    driver = Mock()
    driver.page_source = (
        '<title>ChatGPT</title><p>No hemos podido cargar tu cuenta</p>'
        '<script src="/cdn-cgi/challenge-platform/scripts/jsd/api.js"></script>'
    )
    driver.find_elements.return_value = []
    assert not browser._selenium_human_verification_visible(driver)


def test_visible_turnstile_frame_is_a_human_challenge() -> None:
    driver = Mock(page_source='<title>ChatGPT</title>')
    frame = Mock()
    frame.is_displayed.return_value = True
    driver.find_elements.return_value = [frame]
    assert browser._selenium_human_verification_visible(driver)
    frame.is_displayed.return_value = False
    assert not browser._selenium_human_verification_visible(driver)


def test_worker_is_quarantined_after_human_verification() -> None:
    with TemporaryDirectory() as temporary:
        session = browser.ChatGPTBrowserSession(Path(temporary), browser_engine="firefox")
        with patch.object(
            session, "open", side_effect=RuntimeError("chatgpt_human_verification_required"),
        ):
            with pytest.raises(RuntimeError, match="chatgpt_human_verification_required"):
                with session.generation(symbol="NVDA"):
                    pass
        assert session._quarantined


def test_manual_login_can_target_each_worker_profile() -> None:
    assert browser._parse_cli(["login", "--worker-id", "3"]).worker_id == 3


@pytest.mark.parametrize(
    "web_error,worker_count",
    [
        ("chatgpt_human_verification_required", 2),
        ("chatgpt_account_load_failed: reloads_exhausted=3", 2),
        ("chatgpt_no_healthy_browser_workers", 0),
        ("chatgpt_project_not_open: Analisis", 2),
        ("chatgpt_project_context_not_confirmed: Analisis", 2),
        ("chatgpt_browser_worker_quarantined: navigation_failed", 0),
    ],
)
def test_batch_browser_outage_never_starts_codex_fallback(
    web_error: str, worker_count: int,
) -> None:
    with TemporaryDirectory() as temporary:
        root = Path(temporary)
        output_dir = root / "output" / "NVDA"
        output_dir.mkdir(parents=True)
        (output_dir / "codex_input.md").write_text("test input", encoding="utf-8")
        session = Mock(worker_count=worker_count)
        with patch.object(
            run_one, "generate_markdown_with_chatgpt_browser",
            side_effect=RuntimeError(web_error),
        ), patch.object(run_one, "generate_markdown_with_codex") as codex:
            with pytest.raises(RuntimeError, match=web_error):
                run_one._generate(
                    root, "NVDA", execution_context="batch",
                    generation_provider="chatgpt-browser",
                    chatgpt_browser_session=session,
                )
        codex.assert_not_called()
