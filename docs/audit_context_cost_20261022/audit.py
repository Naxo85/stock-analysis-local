"""Offline size/identity audit. Reads receipts, never calls a model or changes inputs."""
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from src.local_runner.adaptive_context import compact_json, unpack_model_context, pack_model_context, resolve_evidence
from copy import deepcopy

CURRENT = ROOT / 'logs/batch/2026-10-21/06-52-46/adaptive'
PREVIOUS = ROOT / 'logs/batch/2026-10-20/21-10-28/adaptive'

def common(a, b):
    for i, (x,y) in enumerate(zip(a,b)):
        if x != y: return i
    return min(len(a),len(b))

def long_strings(obj, path=''):
    if isinstance(obj,dict):
        for k,v in obj.items(): yield from long_strings(v,path+'/'+k.replace('~','~0').replace('/','~1'))
    elif isinstance(obj,list):
        for i,v in enumerate(obj): yield from long_strings(v,path+'/'+str(i))
    elif isinstance(obj,str) and len(obj)>200:
        yield path,obj

def table_pack(value):
    if isinstance(value,dict):return {k:table_pack(v) for k,v in value.items()}
    if not isinstance(value,list):return value
    converted=[table_pack(v) for v in value]
    if len(value)>=3 and all(isinstance(v,dict) for v in value):
        keys=sorted(value[0])
        if keys and all(sorted(v)==keys for v in value):
            candidate={'$table_columns':keys,'$table_rows':[[v[k] for k in keys] for v in converted]}
            if len(compact_json(candidate))+100<len(compact_json(converted)):return candidate
    return converted

def table_unpack(value):
    if isinstance(value,list):return [table_unpack(v) for v in value]
    if isinstance(value,dict):
        if set(value)=={'$table_columns','$table_rows'}:
            return [{k:table_unpack(v) for k,v in zip(value['$table_columns'],row)} for row in value['$table_rows']]
        return {k:table_unpack(v) for k,v in value.items()}
    return value

