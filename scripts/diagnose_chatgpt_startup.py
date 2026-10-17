"""Observe one real Firefox profile through startup, without sending a message."""
import argparse
import json
from pathlib import Path
import sys
import time
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.local_runner import chatgpt_browser_generator as browser
from src.local_runner.command_worker import local_worker_lock


def observe_responses(driver, failures):
    from selenium.webdriver.common.bidi.common import command_builder
    from selenium.webdriver.common.bidi.network import NetworkEvent

    conn = driver.network.conn
    def received(event):
        response = event.params.get('response', {})
        status = response.get('status', 0)
        url = urlsplit(response.get('url', ''))
        if status < 400 or url.hostname != 'chatgpt.com':
            return
        allowed = {'content-type', 'cf-mitigated', 'server', 'cf-ray'}
        headers = {h['name'].lower(): h['value'].get('value', '')
                   for h in response.get('headers', []) if h['name'].lower() in allowed}
        failure = {'path': url.path, 'status': status, 'headers': headers}
        if not any(f['path'] == failure['path'] and f['status'] == status for f in failures):
            failures.append(failure)
            print(json.dumps({'response_failure': failure}), flush=True)
    conn.add_callback(NetworkEvent('network.responseCompleted'), received)
    conn.execute(command_builder('session.subscribe', {'events': ['network.responseCompleted']}))


def state(driver):
    # Only UI readiness and resource metadata; never cookies, request headers,
    # response bodies or URL query strings containing credentials.
    return driver.execute_script("""
        const body = document.body?.innerText || '';
        const norm = body.toLowerCase();
        const resources = performance.getEntriesByType('resource')
            .filter(r => ['fetch', 'xmlhttprequest'].includes(r.initiatorType))
            .map(r => {const u = new URL(r.name); return {
                host: u.host, path: u.pathname, status: r.responseStatus ?? null,
                duration_ms: Math.round(r.duration), bytes: r.transferSize
            }});
        return {
            ready_state: document.readyState, visibility: document.visibilityState,
            account_error: norm.includes('no hemos podido cargar tu cuenta') ||
                           norm.includes('unable to load your account'),
            loading_profile: norm.includes('cargando perfil') || norm.includes('loading profile'),
            projects: Array.from(document.querySelectorAll('[data-app-action-sidebar-project-id]'))
                .map(e => ({id: e.dataset.appActionSidebarProjectId,
                           label: e.dataset.appActionSidebarProjectLabel})),
            resources: resources.slice(-60)
        };
    """)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--worker-id', type=int, choices=(1, 2, 3), default=1)
    parser.add_argument('--headed', action='store_true')
    parser.add_argument('--timeout', type=int, default=90)
    parser.add_argument('--check-model', action='store_true')
    parser.add_argument('--hide-after-ready', action='store_true')
    parser.add_argument('--observe-network', action='store_true')
    parser.add_argument('--reload-once', action='store_true')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    session = browser.ChatGPTBrowserSession(root, worker_id=args.worker_id, browser_engine='firefox')
    project_url = browser._stored_project_url(root)
    if not project_url:
        raise RuntimeError('chatgpt_project_url_not_configured')
    events = []
    response_failures = []
    driver = None
    failure = None
    stage = 'launch'
    directory = root / 'logs/browser_startup' / f'worker-{args.worker_id}'
    with local_worker_lock(root / 'logs/command_worker.lock') as acquired:
        if not acquired:
            raise RuntimeError('another_command_worker_is_active')
        with browser._exclusive_browser_lock(session.lock_path, timeout_seconds=1):
            try:
                driver = browser._launch_firefox(
                    session.profile_dir, headed=args.headed, enable_bidi=args.observe_network,
                )
                driver.set_page_load_timeout(args.timeout)
                if args.observe_network:
                    observe_responses(driver, response_failures)
                stage = 'home'
                started = time.monotonic()
                driver.get(browser.CHATGPT_URL)
                last_brief = None
                reloaded = False
                while time.monotonic() - started < args.timeout:
                    snapshot = state(driver)
                    snapshot['elapsed_seconds'] = round(time.monotonic() - started, 1)
                    snapshot['challenge'] = browser._selenium_human_verification_visible(driver)
                    snapshot['prompt'] = browser._selenium_prompt_visible(driver)
                    if not events or snapshot['resources'] != events[-1]['resources'] or snapshot['projects'] != events[-1]['projects']:
                        events.append(snapshot)
                    brief = {k: snapshot[k] for k in ('visibility', 'account_error', 'loading_profile', 'projects', 'challenge', 'prompt')}
                    if brief != last_brief:
                        print(json.dumps({'worker': args.worker_id, **brief}), flush=True)
                        last_brief = brief
                    if snapshot['challenge'] and snapshot['elapsed_seconds'] >= 15:
                        raise RuntimeError('chatgpt_human_verification_required')
                    browser._raise_if_browser_access_blocked(driver)
                    if args.reload_once and not reloaded and snapshot['account_error'] and snapshot['elapsed_seconds'] >= 15:
                        reloaded = True
                        browser._click_selenium_retry(driver)
                    expected_id = browser._chatgpt_project_id(project_url)
                    if snapshot['prompt'] and any(p['id'] == expected_id for p in snapshot['projects']):
                        break
                    time.sleep(2)
                else:
                    raise RuntimeError('chatgpt_account_load_failed' if snapshot['account_error'] else 'chatgpt_sidebar_not_ready')
                stage = 'project'
                browser._open_project_selenium(driver, project_url=project_url, timeout_seconds=45)
                print(json.dumps({'worker': args.worker_id, 'project_ready': True}), flush=True)
                if args.check_model:
                    stage = 'model'
                    browser._ensure_selenium_sol_high(driver, timeout_seconds=45)
                    print(json.dumps({'worker': args.worker_id, 'model_ready': True}), flush=True)
                if args.hide_after_ready:
                    stage = 'hide'
                    if not browser._hide_selenium_firefox_window(driver):
                        raise RuntimeError('firefox_hide_failed')
                    time.sleep(15)
                    if not browser._selenium_project_ready(driver, project_url):
                        raise RuntimeError('chatgpt_project_lost_after_hide')
                    print(json.dumps({'worker': args.worker_id, 'hidden_project_ready': True}), flush=True)
            except Exception as exc:
                failure = exc
                print(json.dumps({'worker': args.worker_id, 'stage': stage, 'error': str(exc)}), flush=True)
            finally:
                if driver is not None:
                    try:
                        trace = browser._write_selenium_trace(
                            driver, diagnostic_dir=directory, symbol=f'worker-{args.worker_id}',
                            attempt=0, status='failed' if failure else 'ok', stage=stage,
                            stage_timings={}, error=failure, capture_page=True,
                        )
                        trace.with_suffix('.startup.json').write_text(json.dumps(events, indent=2), encoding='utf-8')
                        trace.with_suffix('.network.json').write_text(json.dumps(response_failures, indent=2), encoding='utf-8')
                        print(json.dumps({'trace': str(trace)}), flush=True)
                    finally:
                        driver.quit()
    return 1 if failure else 0


if __name__ == '__main__':
    raise SystemExit(main())
