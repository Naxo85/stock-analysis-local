from contextlib import nullcontext
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch

from src.local_runner import chatgpt_browser_generator as browser


def test_manual_chromium_uses_dedicated_profile_and_suppresses_extensions_and_sync():
    with TemporaryDirectory() as temporary:
        root = Path(temporary)
        profile = root / '.local/chatgpt-browser-profile'
        with patch.object(Path, 'cwd', return_value=root), patch.object(
            browser, '_profile_dir', return_value=profile
        ), patch.object(browser, '_browser_executable', return_value='chrome.exe'), patch.object(
            browser, '_exclusive_browser_lock', return_value=nullcontext()
        ), patch.object(browser.subprocess, 'run', return_value=Mock(returncode=0)) as run:
            assert browser.main(['login', '--browser', 'chromium', '--worker-id', '1']) == 0
        command = run.call_args.args[0]
        assert f'--user-data-dir={profile}' in command
        assert '--disable-extensions' in command
        assert '--disable-sync' in command
        assert browser.CHATGPT_URL in command
