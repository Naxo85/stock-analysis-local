import collections, hashlib, json, pathlib, sys
sys.stdout.reconfigure(encoding='utf-8')
ROOT=pathlib.Path(__file__).resolve().parents[3]
def j(path):return json.loads(path.read_text(encoding='utf-8-sig'))
census=j(ROOT/'docs/audit_support_constraints_20261019/weights/census.json')
def rows(path):
    out=[]
    for f in sorted(path.glob('*/publish/current_state.json')):
        d=j(f)
        for k in ['entry','ambitious_entry']:
            z=d['semantic_report']['data']['plan'][k]
            if z.get('range'):out.append(((f.parents[1].name,z['range']['lower'],z['range']['upper']),z['strength']['components']))
    return out
a=rows(ROOT/'logs/batch/2026-10-14/16-07-07/adaptive');b=rows(ROOT/'logs/batch/2026-10-18/09-08-40/adaptive')
print('duplicate identities14',[(k,n) for k,n in collections.Counter(k for k,c in a).items() if n>1])
print('duplicate identities18',[(k,n) for k,n in collections.Counter(k for k,c in b).items() if n>1])
A=dict(a);B=dict(b);both=A.keys()&B.keys();removed=A.keys()-B.keys();added=B.keys()-A.keys()
print('independent14to18',{'matched':len(both),'unchanged':sum(A[k]==B[k] for k in both),'sum_delta':{c:sum(B[k][c]-A[k][c] for k in both) for c in next(iter(A.values()))},'visible_matched_before':sum(sum(A[k].values())>=65 for k in both),'visible_matched_after':sum(sum(B[k].values())>=65 for k in both),'removed_visible':sum(sum(A[k].values())>=65 for k in removed),'added_visible':sum(sum(B[k].values())>=65 for k in added)})
bad=[]
for r in census['files']:
    p=ROOT/r['path']
    if hashlib.sha256(p.read_bytes()).hexdigest()!=r['sha256']:bad.append(r['path'])
print('source_hashes',len(census['files']),'bad',bad)
refs=[]
for f in sorted((ROOT/'logs/batch/2026-10-18/09-08-40/adaptive').glob('*/input.json')):
    d=j(f)['reference']
    for k in ['entry','ambitious_entry']:
        z=d['semantic_report']['data']['plan'][k]
        if z.get('range'):refs.append(((f.parent.name,z['range']['lower'],z['range']['upper']),z['strength']['components']))
print('reference_zones',len(refs),'duplicate_reference_identities',[(k,n) for k,n in collections.Counter(k for k,c in refs).items() if n>1])
R=dict(refs);matched=R.keys()&B.keys()
print('independentref18',len(matched),sum(R[k]==B[k] for k in matched),{c:sum(B[k][c]-R[k][c] for k in matched) for c in next(iter(R.values()))})
d=j(ROOT/'docs/audit_support_constraints_20261019/discovery/discovery_replay.json')
print('discovery root',list(d))
for k,v in d.items():
    print(k, type(v).__name__,len(v) if hasattr(v,'__len__') else v)
    if k not in ('rows','cases','tickers','results','inputs') and len(str(v))<12000:print(json.dumps(v,ensure_ascii=False))
