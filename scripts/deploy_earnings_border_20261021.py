"""Thicken only orange earnings borders over the verified current controller."""
import argparse
import json
from pathlib import Path
import shutil
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts import deploy_thesis_links_20261019 as deploy
deploy.OUT=ROOT/'docs/audit_earnings_border_20261021'
deploy.WORK=ROOT/'.tmp/earnings_border_20261021'
deploy.SUFFIX='earnings-border-20261021'
deploy.REVISION='stock-controller-'+deploy.SUFFIX
deploy.TAG='earningsbordertest'
SOURCE=deploy.BASE/'src/stock_analysis/controller/earnings_sheet.py'

PATCH='''import hashlib,json,py_compile
from pathlib import Path
from stock_analysis.controller import earnings_sheet
path=Path(earnings_sheet.__file__)
before=path.read_text(encoding='utf-8')
old="'SOLID_THICK' if alert['severity'] == 'red' else 'SOLID'"
assert before.count(old)==1,'unexpected earnings border baseline'
after=before.replace(old,"'SOLID_THICK'")
path.write_text(after,encoding='utf-8');py_compile.compile(str(path),doraise=True)
print(json.dumps({'patched':str(path),'changes':'orange border SOLID->SOLID_THICK only',
    'before_sha256':hashlib.sha256(before.encode()).hexdigest(),'after_sha256':hashlib.sha256(after.encode()).hexdigest()}))
'''

def prepare():
    value=deploy.current()
    before=deploy.summary(value)
    assert len(deploy.traffic(value))==1 and deploy.traffic(value)[0][1]==100
    assert '@sha256:' in before['image']
    if (deploy.OUT/'controller_before.json').exists():
        assert deploy.load('controller_before.json')['spec_sha256']==before['spec_sha256']
    deploy.save('controller_before.json',before)
    deploy.WORK.mkdir(parents=True,exist_ok=True)
    (deploy.WORK/'patch.py').write_text(PATCH,encoding='utf-8')
    for name in ['test_earnings.py','test_global_sheet_sort.py','test_market_sheet.py']:
        shutil.copyfile(deploy.BASE/'tests'/name,deploy.WORK/name)
    (deploy.WORK/'Dockerfile').write_text('FROM '+before['image']+'\nCOPY . /tmp/borderfix/\nRUN python /tmp/borderfix/patch.py\nRUN python -m unittest discover -s /tmp/borderfix -p "test_*.py" -v\n',encoding='utf-8')
    (deploy.WORK/'.gcloudignore').write_text('__pycache__/\n*.pyc\n',encoding='utf-8')
    deploy.save('package.json',{'local_source_sha256':deploy.sha(SOURCE),'base_image':before['image'],
        'files':{p.name:deploy.sha(p) for p in deploy.WORK.iterdir() if p.is_file()}})
    return deploy.build()

def verify_package():
    record=deploy.load('package.json')
    assert deploy.sha(SOURCE)==record['local_source_sha256']
    for name,expected in record['files'].items():
        assert deploy.sha(deploy.WORK/name)==expected,name

def reconcile_stage():
    """Recover the existing Ready rollout after the local CLI's shorter clock."""
    verify_package()
    before=deploy.load('controller_before.json')
    value=deploy.current()
    assert deploy.digest(deploy.runtime(value))==before['runtime_sha256']
    assert deploy.traffic(value)==sorted((r['revisionName'],r['percent']) for r in before['traffic'] if r.get('percent'))
    assert all(deploy.tags(value).get(r['tag'])==r['revisionName'] for r in before['traffic'] if r.get('tag'))
    revision=deploy.gc('run','revisions','describe',deploy.REVISION,'--region='+deploy.REGION)
    assert any(c['type']=='Ready' and c['status']=='True' for c in revision['status']['conditions'])
    built=deploy.status()['images'][0]
    image=built['name'].rsplit(':',1)[0]+'@'+built['digest']
    assert revision['spec']['containers'][0]['image']==image
    assert value['spec']['template']['spec']['containers'][0]['image']==image
    tag=next(r for r in value['status']['traffic'] if r.get('tag')==deploy.TAG)
    assert tag['revisionName']==deploy.REVISION
    record={**deploy.summary(value),'revision':deploy.REVISION,'tag_url':tag['url'],
            'reconciled_after_cli_timeout':True}
    deploy.save('staged.json',record)
    return {'revision':deploy.REVISION,'ready':True,'runtime_preserved':True}

deploy.verify_package=verify_package

if __name__=='__main__':
    deploy.OUT.mkdir(parents=True,exist_ok=True)
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('action',choices=['prepare','status','stage','reconcile-stage','health','activate'])
    p.add_argument('--execute',action='store_true')
    a=p.parse_args()
    if a.action in ('prepare','stage','activate') and not a.execute:p.error('--execute required')
    action={'prepare':prepare,'reconcile-stage':reconcile_stage}.get(a.action) or getattr(deploy,a.action)
    print(json.dumps(action(),ensure_ascii=False,indent=2),flush=True)
