"""Deploy exact additive acquisition changes over verified active31 images."""
import argparse
import ast
import json
from pathlib import Path
import shutil
import sys
import requests

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts import deploy_price_history_v28 as base

base.SUFFIX='origins39-20261016'
base.DEST=ROOT/'logs/deploy_origins39'
IMAGES={
    'raw':'0de9f8a4f4909f221a0354926309965a0fd60330dc5382147cbdf34ec5e0ea88',
    'slim':'d63ba7f0f9773edec2dbf26a05bb4537642548e8f7354592cedcaeddcaeb9881',
}
ADDED={'raw':{'_parse_option_origins','_observe_option_origins'},'slim':{'_slim_option_origins'}}
CHANGED={'raw':{'support_resistances_raw'},
         'slim':{'support_resistances_slim','_fetch_raw','_build_slim'}}

def verify(kind):
    before=ROOT/f'logs/deploy_options31/{kind}-source/main.py'
    after=ROOT/f'gcp_functions/support_resistances_{kind}/main.py'
    old,new=[ast.parse(p.read_text(encoding='utf-8')) for p in (before,after)]
    oldf={n.name:n for n in old.body if isinstance(n,ast.FunctionDef)}
    newf={n.name:n for n in new.body if isinstance(n,ast.FunctionDef)}
    assert set(newf)-set(oldf)==ADDED[kind] and not set(oldf)-set(newf)
    changed={name for name in oldf if ast.dump(oldf[name])!=ast.dump(newf[name])}
    assert changed==CHANGED[kind],changed
    assert ast.dump(ast.Module(body=[n for n in old.body if not isinstance(n,ast.FunctionDef)],type_ignores=[]))==ast.dump(ast.Module(body=[n for n in new.body if not isinstance(n,ast.FunctionDef)],type_ignores=[]))
    # The few changed functions are reviewed as exact source diff in the audit.
    return after

def build(kind):
    source=verify(kind);service='support-resistances-'+kind
    before=base.describe(service);image=before['spec']['template']['spec']['containers'][0]['image']
    assert image.endswith('@sha256:'+IMAGES[kind]),'active image changed; re-audit'
    assert any(t.get('percent')==100 and t.get('revisionName')==service+'-options31-20261013' for t in before['status']['traffic'])
    base.save(kind+'-before.json',before)
    directory=base.DEST/(kind+'-source');directory.mkdir(exist_ok=True)
    shutil.copy2(source,directory/'main.py')
    shutil.copy2(ROOT/'scripts/verify_option_origin_image.py',directory/'verify_origins.py')
    (directory/'Dockerfile').write_text('FROM '+image+'\nCOPY main.py /app/main.py\nCOPY verify_origins.py /app/verify_origins.py\nRUN python -m py_compile /app/main.py && python /app/verify_origins.py '+kind+'\n',encoding='utf-8')
    tag=f'{base.REGION}-docker.pkg.dev/{base.PROJECT}/cloud-run-source-deploy/{service}:{base.SUFFIX}'
    build=base.gc('builds','submit',str(directory),'--tag='+tag,'--async')
    base.save(kind+'-build.json',build)
    print(json.dumps({'kind':kind,'build_id':build['id']}),flush=True)

def probe(kind):
    service='support-resistances-'+kind
    staged=json.loads((base.DEST/(kind+'-staged.json')).read_text(encoding='utf-8'))
    assert base.describe(service)['spec']==staged['spec']
    tag='originstest39'
    base.gc('run','services','update-traffic',service,'--region='+base.REGION,
            '--update-tags='+tag+'='+service+'-'+base.SUFFIX)
    tagged=base.describe(service)
    assert base.preserved_spec(tagged)==base.preserved_spec(staged)
    assert [t for t in tagged['status']['traffic'] if t.get('percent')]==[t for t in staged['status']['traffic'] if t.get('percent')]
    target=next(t for t in tagged['status']['traffic'] if t.get('tag')==tag)
    assert target['revisionName']==service+'-'+base.SUFFIX
    result=requests.get(target['url'],timeout=60)
    assert result.status_code==400 and 'symbol' in result.json().get('error',''),(result.status_code,result.text[:200])
    # No symbol: validates the application without Tradier calls or mirroring.
    base.save(kind+'-probe.json',{'status':result.status_code,'error':result.json(),'revision':target['revisionName']})
    base.save(kind+'-staged.json',tagged)
    print(kind+': exact staged revision served expected application response',flush=True)

def activate(kind):
    service='support-resistances-'+kind
    before=json.loads((base.DEST/(kind+'-before.json')).read_text(encoding='utf-8'))
    staged=json.loads((base.DEST/(kind+'-staged.json')).read_text(encoding='utf-8'))
    assert base.describe(service)['spec']==staged['spec'],'service changed after staging'
    revision=base.gc('run','revisions','describe',service+'-'+base.SUFFIX,'--region='+base.REGION)
    conditions={row['type']:row['status'] for row in revision['status']['conditions']}
    assert conditions.get('Ready')=='True' and (conditions.get('ContainerHealthy')=='True' or conditions.get('ContainerReady')=='True'),conditions
    checked=json.loads((base.DEST/(kind+'-probe.json')).read_text(encoding='utf-8'))
    assert checked['revision']==service+'-'+base.SUFFIX and checked['status']==400
    base.gc('run','services','update-traffic',service,'--region='+base.REGION,
            '--to-revisions='+service+'-'+base.SUFFIX+'=100')
    active=base.describe(service);base.save(kind+'-verified.json',active)
    assert base.preserved_spec(active)==base.preserved_spec(before)
    assert any(t.get('percent')==100 and t.get('revisionName')==service+'-'+base.SUFFIX for t in active['status']['traffic'])
    base.gc('run','services','update-traffic',service,'--region='+base.REGION,'--remove-tags=originstest39')
    final=base.describe(service);base.save(kind+'-verified.json',final)
    assert base.preserved_spec(final)==base.preserved_spec(before)
    assert {t['tag']:t['revisionName'] for t in final['status']['traffic'] if t.get('tag')}=={t['tag']:t['revisionName'] for t in before['status']['traffic'] if t.get('tag')}
    # No automatic symbol capture, report publication or batch in deployment.
    print(kind+': active, preserved runtime',flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['verify','build','deploy','probe','activate']);p.add_argument('kind',choices=['raw','slim']);a=p.parse_args()
    if a.action=='verify':verify(a.kind);print(a.kind+': exact allowed AST scope verified')
    elif a.action=='deploy':base.deploy(a.kind)
    else:globals()[a.action](a.kind)
