import importlib.util,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
print('TOKENIZERS',json.dumps({x:bool(importlib.util.find_spec(x)) for x in ('tiktoken','tokenizers','transformers')}))
base=ROOT/'logs/sol_medium_test/20261023T163009901298/CLS'
wire=json.loads((base/'triage.input.json').read_text(encoding='utf-8'))
print('FILES',json.dumps({x:(base/x).stat().st_size for x in ('triage.input.json','instructions.md','schema.json')}))
sha=json.loads((ROOT/'logs/batch/2026-10-23/14-18-22/adaptive/CLS/triage.receipt.json').read_text(encoding='utf-8'))['instructions_sha256']
paths=list((ROOT/'.local/codex-analysis-workspace').rglob('triage-'+sha+'.md'))
print('LIVE_PREFIX',json.dumps([str(p) for p in paths]))
ref=wire['reference']
for key in ('catalysts','semantic_data','ibkr_recent_news','analyst_recent_actions'):
 v=ref.get(key);print('REF',key,type(v).__name__,list(v[0]) if isinstance(v,list) and v and isinstance(v[0],dict) else list(v)[:20] if isinstance(v,dict) else None)
print('CMP',json.dumps({k:list(v) if isinstance(v,dict) else type(v).__name__ for k,v in wire['comparison'].items()}))
print('LATEST_KEYS',json.dumps({k:len(json.dumps(v)) for k,v in (wire['comparison'].get('latest_published_review') or {}).items()}))
