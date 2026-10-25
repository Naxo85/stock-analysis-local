"""Read-only46-case character audit; exact roundtrips, not quality validation."""
from collections import Counter
from copy import deepcopy
import hashlib,json,sys,time
from pathlib import Path
from prototypes import snapshot_pack,snapshot_unpack,factor_schema,expand_factored,compact,delta,apply
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from src.local_runner.adaptive_context import unpack_model_context,pack_model_context
from src.local_runner.diff_transport import compact_diffs
from src.local_runner.semantic_report import check_schema

BATCH=ROOT/'logs/batch/2026-10-23/14-18-22/adaptive'
totals=Counter();details=Counter();rows=[];hashes={};logical_sections=Counter()
live_prefix=ROOT/'.local/codex-analysis-workspace/triage-70c17b7ab115b4cec14c92f96da83cc194869687820f823b535a6b2f7f867d63.md'
prefix=live_prefix.read_text(encoding='utf-8')
assert hashlib.sha256(prefix.encode()).hexdigest()=='70c17b7ab115b4cec14c92f96da83cc194869687820f823b535a6b2f7f867d63'
schema=json.loads((BATCH/'AMD/triage.schema.json').read_text(encoding='utf-8'))
factored,names=factor_schema(schema)
assert expand_factored(factored,names)==schema
schema_checks=Counter()
def accepts(value,schema):
    try:check_schema(value,schema);return True
    except ValueError:return False
synthetic=[({}, {'a':None}),({'a':None},{}),({'a':0},{'a':False}),({'a':1},{'a':1.0}),
    ({'a':-0.0},{'a':0.0}),([{'a':1},{'a':2}],[{'a':2},{'a':1}]),([1,2],[1]),([1],[1,2])]
for base,new in synthetic:assert compact(apply(base,delta(base,new)))==compact(new)
base_schema_size=len(compact(schema));factored_schema_size=len(compact(factored))
prefix_size=len(prefix)
for index,file in enumerate(sorted(BATCH.glob('*/triage.input.json'))):
    if index%10==0:print('MEASURE',index,flush=True)
    raw=file.read_text(encoding='utf-8');packed=json.loads(raw)
    hashes[str(file)]=hashlib.sha256(file.read_bytes()).hexdigest()
    obj=unpack_model_context(packed)
    response=json.loads(file.with_name('triage.response').read_text(encoding='utf-8'))
    bad_enum=deepcopy(response);bad_enum['decision']='not_a_decision'
    bad_bool=deepcopy(response);bad_bool['risk']['thesis_change']=0
    missing=deepcopy(response);missing.pop('reason')
    for name,value in [('original',response),('enum',bad_enum),('bool',bad_bool),('missing',missing)]:
        a,b=accepts(value,schema),accepts(value,factored)
        assert a==b
        schema_checks[name+'_matching']+=1
        schema_checks[name+'_accepted']+=int(a)
    for k,v in obj.items():logical_sections[k]+=len(compact(v))
    snapshot,patches=snapshot_pack(packed)
    assert snapshot_unpack(snapshot)==packed
    assert unpack_model_context(snapshot_unpack(snapshot))==obj
    row={'ticker':file.parent.name,'wire':len(raw),'snapshot_patch':len(compact(snapshot)), 'patches':patches}
    # Alias target already appears in the authoritative alias map. Replace only
    # explicitly registered markers with null in a separate exact prototype.
    alias=deepcopy(packed)
    for path,target in packed.get('_context_aliases',{}).items():
        parent=alias;parts=path[1:].split('/')
        for part in parts[:-1]:
            part=part.replace('~1','/').replace('~0','~')
            parent=parent[int(part)] if isinstance(parent,list) else parent[part]
        last=parts[-1].replace('~1','/').replace('~0','~')
        last=int(last) if isinstance(parent,list) else last
        assert parent[last]=={'$same_as':target}
        parent[last]=None
    assert unpack_model_context(alias)==obj
    row['alias_single_target']=len(compact(alias))
    combined,_=snapshot_pack(alias)
    assert unpack_model_context(snapshot_unpack(combined))==obj
    row['combined_snapshot_alias']=len(compact(combined))
    # Semantic ablations are upper bounds ONLY. Repack to account for aliases
    # moving into other blocks; never remove a large packed block naively.
    candidates={
        'omit_latest_review_snapshot':lambda x:x.get('comparison',{}).get('latest_published_review',{}).pop('slim_snapshot',None) if isinstance(x.get('comparison',{}).get('latest_published_review'),dict) else None,
        'omit_old_slim_snapshots':lambda x:[x.get(k,{}).pop('slim_snapshot',None) for k in ('reference','sol_reference')],
        'omit_deterministic_diff_guidance':lambda x:x.get('comparison',{}).pop('deterministic',None),
    }
    # compact_diffs requires source snapshots; apply first, then ablate only a
    # COPY of transport view. These are changed-context views, not roundtrips.
    transport=compact_diffs(obj)
    for name,transform in candidates.items():
        variant=deepcopy(transport);transform(variant)
        row[name]=len(compact(pack_model_context(variant)))
    row['schema_factor_combined_ratio']=(row['wire']+prefix_size+factored_schema_size)/(row['wire']+prefix_size+base_schema_size)
    for k,v in row.items():
        if isinstance(v,int):totals[k]+=v
    for patch in patches:details[patch['path']]+=patch['before']-patch['after']
    rows.append(row)
assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==digest for p,digest in hashes.items())
output={'units':'Unicode chars, NOT model token counts or quota; schema sizes compact-JSON normalized',
    'cases':len(rows),'totals':totals,'snapshot_patch_savings_by_path':details,'rows':rows,'logical_sections':logical_sections,
    'prefix_chars':prefix_size,'schema_chars':base_schema_size,'factored_schema_chars':factored_schema_size,
    'factored_definitions':len(names),'schema_checker_equivalence':schema_checks,'roundtrip_cases':46,'typed_edge_cases':len(synthetic),
    'original_hashes':hashes,'prefix_sha256':hashlib.sha256(prefix.encode()).hexdigest(),
    'limits':'Snapshot and alias transports preserve exact data, not proven model interpretation. Omit variants REMOVE context and are upper bounds, never recommendations to drop financial evidence.'}
Path(__file__).with_name('variants.json').write_text(json.dumps(output,ensure_ascii=False,indent=2),encoding='utf-8')
Path(__file__).with_name('schema_factored.prototype.json').write_text(json.dumps(factored,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in output.items() if k not in ('rows','original_hashes','logical_sections')},ensure_ascii=True,indent=2))
