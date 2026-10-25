"""Generation-checked portfolio state shared by the menu and the local worker."""
import json
from pathlib import Path
from src.local_runner.publication_store import GcsStore, json_text

PORTFOLIO_OBJECT = 'runtime/config/portfolio.json'
LAYOUT_OBJECT = 'runtime/config/market_sheet_layout.json'


def runtime_store(bucket='stock-analysis-system-naxo85'):
    policy = json.loads((Path(__file__).resolve().parents[2] / 'config/codex_analysis.json').read_text(encoding='utf-8'))
    return GcsStore(bucket, auth=policy.get('publication_auth'))


def read_json(store, name):
    raw, generation = store.read(name)
    if raw is None:
        raise RuntimeError('tracking_runtime_state_missing:' + name)
    return json.loads(raw), generation


def is_conflict(error):
    from google.api_core.exceptions import PreconditionFailed
    return isinstance(error, PreconditionFailed)


def update_json(store, name, change):
    for _ in range(5):
        payload, generation = read_json(store, name)
        updated = change(payload)
        try:
            store.write(name, json_text(updated), generation)
            return updated
        except Exception as exc:
            if not is_conflict(exc):
                raise
    raise RuntimeError('tracking_concurrent_update:' + name)
