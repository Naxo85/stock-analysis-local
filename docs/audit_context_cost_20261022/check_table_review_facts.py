import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from src.local_runner.adaptive_context import unpack_model_context
d=unpack_model_context(json.loads((ROOT/'logs/batch/2026-10-21/06-52-46/adaptive/TSLA/triage.input.json').read_text(encoding='utf-8')))
for row in d['news']['items'][:3]:
 print('FIELDS',json.dumps({k:len(v) if isinstance(v,str) else v for k,v in row.items()},ensure_ascii=True))
for i,row in enumerate(d['news']['items'][:15]):
 print(json.dumps({'id':'n'+str(i+1),'headline':row.get('headline'),'title':row.get('title'),'published_at':row.get('published_at')},ensure_ascii=True))
for row in d['slim']['price_history']['sessions']:
 if row['date']>='2026-10-15':print(json.dumps(row,ensure_ascii=True))
