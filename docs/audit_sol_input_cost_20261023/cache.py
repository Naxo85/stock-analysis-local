"""Sol21->Sol22 ordering experiment; no model calls or cache claims."""
from collections import Counter
from copy import deepcopy
from pathlib import Path
import json,sys
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from src.local_runner.adaptive_context import compact_json,unpack_model_context,pack_model_context
from src.local_runner.diff_transport import compact_diffs,VERSION

def ordered(obj):
    data=deepcopy(obj);data['_context_transport']=VERSION;data=compact_diffs(data)
    aliases={};seen={}
    def visit(value,path):
        if isinstance(value,(dict,list)):
            signature=compact_json(value);target=seen.get(signature)
            if target is not None:
                marker={'$same_as':target}
                if len(compact_json({path:target}))+len(compact_json(marker))<len(signature):
                    aliases[path]=target;return marker
            else:seen[signature]=path
            if isinstance(value,dict):return {k:visit(v,path+'/'+k.replace('~','~0').replace('/','~1')) for k,v in sorted(value.items())}
            return [visit(v,path+'/'+str(i)) for i,v in enumerate(value)]
        return deepcopy(value)
    keys=['sol_reference','reference','slim']+[k for k in sorted(data) if k not in ('sol_reference','reference','slim')]
    result={k:visit(data[k],'/'+k) for k in keys if k in data}
    if aliases:result['_context_aliases']=aliases
    assert unpack_model_context(result)=={**obj,'_context_transport':VERSION}
    return '{'+','.join(json.dumps(k)+':'+compact_json(v) for k,v in result.items())+'}'

def common(a,b):
    for i,(x,y) in enumerate(zip(a,b)):
        if x!=y:return i
    return min(len(a),len(b))

before=ROOT/'logs/batch/2026-10-21/06-52-46/adaptive'
after=ROOT/'logs/batch/2026-10-22/12-32-48/adaptive'
rows=[];totals=Counter();unmatched=[]
for i,file in enumerate(sorted(after.glob('*/triage.input.json'))):
    if i%15==0:print('SOL CACHE',i,flush=True)
    old=before/file.parent.name/'triage.input.json'
    if not old.exists():unmatched.append(file.parent.name);continue
    a_raw=old.read_text(encoding='utf-8');b_raw=file.read_text(encoding='utf-8')
    a=unpack_model_context(json.loads(a_raw));b=unpack_model_context(json.loads(b_raw))
    ra=json.loads(old.with_name('triage.receipt.json').read_text(encoding='utf-8'))
    rb=json.loads(file.with_name('triage.receipt.json').read_text(encoding='utf-8'))
    assert ra['model']==rb['model']=='gpt-6.1-sol' and ra['reasoning_effort']==rb['reasoning_effort']=='medium'
    normalized_first=compact_json(pack_model_context(compact_diffs({**a,'_context_transport':VERSION})))
    normalized_second=compact_json(pack_model_context(compact_diffs({**b,'_context_transport':VERSION})))
    first,second=ordered(a),ordered(b)
    row={'ticker':file.parent.name,'same_anchor':a.get('sol_reference')==b.get('sol_reference'),
        'same_instructions':ra['instructions_sha256']==rb['instructions_sha256'],
        'same_schema':ra['schema_sha256']==rb['schema_sha256'],
        'original_wire_chars':len(b_raw),'ordered_wire_chars':len(second),
        'normalized_default_wire_chars':len(normalized_second),
        'original_prefix_chars':common(a_raw,b_raw),
        'normalized_default_prefix_chars':common(normalized_first,normalized_second),
        'ordered_prefix_chars':common(first,second)}
    rows.append(row)
    for key,value in row.items():
        if isinstance(value,int):totals[key]+=value
out={'pairs':len(rows),'unmatched':unmatched,'totals':totals,'rows':rows,
    'limits':'Unicode chars only. Hypothetical layout, no eligible boundary/client support/TTL/hit guarantee. Whole JSON currently one stdin text message.'}
Path(__file__).with_name('cache.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in out.items() if k!='rows'},ensure_ascii=True,indent=2))
