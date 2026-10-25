"""Production-schema equivalence against authenticated Sol originals, no calls."""
from collections import Counter
from copy import deepcopy
from pathlib import Path
import hashlib, json, sys
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(ROOT/'tests'))
from src.local_runner.maintenance_schema_transport import output_schema, VERSION
from src.local_runner.adaptive_maintenance import maintenance_schema
from src.local_runner.adaptive_context import unpack_model_context
from src.local_runner.semantic_report import check_schema, report_schema
from test_maintenance_schema_transport import expanded, wire

HERE=Path(__file__).resolve().parent
def valid(value,schema):
    try:check_schema(value,schema);return True
    except ValueError:return False
def mutants(value,path=()):
    if isinstance(value,dict):
        yield path+('__unexpected_audit_field__',),True,False
        for key,child in value.items():
            yield path+(key,),None,True
            yield from mutants(child,path+(key,))
    elif isinstance(value,list):
        yield path,{},False
        for i,child in enumerate(value):yield from mutants(child,path+(i,))
    else:
        wrong=0 if type(value) is bool else False if type(value) in (int,float) else 123 if isinstance(value,str) else {}
        yield path,wrong,False
def mutate(value,path,new,remove):
    if not path:return deepcopy(new)
    result=deepcopy(value);parent=result
    for part in path[:-1]:parent=parent[part]
    if remove:del parent[path[-1]]
    else:parent[path[-1]]=deepcopy(new)
    return result

policy={'routing_revision':41,'maintenance_output_schema':VERSION}
out={'runs':{},'schema_sizes':{},'original_hashes':{}}
for day,hour in [('2026-10-21','06-52-46'),('2026-10-22','12-32-48')]:
    total=Counter()
    for i,file in enumerate(sorted((ROOT/'logs/batch'/day/hour/'adaptive').glob('*/triage.schema.json'))):
        if i%15==0:print('REPLAY',day,i,flush=True)
        for name in ('triage.input.json','triage.schema.json','triage.receipt.json','triage.response','input.json','policy.json'):
            path=file.with_name(name);out['original_hashes'][str(path)]=hashlib.sha256(path.read_bytes()).hexdigest()
        schema=json.loads(file.read_text(encoding='utf-8'))
        frozen=json.loads(file.with_name('policy.json').read_text(encoding='utf-8'))
        logical=unpack_model_context(json.loads(file.with_name('triage.input.json').read_text(encoding='utf-8')))
        assert wire(maintenance_schema(logical))==wire(schema)
        assert output_schema(schema,frozen,kind='triage') is schema
        shared=output_schema(schema,policy,kind='triage')
        assert wire(expanded(shared,schema))==wire(schema)
        before,after=len(wire(schema)),len(wire(shared))
        out['schema_sizes'][str(before)]={'before':before,'after':after,'reduction_pct':(before-after)/before*100}
        total.update(contexts=1,original_chars=before,shared_chars=after)
        payload=json.loads(file.with_name('triage.response').read_text(encoding='utf-8'))
        assert valid(payload,schema) and valid(payload,shared)
        total['original_responses_admitted']+=1
        for path,value,remove in mutants(payload):
            test=mutate(payload,path,value,remove)
            assert not valid(test,schema) and not valid(test,shared)
            total['mutants_rejected_equally']+=1
        repair={**deepcopy(logical),'maintenance_repair':{'rejection':'invalid_source'}}
        directed=maintenance_schema(repair)
        encoded=output_schema(directed,policy,kind='triage_repair')
        assert wire(expanded(encoded,directed))==wire(directed)
        total['directed_repair_schemas_exact']+=1
        full=report_schema(41)
        assert output_schema(full,policy,kind='report') is full
        total['full_schemas_unchanged']+=1
    old=json.loads((HERE.parent/'results.json').read_text(encoding='utf-8'))['runs'][day]
    denominator=old['calculations']['normalized_current_total_visible_chars']
    out['runs'][day]={'checks':total,'visible_char_reduction_pct':(total['original_chars']-total['shared_chars'])/denominator*100}

assert all(hashlib.sha256(Path(path).read_bytes()).hexdigest()==sha for path,sha in out['original_hashes'].items())
out['original_files_unchanged']=len(out['original_hashes'])
out['limits']='Local schema/receipt checks, not a live admission test or measured token/quota savings.'
(HERE/'replay.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in out.items() if k!='original_hashes'},ensure_ascii=True,indent=2))
