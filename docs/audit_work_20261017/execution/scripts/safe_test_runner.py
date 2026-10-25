"""Run pytest offline; external sockets and unapproved child processes fail closed.

Usage: python -B safe_test_runner.py [--allow-processes allowlist.json] -- tests/...
Optional allowlist: JSON list of exact command arrays (not regexes/prefixes).
No cloud/model CLI can be allowed. Only explicitly authorized local test commands.
"""
import sys, socket, subprocess, json, shlex
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'gcp_services/stock_controller/src'))
args = sys.argv[1:]
allowed = []
if args[:1] == ['--allow-processes']:
    allowed = json.loads(Path(args[1]).read_text(encoding='utf-8'))
    args = args[2:]
if args[:1] == ['--']:
    args = args[1:]
original_popen = subprocess.Popen
def popen(command, *a, **kw):
    value = [str(x) for x in command] if isinstance(command, (tuple, list)) else [str(command)]
    forbidden = ('gcloud', 'gsutil', 'codex', 'curl', 'wget')
    if kw.get('shell') or any(any(word in Path(part).name.lower() for word in forbidden) for part in value):
        raise AssertionError('EXTERNAL_PROCESS_FORBIDDEN: ' + repr(value[:2]))
    if value not in allowed:
        raise AssertionError('UNAPPROVED_PROCESS_FORBIDDEN: ' + repr(value[:2]))
    return original_popen(command, *a, **kw)
def connect(sock, address):
    if isinstance(address, tuple) and address[0] in ('127.0.0.1', '::1', 'localhost'):
        return original_connect(sock, address)
    raise AssertionError('EXTERNAL_SOCKET_FORBIDDEN: ' + repr(address))
original_connect = socket.socket.connect
def connect_ex(sock, address):
    connect(sock, address)
    return 0
with patch.object(socket.socket, 'connect', connect), patch.object(socket.socket, 'connect_ex', connect_ex), patch.object(subprocess, 'Popen', popen):
    import pytest
    raise SystemExit(pytest.main(['-q', '-p', 'no:cacheprovider', *args]))