def main():
    totals=Counter(); sections=Counter(); detail=Counter(); rows=[]; duplicate_examples=[]
    for f in sorted(CURRENT.glob('*/triage.input.json')):
        text=f.read_text(encoding='utf-8'); packed=json.loads(text)
        obj=unpack_model_context(packed)
        totals['packed_chars']+=len(text)
        tabular=table_pack(packed)
        assert table_unpack(tabular)==packed
        totals['tabular_variant_chars']+=len(compact_json(tabular))
        totals['unpacked_chars']+=len(compact_json(obj))
        # Prototype ONLY: replace copied diff values by the existing exact pointers.
        variant=deepcopy(obj); removed=[]
        for group in ['since_current','since_full_sol']:
            market=variant.get('comparison',{}).get('deterministic',{}).get(group,{})
            for field in ['changes','capture_only_changes']:
                for index,change in enumerate(market.get(field,[])):
                    for side in ['previous','current']:
                        present=change[side+'_present']
                        value=resolve_evidence(obj,change[side+'_pointer']) if present else None
                        assert value==change[side], (f.parent.name,group,field,index,side)
                        removed.append((group,field,index,side,deepcopy(change.pop(side))))
        variant_text=compact_json(pack_model_context(variant))
        totals['pointer_diff_variant_chars']+=len(variant_text)
        combined=table_pack(json.loads(variant_text))
        assert table_unpack(combined)==json.loads(variant_text)
        totals['combined_variant_chars']+=len(compact_json(combined))
        totals['verified_diff_values']+=len(removed)
        restored=unpack_model_context(json.loads(variant_text))
        for group,field,index,side,value in removed:
            change=restored['comparison']['deterministic'][group][field][index]
            change[side]=deepcopy(resolve_evidence(restored,change[side+'_pointer'])) if change[side+'_present'] else None
        assert restored==obj
        for k,v in packed.items():
            sections[k]+=len(compact_json(v))
            if isinstance(v,dict):
                for kk,vv in v.items(): detail[k+'/'+kk]+=len(compact_json(vv))
        ss=defaultdict(list)
        for path,s in long_strings(packed): ss[s].append(path)
        saved=0
        for s,paths in ss.items():
            if len(paths)>1:
                # Optimistic upper bound: subtract a pointer marker AND map entry per alias.
                saved+=sum(max(0,len(compact_json(s))-len(compact_json({'$same_as':paths[0]}))-len(compact_json({p:paths[0]}))) for p in paths[1:])
                duplicate_examples.append({'ticker':f.parent.name,'chars':len(s),'copies':len(paths),'paths':paths})
        totals['string_alias_upper_bound_chars']+=saved
        old=PREVIOUS/f.parent.name/'triage.input.json'
        row={'ticker':f.parent.name,'chars':len(text),'pointer_diff_variant_chars':len(variant_text),'string_alias_upper_bound_chars':saved}
        if old.exists():
            oldtext=old.read_text(encoding='utf-8'); oldpacked=json.loads(oldtext); oldobj=unpack_model_context(oldpacked)
            row['existing_prefix_chars']=common(oldtext,text)
            row['unchanged_baseline_chars']=sum(len(compact_json(obj[k])) for k in ['reference','sol_reference'] if obj.get(k)==oldobj.get(k))
            row['unchanged_baseline_fields_chars']=sum(len(compact_json(v)) for k in ['reference','sol_reference'] for kk,v in obj.get(k,{}).items() if v==oldobj.get(k,{}).get(kk))
            row['same_anchor']=obj.get('sol_reference')==oldobj.get('sol_reference')
            row['same_current']=obj.get('reference')==oldobj.get('reference')
            current_base=compact_json(pack_model_context({k:obj[k] for k in ['sol_reference','reference']}))
            old_base=compact_json(pack_model_context({k:oldobj[k] for k in ['sol_reference','reference']}))
            row['independent_baseline_chars']=len(current_base)
            row['independent_baseline_prefix_chars']=common(old_base,current_base)
            dynamic=compact_json(pack_model_context({k:v for k,v in obj.items() if k not in ['reference','sol_reference']}))
            row['separate_blocks_chars']=len(current_base)+len(dynamic)
        receipt=json.loads(f.with_name('triage.receipt.json').read_text(encoding='utf-8'))
        row.update(usage=receipt['usage'],web=receipt.get('web_search_count',0),session_reused=receipt.get('session_reused'))
        rows.append(row)
    out={'units':'serialized Unicode characters; not model tokens. Receipts retain measured tokens.',
         'current':str(CURRENT.relative_to(ROOT)), 'previous':str(PREVIOUS.relative_to(ROOT)),
         'totals':dict(totals),'sections':dict(sections.most_common()),'detail':dict(detail.most_common()),
         'rows':rows,'largest_duplicate_strings':sorted(duplicate_examples,key=lambda x:x['chars']*(x['copies']-1),reverse=True)[:20]}
    target=Path(__file__).with_name('results.json');target.write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'totals':out['totals'],'sections':out['sections'],'detail_top15':dict(detail.most_common(15)),
          'pairs':sum('existing_prefix_chars'in r for r in rows),
          'same_anchor':sum(r.get('same_anchor',False) for r in rows),'same_current':sum(r.get('same_current',False) for r in rows),
          'baseline_chars':sum(r.get('unchanged_baseline_chars',0) for r in rows),
          'baseline_fields_chars':sum(r.get('unchanged_baseline_fields_chars',0) for r in rows),
          'prefix_chars':sum(r.get('existing_prefix_chars',0) for r in rows),
          'independent_baseline_chars':sum(r.get('independent_baseline_chars',0) for r in rows),
          'independent_baseline_prefix_chars':sum(r.get('independent_baseline_prefix_chars',0) for r in rows),
          'string_examples':out['largest_duplicate_strings'][:3]},ensure_ascii=False,indent=2))

if __name__=='__main__': main()
