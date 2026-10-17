"""Check one ChatGPT project in true Firefox headless mode without sending a prompt.

This isolates Selenium/headless behavior from the Windows private-desktop
launcher. It uses the worker's real profile and must not run alongside a batch.
"""

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.local_runner.chatgpt_browser_generator import (  # noqa: E402
    _ensure_selenium_authenticated,
    _exclusive_browser_lock,
    _firefox_executable,
    _lock_path,
    _open_project_selenium,
    _profile_dir,
    _stored_project_url,
    _write_selenium_trace,
)
from src.local_runner.command_worker import local_worker_lock  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--worker-id', type=int, choices=(1, 2, 3), default=1)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    project_url = _stored_project_url(root)
    if not project_url:
        raise RuntimeError('chatgpt_project_url_not_configured')

    with local_worker_lock(root / 'logs' / 'command_worker.lock') as acquired:
        if not acquired:
            raise RuntimeError('another_command_worker_is_active')
        with _exclusive_browser_lock(
            _lock_path(root, worker_id=args.worker_id), timeout_seconds=0,
        ):
            from selenium import webdriver
            from selenium.webdriver.firefox.options import Options

            options = Options()
            options.binary_location = _firefox_executable()
            options.page_load_strategy = 'eager'
            options.add_argument('-headless')
            options.add_argument('-no-remote')
            options.add_argument('-profile')
            options.add_argument(str(_profile_dir(root, engine='firefox', worker_id=args.worker_id)))
            driver = webdriver.Firefox(options=options)
            try:
                driver.set_page_load_timeout(60)
                _ensure_selenium_authenticated(driver, timeout_seconds=45)
                _open_project_selenium(driver, project_url=project_url, timeout_seconds=45)
            except Exception as error:
                _write_selenium_trace(
                    driver,
                    diagnostic_dir=root / 'logs' / 'browser_startup' / f'worker-{args.worker_id}',
                    symbol=f'worker-{args.worker_id}', attempt=0,
                    status='failed', stage='headless_project',
                    stage_timings={}, error=error, capture_page=True,
                )
                print(json.dumps({'worker': args.worker_id, 'mode': 'headless',
                                  'project_ready': False, 'error': str(error)}), flush=True)
                return 1
            else:
                print(json.dumps({'worker': args.worker_id, 'mode': 'headless',
                                  'project_ready': True}), flush=True)
                return 0
            finally:
                driver.quit()


if __name__ == '__main__':
    raise SystemExit(main())
