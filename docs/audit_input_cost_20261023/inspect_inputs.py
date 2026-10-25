"""Read-only inventory of admitted input payloads; no model/auth/network calls."""
from collections import Counter
import hashlib,importlib.util,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from src.local_runner.adaptive_context import compact_json,unpack_model_context

def size(v):return len(compact_json(v))
def walk(v,p='',depth=0):
    yield p,v
    if isinstance(v,dict):
        for k,c in v.items():yield from walk(c,p+'/'+k,depth+1)
    elif isinstance(v,list) and depth<4:
        for i,c in enumerate(v):yield from walk(c,p+'/'+str(i),depth+1)

batch=ROOT/'logs/batch/2026-10-23/14-18-22/adaptive'
sections=Counter();details=Counter();rows=[];instructions={};hashes={}
for file in sorted(batch.glob('*/triage.input.json')):
    raw=file.read_text(encoding='utf-8');packed=json.loads(raw)
    receipt=json.loads(file.with_name('triage.receipt.json').read_text(encoding='utf-8'))
    assert hashlib.sha256(file.read_bytes()).hexdigest()==receipt['input_sha256']
    hashes[str(file)]=receipt['input_sha256']
    for k,v in packed.items():
        sections[k]+=size(v)
        if isinstance(v,dict):
            for kk,vv in v.items():details[k+'/'+kk]+=size(vv)
    row={'ticker':file.parent.name,'wire_chars':len(raw),'sections':{k:size(v) for k,v in packed.items()},
         'usage':receipt['usage'],'web':receipt.get('web_search_count',0)}
    rows.append(row)
    instructions[receipt['instructions_sha256']]=str(file.parent/'triage_instructions.md')
sample=ROOT/'logs/sol_medium_test/20261023T163009901298'
sample_rows={}
for symbol in ('AMD','CLS','IREN'):
    p=json.loads((sample/symbol/'triage.input.json').read_text(encoding='utf-8'))
    sample_rows[symbol]={'sections':{k:size(v) for k,v in p.items()},'top_paths':
        sorted([{'path':path,'chars':size(v)} for path,v in walk(p) if path.count('/') in (2,3)],key=lambda v:v['chars'],reverse=True)[:30]}
data={'units':'Unicode chars, not tokenizer/model tokens','sections':dict(sections.most_common()),
      'details':dict(details.most_common()),'rows':rows,'samples':sample_rows,'hashes':hashes,
      'instruction_hashes':instructions,
      'tokenizer_modules':{name:bool(importlib.util.find_spec(name)) for name in ('tiktoken','tokenizers','transformers')}}
Path(__file__).with_name('inventory.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'sections':data['sections'],'details_top20':dict(details.most_common(20)),
    'sample_paths':sample_rows,'tokenizers':data['tokenizer_modules'],'instructions':instructions},ensure_ascii=True,indent=2))
