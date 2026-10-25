"""Deploy only explicit plain weight for the linked thesis score.

Reuse the verified immutable-image staging workflow without a projection-version
bump: the one stale live format was already repaired without touching finance.
"""
import argparse
import ast
import json
from pathlib import Path
import shutil
import sys

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from scripts import deploy_thesis_links_20261019 as deploy
deploy.OUT=ROOT/'docs/audit_thesis_plain_20261019'
deploy.WORK=ROOT/'.tmp/thesis_plain_20261019'
deploy.SUFFIX='thesis-plain-20261019'
deploy.REVISION='stock-controller-'+deploy.SUFFIX
deploy.TAG='thesisplaintest'
SOURCE=deploy.BASE/'src/stock_analysis/controller/analysis_sheet.py'

PATCH='''import ast,hashlib,json,py_compile
from pathlib import Path
from copy import deepcopy
from stock_analysis.controller import analysis_sheet
function=Path('/tmp/plainfix/score_function.py').read_text(encoding='utf-8')
expected=ast.parse(function).body[0];old=deepcopy(expected);removed=0
for node in ast.walk(old):
    if isinstance(node,ast.Dict):
        keys=[k.value if isinstance(k,ast.Constant) else None for k in node.keys]
        if 'link' in keys and 'underline' in keys and 'bold' in keys:
            i=keys.index('bold');assert isinstance(node.values[i],ast.Constant) and node.values[i].value is False
            node.keys.pop(i);node.values.pop(i);removed+=1
assert removed==1
path=Path(analysis_sheet.__file__);before=path.read_text(encoding='utf-8')
node=next(n for n in ast.parse(before).body if isinstance(n,ast.FunctionDef)and n.name=='_score_cell')
assert ast.dump(node)==ast.dump(old),'unexpected active score formatter baseline'
lines=before.splitlines(keepends=True);lines[node.lineno-1:node.end_lineno]=[function+'\\n']
after=''.join(lines);path.write_text(after,encoding='utf-8');py_compile.compile(str(path),doraise=True)
print(json.dumps({'exact_patch':{'path':str(path),'before_sha256':hashlib.sha256(before.encode()).hexdigest(),'after_sha256':hashlib.sha256(after.encode()).hexdigest()}}))
'''

def inspect():
    value=deploy.current();record=deploy.summary(value)
    if len(deploy.traffic(value))!=1 or deploy.traffic(value)[0][1]!=100 or '@sha256:'not in record['image']:
        raise RuntimeError('single_immutable_active_base_required')
    if (deploy.OUT/'controller_before.json').exists():raise RuntimeError('baseline_already_exists')
    deploy.save('controller_before.json',record);return record

def package():
    before=deploy.load('controller_before.json')
    if deploy.digest(deploy.current()['spec'])!=before['spec_sha256']:raise RuntimeError('controller_changed')
    deploy.WORK.mkdir(exist_ok=True)
    source=SOURCE.read_text(encoding='utf-8');node=next(n for n in ast.parse(source).body if isinstance(n,ast.FunctionDef)and n.name=='_score_cell')
    (deploy.WORK/'score_function.py').write_text(ast.get_source_segment(source,node)+'\n',encoding='utf-8')
    (deploy.WORK/'patch.py').write_text(PATCH,encoding='utf-8')
    for name in ('test_normalized_report_link_sort.py','test_report_link_persistence.py'):
        shutil.copyfile(deploy.BASE/'tests'/name,deploy.WORK/name)
    verifier='''import ast,inspect,unittest
from pathlib import Path
from stock_analysis.controller.analysis_sheet import _score_cell
expected=ast.parse(Path('/tmp/plainfix/score_function.py').read_text()).body[0]
assert ast.dump(ast.parse(inspect.getsource(_score_cell)).body[0])==ast.dump(expected)
suite=unittest.TestLoader().discover('/tmp/plainfix',pattern='test_*.py')
result=unittest.TextTestRunner(verbosity=2).run(suite)
assert result.wasSuccessful()
'''
    (deploy.WORK/'verify.py').write_text(verifier,encoding='utf-8')
    (deploy.WORK/'Dockerfile').write_text('FROM '+before['image']+'\nCOPY . /tmp/plainfix/\nRUN python /tmp/plainfix/patch.py\nRUN python /tmp/plainfix/verify.py\n',encoding='utf-8')
    (deploy.WORK/'.gcloudignore').write_text('__pycache__/\n*.pyc\n',encoding='utf-8')
    record={'base_image':before['image'],'local_score_formatter_sha256':deploy.sha(SOURCE),
        'files':{p.name:deploy.sha(p)for p in deploy.WORK.iterdir()if p.is_file()},
        'changes':['_score_cell uniform rich text bold=false only'],'presentation_version':15}
    deploy.save('package.json',record);return record

def verify_package():
    record=deploy.load('package.json')
    for name,expected in record['files'].items():
        if deploy.sha(deploy.WORK/name)!=expected:raise RuntimeError('package_changed:'+name)
    if deploy.sha(SOURCE)!=record['local_score_formatter_sha256']:raise RuntimeError('local_formatter_changed')
deploy.verify_package=verify_package

if __name__=='__main__':
    deploy.OUT.mkdir(exist_ok=True)
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=['inspect','package','build','status','stage','health','activate']);p.add_argument('--execute',action='store_true');a=p.parse_args()
    if a.action in ('build','stage','activate')and not a.execute:p.error('--execute required')
    action={'inspect':inspect,'package':package}.get(a.action)or getattr(deploy,a.action)
    print(json.dumps(action(),ensure_ascii=False,indent=2))
