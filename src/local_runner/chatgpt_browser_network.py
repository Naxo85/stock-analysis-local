"""Passive, redacted evidence of Cloudflare challenges on ChatGPT UI requests."""
import threading
import time
from collections import deque
from datetime import datetime, timezone
from urllib.parse import urlsplit


class BrowserAccessObserver:
    def __init__(self):
        self._lock = threading.Lock()
        self._blocked = {}
        self._events = deque(maxlen=100)

    def record(self, response):
        url = urlsplit(response.get('url', ''))
        core = url.path in {
            '/backend-api/me', '/backend-api/models', '/backend-api/profiles/me',
        } or url.path.startswith((
            '/backend-api/accounts/', '/backend-api/gizmos/',
            '/backend-api/conversation', '/backend-api/sentinel/',
        ))
        if url.hostname != 'chatgpt.com' or not core:
            return
        status = response.get('status', 0)
        challenged = any(
            h.get('name', '').lower() == 'cf-mitigated'
            and h.get('value', {}).get('value', '').lower() == 'challenge'
            for h in response.get('headers', [])
        )
        with self._lock:
            self._events.append({
                'at': datetime.now(timezone.utc).isoformat(),
                'path': url.path, 'status': status,
                'cloudflare_challenge': challenged,
            })
            if status == 403 and challenged:
                self._blocked.setdefault(url.path, time.monotonic())
            elif 200 <= status < 300:
                self._blocked.pop(url.path, None)

    def blocked_paths(self, *, stable_seconds=0):
        now = time.monotonic()
        with self._lock:
            return sorted(path for path, since in self._blocked.items()
                          if now - since >= stable_seconds)

    def events(self):
        with self._lock:
            return list(self._events)


def install_access_observer(driver):
    capabilities = driver.capabilities
    if not isinstance(capabilities, dict) or not capabilities.get('webSocketUrl'):
        return
    from selenium.webdriver.common.bidi.common import command_builder
    from selenium.webdriver.common.bidi.network import NetworkEvent

    observer = BrowserAccessObserver()
    conn = driver.network.conn
    conn.add_callback(
        NetworkEvent('network.responseCompleted'),
        lambda event: observer.record(event.params.get('response', {})),
    )
    conn.execute(command_builder('session.subscribe', {'events': ['network.responseCompleted']}))
    driver._analysis_access_observer = observer


def blocked_paths(driver, *, stable_seconds=0):
    observer = getattr(driver, '_analysis_access_observer', None)
    if not isinstance(observer, BrowserAccessObserver):
        return []
    return observer.blocked_paths(stable_seconds=stable_seconds)


def access_events(driver):
    observer = getattr(driver, '_analysis_access_observer', None)
    return observer.events() if isinstance(observer, BrowserAccessObserver) else []


def raise_if_access_blocked(driver, *, stable_seconds=5):
    paths = blocked_paths(driver, stable_seconds=stable_seconds)
    if paths:
        raise RuntimeError('chatgpt_human_verification_required: api=' + ','.join(paths))
