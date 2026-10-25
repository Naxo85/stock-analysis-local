"""Check final report evidence against originals, receipts and recorded ledger."""
from collections import Counter
from pathlib import Path
import hashlib
import json

HERE = Path(__file__).resolve().parent
data = json.loads((HERE / 'results.json').read_text(encoding='utf-8'))
assert len(data['hashes']) == data['original_files_unchanged'] == 460
for path, expected in data['hashes'].items():
    assert hashlib.sha256(Path(path).read_bytes()).hexdigest() == expected, path
counts = Counter()
for run in data['runs'].values():
    for kind, effort in [('triage', 'medium'), ('report', 'high')]:
        usage = Counter()
        receipts = list((Path(run['batch']) / 'adaptive').glob('*/' + kind + '.receipt.json'))
        assert len(receipts) == run['recorded_groups'][kind]['calls']
        for path in receipts:
            receipt = json.loads(path.read_text(encoding='utf-8'))
            assert receipt['model'] == 'gpt-6.1-sol'
            assert receipt['reasoning_effort'] == effort
            usage.update(receipt['usage'])
            counts[kind] += 1
        assert dict(usage) == run['recorded_groups'][kind]['usage'], (kind, usage)
cache = json.loads((HERE / 'cache.json').read_text(encoding='utf-8'))
assert cache['pairs'] == 46 and cache['totals']['same_anchor'] == 43
assert cache['totals']['same_instructions'] == cache['totals']['same_schema'] == 46
print('PASS: 460 originals unchanged; usage matches receipts;', dict(counts), '; 46 Sol cache pairs.')
