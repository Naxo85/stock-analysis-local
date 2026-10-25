"""Deeper offline checks: schema mutations, snapshot codecs and cache tradeoff.

Study artefacts only. No production imports this module or its prototypes.
"""
from collections import Counter
from copy import deepcopy
from pathlib import Path
import hashlib, json, sys
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT/'docs/audit_input_cost_20261023'))
sys.path.insert(0, str(ROOT/'docs/audit_sol_input_cost_20261023'))
from prototypes import compact, delta, apply, snapshot_unpack, SNAPSHOTS, factor_schema, expand_factored
from src.local_runner.adaptive_context import unpack_model_context, pack_model_context
from src.local_runner.diff_transport import compact_diffs, VERSION
from src.local_runner.semantic_report import check_schema

HERE = Path(__file__).resolve().parent
RUNS = {'2026-10-21':'06-52-46', '2026-10-22':'12-32-48'}
def wire(v): return json.dumps(v, ensure_ascii=False, separators=(',', ':'), allow_nan=False)
def valid(v,s):
    try: check_schema(v,s); return True
    except ValueError: return False
def set_at(value,path,new,remove=False):
    out=deepcopy(value); parent=out
    for key in path[:-1]: parent=parent[key]
    if not path: return deepcopy(new)
    if remove: del parent[path[-1]]
    else: parent[path[-1]]=deepcopy(new)
    return out
def mutants(value,path=()):
    if isinstance(value,dict):
        yield ('extra', path+('__unexpected_audit_field__',), True, False)
        for key,child in value.items():
            yield ('missing',path+(key,),None,True)
            yield from mutants(child,path+(key,))
    elif isinstance(value,list):
        yield ('array_type',path,{},False)
        for i,child in enumerate(value): yield from mutants(child,path+(i,))
    else:
        wrong=0 if type(value) is bool else False if type(value) in (int,float) else 123 if isinstance(value,str) else {}
        yield ('scalar_type',path,wrong,False)

def ordered_pack(obj):
    """Same stable-layout candidate as cache.py, returning the actual packed dict."""
    data=compact_diffs({**deepcopy(obj),'_context_transport':VERSION})
    aliases={};seen={}
    def visit(value,path):
        if isinstance(value,(dict,list)):
            signature=compact(value);target=seen.get(signature)
            if target is not None:
                marker={'$same_as':target}
                if len(compact({path:target}))+len(compact(marker))<len(signature):
                    aliases[path]=target;return marker
            else:seen[signature]=path
            if isinstance(value,dict):return {k:visit(v,path+'/'+k.replace('~','~0').replace('/','~1')) for k,v in sorted(value.items())}
            return [visit(v,path+'/'+str(i)) for i,v in enumerate(value)]
        return deepcopy(value)
    keys=['sol_reference','reference','slim']+[k for k in sorted(data) if k not in ('sol_reference','reference','slim')]
    out={k:visit(data[k],'/'+k) for k in keys if k in data}
    if aliases:out['_context_aliases']=aliases
    return out

def snapshot_variant(packed, *, arrays=True, preserve_anchor=False):
    def patch(old,new):
        if not arrays and isinstance(old,list) and isinstance(new,list):
            return None if compact(old)==compact(new) else {'v':deepcopy(new)}
        if arrays: return delta(old,new)
        if compact(old)==compact(new):return None
        replace={'v':deepcopy(new)}
        if not isinstance(old,dict) or not isinstance(new,dict):return replace
        changes={k:({'v':deepcopy(v)} if k not in old else patch(old[k],v)) for k,v in new.items()}
        candidate={'o':{k:v for k,v in changes.items() if v is not None}}
        removed=sorted(set(old)-set(new))
        if removed:candidate['d']=removed
        return candidate if len(compact(candidate))<len(compact(replace)) else replace
    result=deepcopy(packed);records=[]
    for parts in SNAPSHOTS:
        if preserve_anchor and parts[0]=='sol_reference':continue
        parent=result
        try:
            for key in parts[:-1]:parent=parent[key]
            value=parent[parts[-1]]
        except (KeyError,TypeError):continue
        if not isinstance(value,dict) or '$same_as' in value:continue
        node={'$snapshot_base':'/slim','$snapshot_delta':patch(packed['slim'],value)}
        if len(compact(node))<len(compact(value)):
            records.append({'path':'/'+('/'.join(parts)),'before':len(compact(value)),'after':len(compact(node))})
            parent[parts[-1]]=node
    # Snapshot object-key order is not a financial datum; preserve JSON values,
    # numeric spelling/types, array order and presence. Schema order IS checked.
    assert compact(snapshot_unpack(result))==compact(packed)
    return result,records

def common(a,b):
    for i,(x,y) in enumerate(zip(a,b)):
        if x!=y:return i
    return min(len(a),len(b))

