"""Read-only adversarial source41 probes against frozen local bars."""
from copy import deepcopy
from datetime import datetime
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path = [entry for entry in sys.path if Path(entry).resolve() != Path(__file__).parent]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'tests'))
from test_support_resistances_slim_evidence import raw, slim


def original(ticker):
    path = ROOT / 'logs/batch/2026-10-18/09-08-40/adaptive' / ticker / 'input.json'
    inp = json.loads(path.read_text(encoding='utf-8'))
    for file in (ROOT / 'data/technical_archive' / ticker).glob('*.json'):
        archive = json.loads(file.read_text(encoding='utf-8'))
        if archive['snapshot_at'] == inp['slim']['as_of']:
            return inp, archive['daily']['rows']
    raise AssertionError('matching archive absent')


def observe(inp, rows, request):
    return raw._observe_support_origins([request], rows,
        inp['slim']['technicals']['atr10'], datetime.fromisoformat(inp['slim']['as_of']),
        inp['slim']['volume_profile'])[0][0]


if __name__ == '__main__':
    for ticker, request in [('WDC', {'type': 'gap_up_lower', 'level': 312.2, 'date': '2026-04-08'}),
                           ('CLS', {'type': 'range_bottom_3_6m', 'level': 290.88,
                                    'date': '2026-08-19', 'touches': 2})]:
        inp, rows = original(ticker)
        baseline = observe(inp, rows, request)
        richer = dict(request, origin_identity=baseline['source_record']['meta']['origin_identity'])
        changed = deepcopy(rows)
        # A remote missing session preserves the exact formation but makes some
        # following-history claims and forward-session counts incomplete.
        after = max(richer['origin_identity']['confirmation_dates'])
        index = next(i for i, row in enumerate(changed) if row['date'] > after)
        removed = changed.pop(index)
        mutated = observe(inp, changed, richer)
        meta = mutated['source_record']['meta']
        reaction = meta.get('historical_reaction') or {}
        paths = reaction.get('path_evidence') or {}
        print(json.dumps({'ticker': ticker, 'removed_session': removed['date'],
            'status': mutated['status'], 'filled': meta.get('filled'),
            'gap_history_status': meta.get('gap_history_status'),
            'reaction': {key: reaction.get(key) for key in ('status', 'reason',
                'observation_policy', 'forward_sessions', 'excluded_incomplete_data_test_count')},
            'path_events': paths.get('events')}, ensure_ascii=False))
