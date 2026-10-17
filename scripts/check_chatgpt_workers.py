"""Check browser startup without sending any analysis request."""
import argparse
import ctypes
from ctypes import wintypes
import json
from pathlib import Path
import sys
import time
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.local_runner.chatgpt_browser_generator import (
    ChatGPTBrowserSession,
    ChatGPTBrowserSessionPool,
    _ensure_selenium_sol_high,
    _open_project_selenium,
    _stored_project_url,
    _write_selenium_trace,
)
from src.local_runner.command_worker import local_worker_lock
from check_firefox_background import windows_for_pid


def _sessions_for_check(pool, *, sequential=False, stagger_seconds=30):
    if not sequential:
        pool.preflight()
        yield from pool.sessions
        return
    # Yield one open session so the caller verifies project/model before the
    # next starts. Keep earlier sessions alive, as a real three-worker pool does.
    for index, session in enumerate(pool.sessions):
        if index:
            print(json.dumps({'stagger_seconds': stagger_seconds}), flush=True)
            time.sleep(stagger_seconds)
        print(json.dumps({'opening_worker': session.worker_id,
                          'at': datetime.now(timezone.utc).isoformat()}), flush=True)
        session.open()
        yield session


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verify-background', action='store_true')
    parser.add_argument('--verify-project', action='store_true',
                        help='Require the configured ChatGPT project to open without sending a prompt.')
    parser.add_argument('--worker-id', type=int, choices=(1, 2, 3),
                        help='Start and check only this worker; omit to check all three.')
    parser.add_argument('--verify-model', action='store_true',
                        help='Also confirm the configured model and reasoning without sending a prompt.')
    parser.add_argument('--sequential', action='store_true',
                        help='Open and fully check each worker before starting the next; stop on first failure.')
    parser.add_argument('--stagger-seconds', type=int, default=30,
                        help='Wait between sequential workers (default: 30; range: 0-60).')
    args = parser.parse_args()
    if not 0 <= args.stagger_seconds <= 60:
        parser.error('--stagger-seconds must be between 0 and 60')
    root = Path(__file__).resolve().parents[1]
    with local_worker_lock(root / 'logs' / 'command_worker.lock') as acquired:
        if not acquired:
            raise RuntimeError('another_command_worker_is_active')
        worker_ids = (args.worker_id,) if args.worker_id else (1, 2, 3)
        pool = ChatGPTBrowserSessionPool(
            root, worker_count=len(worker_ids), sessions=tuple(
                ChatGPTBrowserSession(root, worker_id=worker_id) for worker_id in worker_ids
            ),
        )
        try:
            print(json.dumps({'starting_workers': worker_ids,
                              'sequential': args.sequential}), flush=True)
            verify_project = args.verify_project or args.verify_model
            project_url = _stored_project_url(root) if verify_project else None
            if verify_project and not project_url:
                raise RuntimeError('chatgpt_project_url_not_configured')
            project_failures = []
            authenticated = 0
            for session in _sessions_for_check(
                pool, sequential=args.sequential, stagger_seconds=args.stagger_seconds,
            ):
                authenticated += 1
                if args.verify_background:
                    api = ctypes.WinDLL('user32', use_last_error=True)
                    api.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
                    api.EnumDesktopWindows.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.LPARAM]
                    api.IsWindowVisible.argtypes = [wintypes.HWND]
                    driver = session._driver
                    desktop = getattr(driver.service, 'desktop', None)
                    pid = driver.capabilities['moz:processID']
                    interactive = windows_for_pid(api, pid)
                    private = windows_for_pid(api, pid, desktop.handle) if desktop else []
                    visible = [hwnd for hwnd in interactive if api.IsWindowVisible(hwnd)]
                    if desktop:
                        assert not interactive, f'Worker {session.worker_id} appeared on user desktop'
                        assert private, f'Worker {session.worker_id} has no private desktop windows'
                    else:
                        assert not visible, f'Worker {session.worker_id} still has a visible window'
                    print(json.dumps({'worker': session.worker_id, 'interactive_windows': len(interactive),
                                      'visible_windows': len(visible), 'private_windows': len(private)}), flush=True)
                project_selected = verify_project
                if project_selected:
                    try:
                        _open_project_selenium(
                            session._driver,
                            project_url=project_url,
                            timeout_seconds=session.navigation_timeout_seconds,
                        )
                        if args.verify_model:
                            _ensure_selenium_sol_high(
                                session._driver, timeout_seconds=session.navigation_timeout_seconds,
                            )
                    except Exception as error:
                        project_failures.append(session.worker_id)
                        _write_selenium_trace(
                            session._driver,
                            diagnostic_dir=root / 'logs/browser_startup' / f'worker-{session.worker_id}',
                            symbol=f'worker-{session.worker_id}', attempt=0, status='failed',
                            stage='project', stage_timings={}, error=error, capture_page=True,
                        )
                        print(json.dumps({'worker': session.worker_id, 'project_ready': False,
                                          'error': str(error)}), flush=True)
                    else:
                        print(json.dumps({'worker': session.worker_id, 'project_ready': True,
                                          'model_verified': args.verify_model}), flush=True)
                if session.worker_id not in project_failures:
                    _write_selenium_trace(
                        session._driver,
                        diagnostic_dir=root / 'logs/browser_startup' / f'worker-{session.worker_id}',
                        symbol=f'worker-{session.worker_id}', attempt=0, status='ok',
                        stage='project' if project_selected else 'authenticate',
                        stage_timings={}, capture_page=True,
                    )
                if args.sequential and session.worker_id in project_failures:
                    break
            print(f'BROWSER PREFLIGHT: authenticated={authenticated}; '
                  f'failed_checks={project_failures}; disabled={pool.disabled_worker_ids}', flush=True)
            return 0 if authenticated == len(worker_ids) and not project_failures else 1
        finally:
            pool.close()


if __name__ == '__main__':
    raise SystemExit(main())
