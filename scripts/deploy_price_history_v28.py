"""Narrow additive producer deployment. No models, reports or portfolio writes.

Build from the verified active immutable image, replace only main.py after an
AST equivalence check, stage without traffic, then explicitly activate/verify.
The technical smoke has the producer's normal technical-JSON mirror effect.
"""
import argparse
import ast
from copy import deepcopy
import json
from pathlib import Path
import shutil
import subprocess
import sys
import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.local_runner.gcs_uploader import require_gcloud
from src.local_runner.technical_preparation import require_price_history

PROJECT='recipe-generator-429817'
REGION='europe-southwest1'
SUFFIX='history28-20261013'
DEST=ROOT/'logs/deploy_history28'
IMAGES={
 'raw':'605292334ae1a69102b79ff02a707ba2b557a5cb8c4b792337ba585734a15ff2',
 'slim':'06c73257ef2b6c84958dc171ff23cbee8fc2fc1036ea3d6a9e19526d9bd03026',
}

def save(name, data):
    DEST.mkdir(exist_ok=True)
    (DEST/name).write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')

def gc(*args):
    result=subprocess.run([require_gcloud(),*args,'--project='+PROJECT,'--format=json','--quiet'],
        capture_output=True,text=True,encoding='utf-8',timeout=900)
    if result.returncode:
        raise RuntimeError(result.stderr[-3000:])
    return json.loads(result.stdout) if result.stdout.strip() else {}

def describe(service):
    return gc('run','services','describe',service,'--region='+REGION)

def preserved_spec(data):
    spec=deepcopy(data['spec']['template']['spec'])
    spec['containers'][0].pop('image',None)
    return spec

class RemoveAddedHistory(ast.NodeTransformer):
    def visit_FunctionDef(self,node):
        if node.name=='_recent_price_history': return None
        return self.generic_visit(node)
    def visit_Dict(self,node):
        self.generic_visit(node)
        pairs=[(k,v) for k,v in zip(node.keys,node.values) if not isinstance(k,ast.Constant) or k.value!='price_history']
        node.keys=[k for k,v in pairs];node.values=[v for k,v in pairs]
        return node

def build(kind):
    service='support-resistances-'+kind
    before=describe(service);save(kind+'-before.json',before)
    image=before['spec']['template']['spec']['containers'][0]['image']
    assert image.endswith('@sha256:'+IMAGES[kind]), 'active image changed; re-audit'
    assert any(t.get('percent')==100 and t.get('revisionName')==service+'-evidence26-20261009' for t in before['status']['traffic'])
    source=ROOT/('gcp_functions/support_resistances_'+kind+'/main.py')
    old=ast.parse((ROOT/('logs/deploy_evidence26/'+kind+'-source/main.py')).read_text(encoding='utf-8'))
    new=RemoveAddedHistory().visit(ast.parse(source.read_text(encoding='utf-8')))
    assert ast.dump(old)==ast.dump(new), 'non-additive producer changes'
    directory=DEST/(kind+'-source');directory.mkdir(exist_ok=True)
    shutil.copy2(source,directory/'main.py')
    (directory/'Dockerfile').write_text('FROM '+image+'\nCOPY main.py /app/main.py\nRUN python -m py_compile /app/main.py\n',encoding='utf-8')
    tag=f'{REGION}-docker.pkg.dev/{PROJECT}/cloud-run-source-deploy/{service}:{SUFFIX}'
    result=gc('builds','submit',str(directory),'--tag='+tag,'--async')
    save(kind+'-build.json',result)
    print(json.dumps({'kind':kind,'build_id':result['id'],'image':tag}),flush=True)

def deploy(kind):
    service='support-resistances-'+kind
    before=json.loads((DEST/(kind+'-before.json')).read_text(encoding='utf-8'))
    build_id=json.loads((DEST/(kind+'-build.json')).read_text())['id']
    build=gc('builds','describe',build_id);save(kind+'-build-status.json',build)
    assert build['status']=='SUCCESS', build['status']
    current=describe(service)
    assert current['spec']==before['spec'], 'service changed during build'
    built=build['results']['images'][0]
    image=built['name'].split(':')[0]+'@'+built['digest']
    gc('run','deploy',service,'--region='+REGION,'--image='+image,'--revision-suffix='+SUFFIX,'--no-traffic')
    staged=describe(service);save(kind+'-staged.json',staged)
    assert preserved_spec(staged)==preserved_spec(before), 'runtime changed'
    revision=gc('run','revisions','describe',service+'-'+SUFFIX,'--region='+REGION)
    save(kind+'-revision.json',revision)
    assert any(c['type']=='Ready' and c['status']=='True' for c in revision['status']['conditions'])
    assert [t for t in staged['status']['traffic'] if t.get('percent')]==[t for t in before['status']['traffic'] if t.get('percent')], 'traffic changed prematurely'
    print(kind+' staged Ready, old traffic intact',flush=True)

def activate(kind):
    service='support-resistances-'+kind
    before=json.loads((DEST/(kind+'-before.json')).read_text(encoding='utf-8'))
    staged=json.loads((DEST/(kind+'-staged.json')).read_text(encoding='utf-8'))
    assert describe(service)['spec']==staged['spec'], 'service changed after staging'
    gc('run','services','update-traffic',service,'--region='+REGION,'--to-revisions='+service+'-'+SUFFIX+'=100')
    active=describe(service);save(kind+'-verified.json',active)
    assert preserved_spec(active)==preserved_spec(before)
    assert any(t.get('percent')==100 and t.get('revisionName')==service+'-'+SUFFIX for t in active['status']['traffic'])
    response=requests.get(active['status']['url'],params={'symbol':'LRCX'},timeout=115)
    response.raise_for_status();payload=response.json();save(kind+'-smoke.json',payload)
    require_price_history(payload)
    assert payload['volume_profile']['status']=='available'
    if kind=='slim':
        previous=json.loads((DEST/'raw-smoke.json').read_text(encoding='utf-8'))
        assert payload['price_history']==previous['price_history'], 'raw/slim history mismatch'
    print(json.dumps({'kind':kind,'active':service+'-'+SUFFIX,'sessions':len(payload['price_history']['sessions']),'last_session':payload['price_history']['last_session']}),flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['build','deploy','activate']);parser.add_argument('kind',choices=['raw','slim'])
    args=parser.parse_args();globals()[args.action](args.kind)
