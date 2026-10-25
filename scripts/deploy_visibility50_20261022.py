"""Apply the authorized Mercado support visibility threshold over the active image."""
import argparse
import json
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import deploy_thesis_links_20261019 as deploy

deploy.OUT = ROOT / 'docs/audit_visibility50_20261022'
deploy.WORK = ROOT / '.tmp/visibility50_20261022'
deploy.SUFFIX = 'visibility50-20261022'
deploy.REVISION = 'stock-controller-' + deploy.SUFFIX
deploy.TAG = 'visibility50test'
SOURCES = [deploy.BASE / 'src/stock_analysis/controller/analysis_sheet.py',
           deploy.BASE / 'src/stock_analysis/analysis_worker/run_sync.py']

PATCH = '''import ast,hashlib,json,py_compile
from pathlib import Path
from stock_analysis.controller import analysis_sheet
from stock_analysis.analysis_worker import run_sync
changes=[]
for module,relative,old,new in [
 (analysis_sheet,'controller/analysis_sheet.py','SUPPORT_STRENGTH_VISIBLE_THRESHOLD = 65','SUPPORT_STRENGTH_VISIBLE_THRESHOLD = 50'),
 (run_sync,'analysis_worker/run_sync.py','"presentation_version": 16','"presentation_version": 17')]:
 paths={Path(module.__file__)}
 other=Path('/app/src/stock_analysis')/relative
 if module is analysis_sheet and other.is_file():paths.add(other)
 for path in sorted(paths):
  before=path.read_text(encoding='utf-8')
  if module is analysis_sheet:
   node=next(n for n in ast.parse(before).body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='SUPPORT_STRENGTH_VISIBLE_THRESHOLD' for t in n.targets))
   assert node.value.value == (65 if path==Path(module.__file__) else 70),'unexpected threshold baseline:'+str(path)
   lines=before.splitlines(keepends=True)
   lines[node.lineno-1:node.end_lineno]=[new+'\\n']
   after=''.join(lines)
  else:
   assert before.count(old)==1,'unexpected baseline:'+str(path)
   after=before.replace(old,new)
  path.write_text(after,encoding='utf-8');py_compile.compile(str(path),doraise=True)
  changes.append({'path':str(path),'before_sha256':hashlib.sha256(before.encode()).hexdigest(),'after_sha256':hashlib.sha256(after.encode()).hexdigest()})
print(json.dumps({'exact_patch':changes}))
'''


def prepare():
    value = deploy.current()
    before = deploy.summary(value)
    assert len(deploy.traffic(value)) == 1 and deploy.traffic(value)[0][1] == 100
    revision = deploy.gc('run', 'revisions', 'describe', deploy.traffic(value)[0][0], '--region='+deploy.REGION)
    assert '@sha256:' in before['image']
    assert revision['spec']['containers'][0]['image'] == before['image']
    if (deploy.OUT/'controller_before.json').exists():
        assert deploy.load('controller_before.json')['spec_sha256'] == before['spec_sha256']
    deploy.save('controller_before.json', before)
    deploy.WORK.mkdir(parents=True, exist_ok=True)
    (deploy.WORK/'patch.py').write_text(PATCH, encoding='utf-8')
    for name in ['test_analysis_sheet.py', 'test_global_sheet_sort.py', 'test_market_sheet.py', 'test_earnings.py']:
        shutil.copyfile(deploy.BASE/'tests'/name, deploy.WORK/name)
    (deploy.WORK/'Dockerfile').write_text('FROM '+before['image']+'\nCOPY . /tmp/visibilityfix/\nRUN python /tmp/visibilityfix/patch.py\nRUN python -m unittest discover -s /tmp/visibilityfix -p "test_*.py" -v\n', encoding='utf-8')
    (deploy.WORK/'.gcloudignore').write_text('__pycache__/\n*.pyc\n', encoding='utf-8')
    deploy.save('package.json', {'sources': {str(p.relative_to(ROOT)): deploy.sha(p) for p in SOURCES},
        'base_image': before['image'], 'files': {p.name: deploy.sha(p) for p in deploy.WORK.iterdir() if p.is_file()}})
    return deploy.build()


def verify_package():
    record = deploy.load('package.json')
    for name, expected in record['sources'].items():
        assert deploy.sha(ROOT/name) == expected, name
    for name, expected in record['files'].items():
        assert deploy.sha(deploy.WORK/name) == expected, name


deploy.verify_package = verify_package

if __name__ == '__main__':
    deploy.OUT.mkdir(parents=True, exist_ok=True)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['prepare', 'status', 'stage', 'health', 'activate', 'refresh'])
    parser.add_argument('--execute', action='store_true')
    args = parser.parse_args()
    if args.action in ('prepare', 'stage', 'activate', 'refresh') and not args.execute:
        parser.error('--execute required')
    action = prepare if args.action == 'prepare' else getattr(deploy, args.action)
    print(json.dumps(action(), ensure_ascii=False, indent=2), flush=True)
