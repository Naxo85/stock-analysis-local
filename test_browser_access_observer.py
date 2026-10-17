from unittest.mock import Mock, patch

import pytest

from src.local_runner import chatgpt_browser_generator as browser
from src.local_runner import chatgpt_browser_network as network


def response(status=403, *, challenge=True, path='/backend-api/models?private=value'):
    return {
        'url': 'https://chatgpt.com' + path,
        'status': status,
        'headers': ([{'name': 'cf-mitigated', 'value': {'type': 'string', 'value': 'challenge'}}]
                    if challenge else []),
    }


def test_observer_requires_actual_challenge_header_and_essential_endpoint():
    observer = network.BrowserAccessObserver()
    observer.record(response(challenge=False))
    observer.record(response(path='/ces/v1/rgstr'))
    assert observer.blocked_paths() == []
    observer.record(response())
    assert observer.blocked_paths() == ['/backend-api/models']


def test_successful_retry_clears_challenge_evidence():
    observer = network.BrowserAccessObserver()
    observer.record(response())
    observer.record(response(status=200, challenge=False))
    assert observer.blocked_paths() == []


def test_authentication_rejects_composer_shell_with_blocked_account_requests():
    driver = Mock()
    driver._analysis_access_observer = network.BrowserAccessObserver()
    with patch.object(network.time, 'monotonic', return_value=100):
        driver._analysis_access_observer.record(response(path='/backend-api/me'))
    with patch.object(network.time, 'monotonic', return_value=106), patch.object(
        browser, '_selenium_prompt_visible', return_value=True
    ), patch.object(browser, '_selenium_login_visible', return_value=False):
        with pytest.raises(RuntimeError, match='human_verification_required: api=/backend-api/me'):
            browser._ensure_selenium_authenticated(driver, timeout_seconds=20)


def test_project_is_not_ready_when_only_cached_context_survives_a_challenge():
    driver = Mock()
    driver._analysis_access_observer = network.BrowserAccessObserver()
    driver._analysis_access_observer.record(response())
    with patch.object(browser, '_selenium_prompt_visible', return_value=True), patch.object(
        browser, '_selenium_project_context_visible', return_value=True
    ):
        assert not browser._selenium_project_ready(driver, 'https://chatgpt.com/g/g-p-test/project')