out={'runs':{},'cache_tradeoff':{},'schema':{},'boundaries':{},'limits':'Chars only; no model interpretation, tokenizer or cache hits measured.'}
unique_schemas={};layout_runs={};hashes={}
old_results=json.loads((HERE.parent/'results.json').read_text(encoding='utf-8'))
for day,hour in RUNS.items():
    summary=Counter();rows=[];layouts={};mutations=Counter();session_counts={}
    for i,file in enumerate(sorted((ROOT/'logs/batch'/day/hour/'adaptive').glob('*/triage.input.json'))):
        if i%15==0: print('FOLLOWUP',day,i,flush=True)
        hashes[str(file)]=hashlib.sha256(file.read_bytes()).hexdigest()
        packed=json.loads(file.read_text(encoding='utf-8'));obj=unpack_model_context(packed)
        opt_obj={**deepcopy(obj),'_context_transport':VERSION}
        existing=pack_model_context(compact_diffs(opt_obj))
        stable=ordered_pack(obj)
        assert unpack_model_context(stable)==opt_obj
        versions={'normalized':existing,'stable':stable};patch_records={}
        for label,base,arrays,anchor in [('delta_arrays',existing,True,False),
                ('delta_whole_arrays',existing,False,False),('stable_delta_all',stable,True,False),
                ('stable_delta_preserve_anchor',stable,True,True)]:
            versions[label],patch_records[label]=snapshot_variant(base,arrays=arrays,preserve_anchor=anchor)
            assert unpack_model_context(snapshot_unpack(versions[label]))==opt_obj
        lengths={label:len(wire(value)) for label,value in versions.items()}
        for label,n in lengths.items():summary[label]+=n
        layouts[file.parent.name]={label:wire(v) for label,v in versions.items() if label.startswith('stable')}
        receipt=json.loads(file.with_name('triage.receipt.json').read_text(encoding='utf-8'))
        usage=receipt['usage'];session='reused' if receipt.get('session_reused') else 'new'
        if not receipt.get('web_search_count'):
            group=session_counts.setdefault(session,Counter())
            group.update(calls=1, input_tokens=usage['input_tokens'],cached_input_tokens=usage['cached_input_tokens'],
                zero_cache=int(usage['cached_input_tokens']==0),history_cleared=int(bool(receipt.get('session_history_cleared'))))
        schema=json.loads(file.with_name('triage.schema.json').read_text(encoding='utf-8'))
        key=hashlib.sha256(wire(schema).encode()).hexdigest()
        if key not in unique_schemas:
            factored,names=factor_schema(schema)
            assert wire(expand_factored(factored,names))==wire(schema), 'property/output ordering changed'
            nodes=[]
            def walk(v,path=''):
                if isinstance(v,dict):
                    if v.get('type')=='object':
                        assert v.get('additionalProperties') is False,path
                        assert set(v.get('properties',{}))==set(v.get('required',[])),path
                    if '$ref' in v:assert v['$ref'].startswith('#/$defs/')
                    for k,child in v.items():walk(child,path+'/'+k)
                elif isinstance(v,list):
                    for j,child in enumerate(v):walk(child,path+'/'+str(j))
            walk(factored)
            unique_schemas[key]=(factored,names)
            out['schema'][key]={'original_chars':len(compact(schema)),'factored_chars':len(compact(factored)),
                'definitions_added':len(names),'ordered_expansion_exact':True,
                'objects_closed_and_all_fields_required':True}
            (HERE/'schema_factored.prototype.json').write_text(json.dumps(factored,ensure_ascii=False,indent=2),encoding='utf-8')
        factored,_=unique_schemas[key]
        response=json.loads(file.with_name('triage.response').read_text(encoding='utf-8'))
        assert valid(response,schema) and valid(response,factored)
        mutations['originals']+=1
        for kind,path,new,remove in mutants(response):
            test=set_at(response,path,new,remove)
            before,after=valid(test,schema),valid(test,factored)
            assert before==after,(file.parent.name,kind,path)
            mutations[kind+'_checks']+=1;mutations[kind+'_accepted']+=int(after)
        rows.append({'ticker':file.parent.name,'lengths':lengths,'patches':patch_records})
    baseline=old_results['runs'][day]['calculations']['normalized_current_total_visible_chars']
    out['runs'][day]={'chars':summary,'additional_visible_reduction_pct':{
        label:(summary['normalized']-value)/baseline*100 for label,value in summary.items() if label!='normalized'},
        'schema_mutations':mutations,'no_web_by_session':session_counts,'rows':rows}
    layout_runs[day]=layouts

for label in ('stable','stable_delta_all','stable_delta_preserve_anchor'):
    pairs=Counter()
    for ticker,a in layout_runs['2026-10-21'].items():
        b=layout_runs['2026-10-22'][ticker]
        pairs.update(pairs=1,common_chars=common(a[label],b[label]))
    pairs['common_mean_chars']=pairs['common_chars']/pairs['pairs']
    out['cache_tradeoff'][label]=pairs

edges=[(None,False),(False,0),(0,0.0),(-0.0,0.0),({'x':None},{}),({}, {'x':None}),
    ([1,2],[2,1]),([1],[1,None]),([1,2],[1]),({'a/b':1,'~':2},{'a/b':2,'~':2})]
for a,b in edges:assert compact(apply(a,delta(a,b)))==compact(b)
out['boundaries']['delta_exact_cases']=len(edges)
assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==sha for p,sha in hashes.items())
out['source_inputs_unchanged']=len(hashes)
(HERE/'variants.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({**out,'runs':{day:{k:v for k,v in run.items() if k!='rows'} for day,run in out['runs'].items()}},ensure_ascii=True,indent=2))
