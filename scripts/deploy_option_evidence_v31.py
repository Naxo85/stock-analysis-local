"""Add only preserved option evidence to the currently verified runtime."""
import argparse
import ast
import json
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import deploy_price_history_v28 as base

base.SUFFIX = 'options31-20261013'
base.DEST = ROOT/'logs/deploy_options31'
IMAGES = {
    'raw': '4a2a32ec601fdc14b02f74981cddb0d6ea71192f54101068b55bc7dca927aaa4',
    'slim': 'd92056c8611f179db22ec489f56a2f31f46e463707bbcb8de8fc27242f9fdbe5',
}

class RemoveAddedEvidence(ast.NodeTransformer):
    def visit_FunctionDef(self, node):
        if node.name == '_wall_option_details':
            return None
        return self.generic_visit(node)
    def visit_Assign(self, node):
        if any(isinstance(t, ast.Name) and t.id == 'sampled_chains' or
               isinstance(t, ast.Subscript) and isinstance(t.value, ast.Name)
               and t.value.id == 'sampled_chains' for t in node.targets):
            return None
        return self.generic_visit(node)
    def visit_Dict(self, node):
        self.generic_visit(node)
        pairs = [(k,v) for k,v in zip(node.keys,node.values)
                 if not isinstance(k,ast.Constant) or k.value not in
                 ('option_details','bid_date','ask_date')]
        node.keys = [k for k,v in pairs]; node.values = [v for k,v in pairs]
        return node

def verify_additive(kind):
    old_path = ROOT/f'logs/deploy_history28/{kind}-source/main.py'
    new_path = ROOT/f'gcp_functions/support_resistances_{kind}/main.py'
    old = RemoveAddedEvidence().visit(ast.parse(old_path.read_text(encoding='utf-8')))
    new = RemoveAddedEvidence().visit(ast.parse(new_path.read_text(encoding='utf-8')))
    assert ast.dump(old) == ast.dump(new), 'non-additive producer changes: '+kind
    return new_path

def build(kind):
    source = verify_additive(kind)
    service = 'support-resistances-'+kind
    before = base.describe(service)
    image = before['spec']['template']['spec']['containers'][0]['image']
    assert image.endswith('@sha256:'+IMAGES[kind]), 'active image changed; re-audit'
    assert any(t.get('percent')==100 and t.get('revisionName')==service+'-history28-20261013'
               for t in before['status']['traffic'])
    base.save(kind+'-before.json',before)
    directory = base.DEST/(kind+'-source'); directory.mkdir(exist_ok=True)
    shutil.copy2(source,directory/'main.py')
    (directory/'Dockerfile').write_text('FROM '+image+'\nCOPY main.py /app/main.py\nRUN python -m py_compile /app/main.py\n',encoding='utf-8')
    tag=f'{base.REGION}-docker.pkg.dev/{base.PROJECT}/cloud-run-source-deploy/{service}:{base.SUFFIX}'
    result=base.gc('builds','submit',str(directory),'--tag='+tag,'--async')
    base.save(kind+'-build.json',result)
    print(json.dumps({'kind':kind,'build_id':result['id']}),flush=True)

def activate(kind):
    # Deliberately no symbol fetch: a technical capture also mirrors JSON remotely.
    # Offline raw->slim integration proves preservation; natural batch gets new data.
    service='support-resistances-'+kind
    before=json.loads((base.DEST/(kind+'-before.json')).read_text(encoding='utf-8'))
    staged=json.loads((base.DEST/(kind+'-staged.json')).read_text(encoding='utf-8'))
    assert base.describe(service)['spec']==staged['spec'], 'service changed after staging'
    base.gc('run','services','update-traffic',service,'--region='+base.REGION,
            '--to-revisions='+service+'-'+base.SUFFIX+'=100')
    active=base.describe(service);base.save(kind+'-verified.json',active)
    assert base.preserved_spec(active)==base.preserved_spec(before)
    assert any(t.get('percent')==100 and t.get('revisionName')==service+'-'+base.SUFFIX
               for t in active['status']['traffic'])
    print(kind+' active; same runtime; no symbol capture/model/report',flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('action',choices=['verify','build','deploy','activate'])
    parser.add_argument('kind',choices=['raw','slim'])
    args=parser.parse_args()
    if args.action=='verify': verify_additive(args.kind);print('additive AST verified')
    elif args.action=='deploy': base.deploy(args.kind)
    else: globals()[args.action](args.kind)
