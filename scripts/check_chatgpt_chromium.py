"""Check the existing dedicated Chromium profile; never log in or submit prompts."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.local_runner import chatgpt_browser_generator as browser
from src.local_runner.chatgpt_browser_network import BrowserAccessObserver
from src.local_runner.command_worker import local_worker_lock


def ui_state(page):
    return page.evaluate("""() => {
        const norm = (document.body?.innerText || '').toLowerCase();
        const visible = e => !!e.getClientRects().length;
        return {
            login: [...document.querySelectorAll('button,a')].some(e =>
                visible(e) && /^(log in|iniciar sesi[oó]n)$/i.test(e.textContent.trim())),
            account_error: /no hemos podido cargar tu cuenta|unable to load your account|we couldn't load your account/.test(norm),
            loading: /cargando perfil|loading profile/.test(norm),
            projects: [...document.querySelectorAll('[data-app-action-sidebar-project-id]')]
                .map(e => e.getAttribute('data-app-action-sidebar-project-id')),
            human_challenge: [...document.querySelectorAll('iframe[src*="challenges.cloudflare.com"]')]
                .some(visible) || (typeof window._cf_chl_opt !== 'undefined'),
        };
    }""")


def wait_ready(page, observer, expected_id, *, project_url=None, timeout=60):
    deadline = time.monotonic() + timeout
    retry_after = 0
    reloads = 0
    login_since = None
    while time.monotonic() < deadline:
        state = ui_state(page)
        now = time.monotonic()
        if state['human_challenge']:
            raise RuntimeError('chatgpt_human_verification_required')
        if state['login']:
            login_since = login_since or now
            if now - login_since >= 3:
                raise RuntimeError('chatgpt_login_required: dedicated_chromium_profile')
        else:
            login_since = None
        if state['account_error'] and reloads < 3 and now >= retry_after:
            for label in ('Volver a cargar', 'Reload', 'Retry', 'Try again', 'Reintentar'):
                button = page.get_by_role('button', name=label, exact=True)
                if button.count() and button.first.is_visible():
                    button.first.click(timeout=3000)
                    reloads += 1
                    retry_after = time.monotonic() + 10
                    print(json.dumps({'account_reload': reloads}), flush=True)
                    break
        if now >= retry_after and observer.blocked_paths(stable_seconds=5):
            raise RuntimeError('chatgpt_human_verification_required: api=' + ','.join(observer.blocked_paths()))
        if (not state['login'] and not state['loading'] and not state['account_error']
                and not observer.blocked_paths() and browser._prompt_visible(page)
                and expected_id in state['projects']
                and (not project_url or browser._same_chatgpt_project(page.url, project_url))):
            return
        page.wait_for_timeout(500)
    raise RuntimeError('chatgpt_chromium_not_ready')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--headless', action='store_true')
    args = parser.parse_args()
    from playwright.sync_api import sync_playwright

    root = Path(__file__).resolve().parents[1]
    profile = browser._profile_dir(root, engine='chromium', worker_id=1)
    project_url = browser._stored_project_url(root)
    if not project_url:
        raise RuntimeError('chatgpt_project_url_not_configured')
    expected_id = browser._chatgpt_project_id(project_url)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    directory = root / 'logs/browser_startup/chromium'
    directory.mkdir(parents=True, exist_ok=True)
    observer = BrowserAccessObserver()
    stage = 'launch'
    result = {'status': 'failed', 'profile': str(profile), 'headed': not args.headless}
    with local_worker_lock(root / 'logs/command_worker.lock') as acquired:
        if not acquired:
            raise RuntimeError('another_command_worker_is_active')
        with browser._exclusive_browser_lock(browser._lock_path(root, worker_id=1), timeout_seconds=0):
            with sync_playwright() as manager:
                context = None
                page = None
                try:
                    executable = browser._browser_executable()
                    result['executable'] = executable
                    print(json.dumps({'browser': executable, 'profile': str(profile)}), flush=True)
                    context = manager.chromium.launch_persistent_context(
                        user_data_dir=str(profile), executable_path=executable,
                        headless=args.headless, viewport={'width': 1440, 'height': 1000},
                        accept_downloads=False, args=(
                            '--disable-background-timer-throttling',
                            '--disable-extensions', '--disable-sync',
                        ),
                    )
                    def on_response(response):
                        observer.record({'url': response.url, 'status': response.status,
                                         'headers': [{'name': 'cf-mitigated', 'value': {
                                             'value': response.headers.get('cf-mitigated', '')}}]})
                    context.on('response', on_response)
                    page = context.pages[0] if context.pages else context.new_page()
                    stage = 'authenticate'
                    page.goto(browser.CHATGPT_URL, wait_until='domcontentloaded', timeout=60000)
                    wait_ready(page, observer, expected_id)
                    print('CHROMIUM: account_ready', flush=True)
                    stage = 'project'
                    page.goto(project_url, wait_until='domcontentloaded', timeout=60000)
                    wait_ready(page, observer, expected_id, project_url=project_url)
                    print('CHROMIUM: project_ready', flush=True)
                    stage = 'model'
                    browser._ensure_playwright_sol_high(page, timeout_seconds=30)
                    result['status'] = 'ok'
                    print('CHROMIUM: model_verified', flush=True)
                except Exception as error:
                    result['error'] = str(error)
                    print(json.dumps({'stage': stage, 'error': str(error)}), flush=True)
                finally:
                    result.update(stage=stage, events=observer.events(), blocked=observer.blocked_paths())
                    if page is not None:
                        try:
                            result['ui'] = ui_state(page)
                            result['url'] = page.url.split('?')[0]
                            page.screenshot(path=str(directory / (stamp + '.png')))
                        except Exception as error:
                            result['capture_error'] = str(error)
                    (directory / (stamp + '.json')).write_text(json.dumps(result, indent=2), encoding='utf-8')
                    print(json.dumps({'trace': str(directory / (stamp + '.json'))}), flush=True)
                    if context:
                        context.close()
    return 0 if result['status'] == 'ok' else 1


if __name__ == '__main__':
    raise SystemExit(main())
