"""Offline ordering experiment, no claims of backend cache retention/hits."""
from collections import Counter
from copy import deepcopy
import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from src.local_runner.adaptive_context import compact_json,unpack_model_context,resolve_evidence
from src.local_runner.diff_transport import compact_diffs,VERSION

def ordered(obj):
    data=deepcopy(obj);data['_context_transport']=VERSION
    data=compact_diffs(data)
    aliases={};seen={}
    def visit(value,path):
        if isinstance(value,(dict,list)):
            signature=compact_json(value)
            target=seen.get(signature)
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
    # Keep canonical encoding inside blocks; deliberate TOP-level order only.
    wire='{'+','.join(json.dumps(k)+':'+compact_json(v) for k,v in result.items())+'}'
    assert json.loads(wire)==result
    return wire

def common(a,b):
    for i,(x,y) in enumerate(zip(a,b)):
        if x!=y:return i
    return min(len(a),len(b))

now=ROOT/'logs/batch/2026-10-23/14-18-22/adaptive'
old=ROOT/'logs/batch/2026-10-22/12-32-48/adaptive'
rows=[];totals=Counter();unmatched=[]
for i,file in enumerate(sorted(now.glob('*/triage.input.json'))):
    if i%10==0:print('PREFIX',i,flush=True)
    other=old/file.parent.name/'triage.input.json'
    if not other.exists():unmatched.append(file.parent.name);continue
    a_raw=other.read_text(encoding='utf-8');b_raw=file.read_text(encoding='utf-8')
    a=unpack_model_context(json.loads(a_raw));b=unpack_model_context(json.loads(b_raw))
    first,second=ordered(a),ordered(b)
    row={'ticker':file.parent.name,'original_wire':len(b_raw),'ordered_wire':len(second),
         'original_prefix':common(a_raw,b_raw),'ordered_prefix':common(first,second),
         'same_anchor':a.get('sol_reference')==b.get('sol_reference')}
    rows.append(row)
    for key,value in row.items():
        if isinstance(value,int):totals[key]+=value
out={'units':'Unicode characters only','totals':totals,'rows':rows,'matched_pairs':len(rows),'unmatched':unmatched,
     'limits':'Pairs used different actual models and changed production prefixes. This is a hypothetical same-model layout experiment, not actual measured cache hits. No TTL assumption. All matched older/newer contexts exactly reconstruct under this layout.'}
Path(__file__).with_name('cache_layout.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in out.items() if k!='rows'},ensure_ascii=True,indent=2))
