import sys
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent / 'scripts'))
import check_chatgpt_chromium as check


def state(**changes):
    return dict(login=False, loading=False, account_error=False,
                human_challenge=False, projects=['g-p-test']) | changes


def test_diagnostic_never_accepts_logged_out_composer_as_authentication():
    page = Mock()
    observer = Mock()
    observer.blocked_paths.return_value = []
    clock = [100.0]
    page.wait_for_timeout.side_effect = lambda ms: clock.__setitem__(0, clock[0] + ms / 1000)
    with patch.object(check, 'ui_state', return_value=state(login=True)), patch.object(
        check.time, 'monotonic', side_effect=lambda: clock[0]
    ), patch.object(check.browser, '_prompt_visible', return_value=True):
        with pytest.raises(RuntimeError, match='chatgpt_login_required'):
            check.wait_ready(page, observer, 'g-p-test')
    page.get_by_role.assert_not_called()


def test_diagnostic_stops_on_visible_challenge_without_clicking():
    page = Mock()
    with patch.object(check, 'ui_state', return_value=state(human_challenge=True)):
        with pytest.raises(RuntimeError, match='chatgpt_human_verification_required'):
            check.wait_ready(page, Mock(), 'g-p-test')
    page.get_by_role.assert_not_called()


def test_diagnostic_stops_on_confirmed_network_challenge():
    observer = Mock()
    observer.blocked_paths.return_value = ['/backend-api/me']
    with patch.object(check, 'ui_state', return_value=state()):
        with pytest.raises(RuntimeError, match='chatgpt_human_verification_required: api=/backend-api/me'):
            check.wait_ready(Mock(), observer, 'g-p-test')


def test_diagnostic_accepts_only_loaded_expected_project():
    page = Mock(url='https://chatgpt.com/g/g-p-test/project')
    observer = Mock()
    observer.blocked_paths.return_value = []
    with patch.object(check, 'ui_state', return_value=state()), patch.object(
        check.browser, '_prompt_visible', return_value=True
    ):
        check.wait_ready(page, observer, 'g-p-test', project_url=page.url)
    page.get_by_role.assert_not_called()
