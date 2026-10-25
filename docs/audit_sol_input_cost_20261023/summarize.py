"""Print selected recorded evidence; no model calls or financial mutations."""
from pathlib import Path
import json

HERE = Path(__file__).resolve().parent
data = json.loads((HERE / 'results.json').read_text(encoding='utf-8'))
print('Original files unchanged:', data['original_files_unchanged'])
for day, run in data['runs'].items():
    print(day)
    print(json.dumps({k: run[k] for k in ('summary', 'recorded_groups', 'calculations',
        'no_web_reviews', 'schema_checker_equivalence')}, indent=2))
    print('Top physical JSON sections:', sorted(run['sections'].items(), key=lambda x: -x[1])[:10])
    print('Top nested sections:', sorted(run['details'].items(), key=lambda x: -x[1])[:15])
cache = json.loads((HERE / 'cache.json').read_text(encoding='utf-8'))
print('Cache layout experiment:', json.dumps({k:v for k,v in cache.items() if k!='rows'}, indent=2))
