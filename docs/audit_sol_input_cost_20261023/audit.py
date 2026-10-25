"""Audit two actual Sol-maintenance batches. No model/auth/network/publication."""
from collections import Counter
from copy import deepcopy
from pathlib import Path
from statistics import median
import hashlib,json,sys
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(ROOT/'docs/audit_input_cost_20261023'))
from prototypes import snapshot_pack,snapshot_unpack,factor_schema,expand_factored,compact
from src.local_runner.adaptive_context import unpack_model_context,pack_model_context
from src.local_runner.diff_transport import compact_diffs,VERSION,INSTRUCTIONS
from src.local_runner.semantic_report import check_schema

RUNS={'2026-10-21':'06-52-46','2026-10-22':'12-32-48'}
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def accepts(value,schema):
    try:check_schema(value,schema);return True
    except ValueError:return False
def null_aliases(packed):
    result=deepcopy(packed)
    for path,target in packed.get('_context_aliases',{}).items():
        parts=[p.replace('~1','/').replace('~0','~') for p in path[1:].split('/')]
        parent=result
        for p in parts[:-1]:parent=parent[int(p)] if isinstance(parent,list) else parent[p]
        k=int(parts[-1]) if isinstance(parent,list) else parts[-1]
        assert parent[k]=={'$same_as':target}
        parent[k]=None
    return result

