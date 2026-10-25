"""Attempt status is separate from immutable last valid financial reports."""
import json
from datetime import datetime, timezone
from pathlib import Path
from src.local_runner.publication_contract import digest_text


def record_attempt(root, work, symbol, stage, status, error=None, *, policy=None, store=None, started_at=None):
    root, work = Path(root), Path(work)
    work.mkdir(parents=True, exist_ok=True)
    path = work / 'attempt.json'
    previous = json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}
    if previous.get('status') == 'succeeded' and status != 'succeeded':
        return previous
    now = datetime.now(timezone.utc).isoformat()
    attempt = {'schema_version': 1, 'symbol': symbol,
               'attempt_id': digest_text(str(work.resolve())),
               'started_at': previous.get('started_at') or started_at or now, 'at': now,
               'status': status, 'stage': stage}
    if error is not None:
        attempt['error'] = {'type': type(error).__name__, 'message': str(error)[:2000]}
    committed = work / 'publication.committed.json'
    if committed.exists():
        attempt['committed_version'] = json.loads(committed.read_text(encoding='utf-8'))['version']
    path.write_text(json.dumps(attempt, ensure_ascii=False, indent=2), encoding='utf-8')
    latest = root / 'output' / symbol / 'latest_attempt.json'
    latest.parent.mkdir(parents=True, exist_ok=True)
    old = json.loads(latest.read_text(encoding='utf-8')) if latest.exists() else {}
    if old.get('started_at', '') <= attempt['started_at']:
        latest.write_text(json.dumps(attempt, ensure_ascii=False, indent=2), encoding='utf-8')
    if policy is None:
        policy_path = work / 'policy.json'
        if not policy_path.exists():
            policy_path = root / 'config' / 'codex_analysis.json'
        policy = json.loads(policy_path.read_text(encoding='utf-8')) if policy_path.exists() else {}
    if policy.get('latest_attempt_publication_enabled') is True:
        from src.local_runner.publication_store import GcsStore, json_text
        from src.local_runner.gcs_uploader import TEST_BUCKET
        store = store or GcsStore(TEST_BUCKET, auth=policy.get('publication_auth'))
        name = f'{symbol}/attempt.json'
        for retry in range(3):
            raw, generation = store.read(name)
            old = json.loads(raw) if raw else {}
            if old.get('started_at', '') > attempt['started_at']:
                break
            if (old.get('attempt_id') == attempt['attempt_id']
                    and old.get('status') == 'succeeded' and status != 'succeeded'):
                break
            try:
                store.write(name, json_text(attempt), generation)
                break
            except Exception:
                if retry == 2:
                    raise
    return attempt


def record_failure(root, work, symbol, stage, error, *, started_at=None):
    # A secondary status-upload error must not replace the original failure.
    try:
        return record_attempt(root, work, symbol, stage, 'failed', error, started_at=started_at)
    except Exception as exc:
        Path(work, 'attempt_publication_failure.json').write_text(
            json.dumps({'error': str(exc), 'original_error': str(error)}), encoding='utf-8')
        return None
