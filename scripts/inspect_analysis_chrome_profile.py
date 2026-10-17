"""Read-only, redacted audit of the dedicated Chrome profile; no cookies or tokens."""
import json
import os
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.local_runner import chatgpt_browser_generator as browser
from check_background_processes import process_inventory


def read_json(path):
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except FileNotFoundError:
        return {}


def main():
    root = Path(__file__).resolve().parents[1]
    # Resolve configuration without creating/copying any profile directory.
    configured = os.environ.get('CHATGPT_BROWSER_PROFILE_DIR_WORKER_1') or os.environ.get('CHATGPT_BROWSER_PROFILE_DIR')
    profile = (Path(configured) if configured else root / browser.DEFAULT_PROFILE_PATH).resolve()
    personal = (Path(os.environ['LOCALAPPDATA']) / 'Google/Chrome/User Data').resolve()
    prefs = read_json(profile / 'Default/Preferences')
    secure = read_json(profile / 'Default/Secure Preferences')
    settings = secure.get('extensions', {}).get('settings', {}) or prefs.get('extensions', {}).get('settings', {})
    extensions = []
    for extension_id, config in settings.items():
        manifest = config.get('manifest', {})
        # Names and versions only; never extension settings, account IDs or URLs.
        extensions.append({'id': extension_id, 'name': manifest.get('name'),
                           'version': manifest.get('version'), 'state': config.get('state'),
                           'from_webstore': config.get('from_webstore')})
    roots = []
    for row in process_inventory(extra_names=('chrome.exe', 'msedge.exe')):
        if row['name'] not in ('chrome.exe', 'msedge.exe') or '--type=' in row['command']:
            continue
        match = re.search(r'--user-data-dir=(?:"([^"]+)"|(\S+))', row['command'])
        selected = Path(match.group(1) or match.group(2)).resolve() if match else None
        roots.append({'pid': row['pid'], 'name': row['name'],
                      'dedicated_profile': selected == profile,
                      'explicit_profile': selected is not None,
                      'command_readable': bool(row['command'])})
    print(json.dumps({
        'dedicated_path': str(profile), 'personal_path': str(personal),
        'same_directory': profile == personal or (
            profile.exists() and personal.exists() and os.path.samefile(profile, personal)),
        'google_account_entries': len(prefs.get('account_info', [])),
        'sync': {key: prefs.get('sync', {}).get(key) for key in (
            'requested', 'keep_everything_synced', 'has_setup_completed')},
        'extension_count': len(extensions), 'extensions': extensions,
        'browser_root_processes': roots,
    }, indent=2))


if __name__ == '__main__':
    main()