hashes={};output={}
for day,hour in RUNS.items():
    batch=ROOT/'logs/batch'/day/hour
    summary=json.loads((batch/'summary.json').read_text(encoding='utf-8'))
    ledger=json.loads((batch/'codex_budget.json').read_text(encoding='utf-8'))
    groups={};rows=[];sections=Counter();details=Counter();schema_checks=Counter();totals=Counter();schema_specs={};prefix_specs={}
    for call in ledger['calls'].values():
        assert call.get('model')=='gpt-6.1-sol'
        group=groups.setdefault(call['kind'],{'calls':0,'statuses':Counter(),'usage':Counter(),'credit_proxy':0})
        group['calls']+=1;group['statuses'][call['status']]+=1
        u=call.get('usage') or {};group['usage'].update(u)
        group['credit_proxy']+=(u.get('uncached_input_tokens',0)*50+u.get('cached_input_tokens',0)*2.5+u.get('output_tokens',0)*250)/1e6
    assert groups['triage']['calls']==46 and 'triage_repair' not in groups
    for index,file in enumerate(sorted((batch/'adaptive').glob('*/triage.input.json'))):
        if index%15==0:print('SOL',day,index,flush=True)
        work=file.parent
        receipt=json.loads((work/'triage.receipt.json').read_text(encoding='utf-8'))
        assert receipt['model']=='gpt-6.1-sol' and receipt['reasoning_effort']=='medium'
        assert digest(file)==receipt['input_sha256']
        assert digest(work/'triage.response')==receipt['response_sha256']
        for p in (file,work/'triage.response',work/'triage.receipt.json',work/'triage.schema.json',work/'policy.json'):
            hashes[str(p)]=digest(p)
        raw=file.read_text(encoding='utf-8');packed=json.loads(raw);obj=unpack_model_context(packed)
        assert '_context_transport' not in obj
        prefix_sha=receipt['instructions_sha256']
        if prefix_sha not in prefix_specs:
            prefix_path=ROOT/'.local/codex-analysis-workspace'/('triage-'+prefix_sha+'.md')
            prefix=prefix_path.read_text(encoding='utf-8')
            assert hashlib.sha256(prefix.encode()).hexdigest()==prefix_sha
            prefix_specs[prefix_sha]={'chars':len(prefix),'file':str(prefix_path)}
        prefix_chars=prefix_specs[prefix_sha]['chars']
        schema=json.loads((work/'triage.schema.json').read_text(encoding='utf-8'))
        schema_key=hashlib.sha256(compact(schema).encode()).hexdigest()
        if schema_key not in schema_specs:
            factored,names=factor_schema(schema)
            assert expand_factored(factored,names)==schema
            schema_specs[schema_key]={'before_chars':len(compact(schema)),'after_chars':len(compact(factored)),
                'definitions':len(names),'cases':0}
        else:factored,names=factor_schema(schema)
        schema_specs[schema_key]['cases']+=1
        response=json.loads((work/'triage.response').read_text(encoding='utf-8'))
        negative_enum=deepcopy(response);negative_enum['decision']='invalid'
        negative_bool=deepcopy(response);negative_bool['risk']['thesis_change']=0
        missing=deepcopy(response);missing.pop('reason')
        for label,payload in [('original',response),('enum',negative_enum),('boolean',negative_bool),('missing',missing)]:
            a,b=accepts(payload,schema),accepts(payload,factored)
            assert a==b
            schema_checks[label+'_matching']+=1;schema_checks[label+'_accepted']+=int(a)
        for k,v in packed.items():
            sections[k]+=len(compact(v))
            if isinstance(v,dict):
                for kk,vv in v.items():details[k+'/'+kk]+=len(compact(vv))
        # Separate the optimization ALREADY active in today's policy from NEW
        # transport proposals. No historical input or frozen policy is changed.
        opt_obj={**deepcopy(obj),'_context_transport':VERSION}
        existing=pack_model_context(compact_diffs(opt_obj))
        assert unpack_model_context(existing)==opt_obj
        patch,changes=snapshot_pack(existing)
        assert snapshot_unpack(patch)==existing
        alias=null_aliases(existing)
        assert unpack_model_context(alias)==opt_obj
        combined,_=snapshot_pack(alias)
        assert unpack_model_context(snapshot_unpack(combined))==opt_obj
        row={'ticker':work.name,'model':receipt['model'],'effort':receipt['reasoning_effort'],
            'decision':response['decision'],'web':receipt.get('web_search_count',0),'usage':receipt['usage'],
            'original_wire_chars':len(raw),'original_prefix_chars':prefix_chars,'original_schema_chars':len(compact(schema)),
            'already_active_pointer_wire_chars':len(compact(existing)),
            'already_active_prefix_chars':prefix_chars+2+len(INSTRUCTIONS),
            'snapshot_patch_chars':len(compact(patch)),'alias_single_target_chars':len(compact(alias)),
            'combined_new_codec_chars':len(compact(combined)),'factored_schema_chars':len(compact(factored)),
            'snapshot_patches':changes}
        for key,value in row.items():
            if isinstance(value,int):totals[key]+=value
        rows.append(row)
    no_web=[r for r in rows if r['web']==0]
    credit_total=sum(g['credit_proxy'] for g in groups.values())
    original_total=totals['original_wire_chars']+totals['original_prefix_chars']+totals['original_schema_chars']
    current_total=totals['already_active_pointer_wire_chars']+totals['already_active_prefix_chars']+totals['original_schema_chars']
    new_total=totals['combined_new_codec_chars']+totals['already_active_prefix_chars']+totals['factored_schema_chars']
    calculations={'credit_proxy_total':credit_total,
        'credit_proxy_shares_pct':{k:g['credit_proxy']/credit_total*100 for k,g in groups.items()},
        'maintenance_credit_by_component':{'uncached_input':groups['triage']['usage']['uncached_input_tokens']*50/1e6,
            'cached_input':groups['triage']['usage']['cached_input_tokens']*2.5/1e6,
            'output':groups['triage']['usage']['output_tokens']*250/1e6},
        'original_total_visible_chars':original_total,'normalized_current_total_visible_chars':current_total,
        'already_active_pointer_reduction_pct':(original_total-current_total)/original_total*100,
        'additional_snapshot_reduction_pct':(totals['already_active_pointer_wire_chars']-totals['snapshot_patch_chars'])/current_total*100,
        'additional_alias_reduction_pct':(totals['already_active_pointer_wire_chars']-totals['alias_single_target_chars'])/current_total*100,
        'additional_schema_reduction_pct':(totals['original_schema_chars']-totals['factored_schema_chars'])/current_total*100,
        'additional_combined_reduction_pct':(current_total-new_total)/current_total*100,
        'combined_reduction_vs_historical_pct':(original_total-new_total)/original_total*100,
        'original_visible_mix_pct':{'data_json':totals['original_wire_chars']/original_total*100,
            'instructions':totals['original_prefix_chars']/original_total*100,'schema':totals['original_schema_chars']/original_total*100}}
    output[day]={'batch':str(batch),'summary':{k:summary.get(k) for k in
        ('total','success','failed','retained_reports','updated_reports','regenerated_reports')},
        'recorded_groups':groups,'calculations':calculations,'no_web_reviews':{
            'count':len(no_web),'input_sum':sum(r['usage']['input_tokens'] for r in no_web),
            'input_median':median(r['usage']['input_tokens'] for r in no_web),
            'cached_input_sum':sum(r['usage']['cached_input_tokens'] for r in no_web),
            'zero_cache':sum(r['usage']['cached_input_tokens']==0 for r in no_web)},
        'sections':sections,'details':details,'schema_specs':schema_specs,'prefix_specs':prefix_specs,
        'schema_checker_equivalence':schema_checks,'rows':rows}
assert all(digest(Path(path))==sha for path,sha in hashes.items())
result={'scope':'Actual Sol6.1 medium maintenance on21/22Oct, not Luna23Oct',
        'units':'Recorded tokens; Standard-credit calculation not included-weekly quota; structural variants measured Unicode chars only',
        'original_files_unchanged':len(hashes),'hashes':hashes,'runs':output}
Path(__file__).with_name('results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
for day,data in output.items():
    print(json.dumps({'day':day,**{k:data[k] for k in ('summary','recorded_groups','calculations','no_web_reviews','schema_specs','prefix_specs','schema_checker_equivalence')}},ensure_ascii=True,indent=2))
