"""Repair normalized report links in the controller's row-sort serializer.

Build a two-module patch over the verified active image. Preserve runtime and
financial reports. Explicit actions separate build, staging and activation.
"""
import argparse
import ast
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts.deploy_support_origins_v41 import gc, digest, runtime, traffic, tags
OUT=ROOT/'docs/audit_thesis_links_20261019'
WORK=ROOT/'.tmp/thesis_links_20261019'
REGION='europe-southwest1'
SERVICE='stock-controller'
SUFFIX='report-links-sort-20261019'
REVISION=SERVICE+'-'+SUFFIX
TAG='linkssorttest'
BASE=ROOT/'gcp_services/stock_controller'


def load(name): return json.loads((OUT/name).read_text(encoding='utf-8'))
def save(name,value): (OUT/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def current(): return gc('run','services','describe',SERVICE,'--region='+REGION)
def summary(value):
    return {'spec_sha256':digest(value['spec']),'runtime_sha256':digest(runtime(value)),
            'traffic':value['status']['traffic'],'url':value['status']['url'],
            'image':value['spec']['template']['spec']['containers'][0]['image']}


PATCH = '''import ast,hashlib,json,py_compile
from pathlib import Path
from copy import deepcopy
from stock_analysis.controller import global_sheet_sort as sort
from stock_analysis.analysis_worker import run_sync as sync

function=Path('/tmp/linksfix/writable_function.py').read_text(encoding='utf-8')
expected=ast.parse(function).body[0]
old=deepcopy(expected);old.body=old.body[:2]+[old.body[-1]]
expected_old=ast.dump(old)
changed=[]
for module,relative,mode in [(sort,'controller/global_sheet_sort.py','function'),(sync,'analysis_worker/run_sync.py','version')]:
    imported=Path(module.__file__)
    paths={imported}
    other=Path('/app/src/stock_analysis')/relative
    if mode=='function' and other.is_file():paths.add(other)
    for path in sorted(paths):
        before=path.read_text(encoding='utf-8')
        if mode=='function':
            node=next(n for n in ast.parse(before).body if isinstance(n,ast.FunctionDef) and n.name=='_writable_cell')
            assert ast.dump(node)==expected_old, 'unexpected serializer baseline:'+str(path)
            lines=before.splitlines(keepends=True)
            lines[node.lineno-1:node.end_lineno]=[function+'\\n']
            after=''.join(lines)
        else:
            assert before.count('"presentation_version": 14')==1,'unexpected projection baseline:'+str(path)
            after=before.replace('"presentation_version": 14','"presentation_version": 15')
        path.write_text(after,encoding='utf-8');py_compile.compile(str(path),doraise=True)
        changed.append({'path':str(path),'before_sha256':hashlib.sha256(before.encode()).hexdigest(),'after_sha256':hashlib.sha256(after.encode()).hexdigest()})
print(json.dumps({'exact_patch':changed}))
'''


def package():
    before=load('controller_before.json')
    service=current()
    if digest(service['spec'])!=before['spec_sha256']:
        raise RuntimeError('controller_changed_since_inventory')
    if len(traffic(service))!=1 or traffic(service)[0][1]!=100 or '@sha256:' not in before['image']:
        raise RuntimeError('single_immutable_active_base_required')
    WORK.mkdir(exist_ok=True)
    path=BASE/'src/stock_analysis/controller/global_sheet_sort.py'
    source=path.read_text(encoding='utf-8')
    node=next(n for n in ast.parse(source).body if isinstance(n,ast.FunctionDef) and n.name=='_writable_cell')
    (WORK/'writable_function.py').write_text(ast.get_source_segment(source,node)+'\n',encoding='utf-8')
    (WORK/'patch.py').write_text(PATCH,encoding='utf-8')
    for name in ('test_normalized_report_link_sort.py','test_report_link_persistence.py'):
        shutil.copyfile(BASE/'tests'/name,WORK/name)
    verifier='''import ast,json,unittest
from pathlib import Path
from stock_analysis.controller import global_sheet_sort as sort
from stock_analysis.analysis_worker import run_sync as sync
expected=ast.parse(Path('/tmp/linksfix/writable_function.py').read_text()).body[0]
import inspect
assert ast.dump(ast.parse(inspect.getsource(sort._writable_cell)).body[0])==ast.dump(expected)
assert '"presentation_version": 15' in Path(sync.__file__).read_text()
suite=unittest.TestLoader().discover('/tmp/linksfix',pattern='test_*.py')
result=unittest.TextTestRunner(verbosity=2).run(suite)
assert result.wasSuccessful()
print(json.dumps({'image_verification':'passed','tests':result.testsRun,'no_external_calls':True}))
'''
    (WORK/'verify.py').write_text(verifier,encoding='utf-8')
    docker='FROM '+before['image']+'\nCOPY . /tmp/linksfix/\nRUN python /tmp/linksfix/patch.py\nRUN python /tmp/linksfix/verify.py\n'
    (WORK/'Dockerfile').write_text(docker,encoding='utf-8')
    (WORK/'.gcloudignore').write_text('__pycache__/\n*.pyc\n',encoding='utf-8')
    record={'base_image':before['image'],'files':{p.name:sha(p) for p in WORK.iterdir() if p.is_file()},
            'local_serializer_sha256':sha(path),'changes':['global_sheet_sort._writable_cell','run_sync.presentation_version14->15']}
    save('package.json',record)
    return record


def verify_package():
    record=load('package.json')
    for name,expected in record['files'].items():
        if sha(WORK/name)!=expected:raise RuntimeError('package_changed:'+name)
    if sha(BASE/'src/stock_analysis/controller/global_sheet_sort.py')!=record['local_serializer_sha256']:
        raise RuntimeError('local_serializer_changed')


def build():
    verify_package()
    if digest(current()['spec'])!=load('controller_before.json')['spec_sha256']:
        raise RuntimeError('controller_changed_before_build')
    if (OUT/'build.json').exists():
        previous=load('build.json')
        final=gc('builds','describe',previous['id'])
        if final['status']!='FAILURE':raise RuntimeError('build_exists_check_status')
        save('build_attempt1.json',previous);save('build_attempt1_status.json',final)
    image=f'{REGION}-docker.pkg.dev/recipe-generator-429817/cloud-run-source-deploy/{SERVICE}:{SUFFIX}'
    result=gc('builds','submit',str(WORK),'--tag='+image,'--async')
    save('build.json',result)
    return {'id':result['id'],'status':result['status']}


def status():
    result=gc('builds','describe',load('build.json')['id']);save('build_status.json',result)
    return {'id':result['id'],'status':result['status'],'images':result.get('results',{}).get('images',[])}


def stage():
    verify_package();result=status()
    if result['status']!='SUCCESS':raise RuntimeError('build_not_successful')
    before=current()
    if digest(before['spec'])!=load('controller_before.json')['spec_sha256']:
        raise RuntimeError('controller_changed_before_stage')
    built=result['images'][0];image=built['name'].rsplit(':',1)[0]+'@'+built['digest']
    gc('run','deploy',SERVICE,'--region='+REGION,'--image='+image,
       '--revision-suffix='+SUFFIX,'--no-traffic','--tag='+TAG)
    after=current()
    if runtime(before)!=runtime(after) or traffic(before)!=traffic(after) or any(tags(after).get(k)!=v for k,v in tags(before).items()):
        raise RuntimeError('runtime_traffic_or_existing_tags_changed')
    row=next(r for r in after['status']['traffic'] if r.get('tag')==TAG)
    if row['revisionName']!=REVISION:raise RuntimeError('wrong_revision')
    record={**summary(after),'revision':REVISION,'tag_url':row['url']}
    save('staged.json',record);return record


def token():
    result=subprocess.run(['cmd.exe','/d','/c',shutil.which('gcloud.cmd'),'auth','print-identity-token',
                           '--account=ignacioanefra@gmail.com'],capture_output=True,text=True,timeout=60)
    if result.returncode:raise RuntimeError('identity_token_unavailable')
    return result.stdout.strip()


def request(url,method='GET',timeout=60):
    import requests
    response=requests.request(method,url,headers={'Authorization':'Bearer '+token()},timeout=timeout,allow_redirects=False)
    if response.status_code!=200:raise RuntimeError('controller_http_error:'+str(response.status_code)+':'+response.text[:500])
    return response.json()


def health():
    stage=load('staged.json')
    result=request(stage['tag_url']+'/health')
    if result.get('status')!='ok':raise RuntimeError('staged_health_not_ok')
    save('staged_health.json',{'revision':REVISION,'http_status':200,'body':result})
    return result


def activate():
    verify_package();stage=load('staged.json')
    if load('staged_health.json')['revision']!=REVISION:raise RuntimeError('health_missing')
    before=current()
    if digest(before['spec'])!=stage['spec_sha256']:raise RuntimeError('controller_changed_before_activation')
    revision=gc('run','revisions','describe',REVISION,'--region='+REGION)
    if not any(c['type']=='Ready' and c['status']=='True' for c in revision['status']['conditions']):raise RuntimeError('revision_not_ready')
    gc('run','services','update-traffic',SERVICE,'--region='+REGION,'--to-revisions='+REVISION+'=100')
    after=current()
    if traffic(after)!=[(REVISION,100)] or runtime(before)!=runtime(after) or tags(before)!=tags(after):
        raise RuntimeError('activation_invariants_failed')
    record={**summary(after),'runtime_preserved':True};save('active.json',record);return record


def refresh():
    value=current()
    if traffic(value)!=[(REVISION,100)]:raise RuntimeError('fix_not_active')
    result=request(value['status']['url']+'/analysis/refresh','POST',timeout=300)
    save('refresh.json',result);return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['package','build','status','stage','health','activate','refresh'])
    parser.add_argument('--execute',action='store_true');args=parser.parse_args()
    if args.action in ('build','stage','activate','refresh') and not args.execute:parser.error('--execute required')
    print(json.dumps(globals()[args.action](),ensure_ascii=False,indent=2))
