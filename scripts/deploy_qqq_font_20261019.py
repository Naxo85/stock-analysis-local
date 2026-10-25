"""Reduce only the QQQ percentage font from 23 to 14 over the active image."""
import argparse
import ast
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import deploy_thesis_links_20261019 as deploy

SOURCE = ROOT / 'gcp_services/stock_controller/src/stock_analysis/controller/qqq_pullback_panel.py'
deploy.OUT = ROOT / 'docs/audit_qqq_pullback_20261019/font'
deploy.WORK = ROOT / '.tmp/qqq_font_20261019'
deploy.SUFFIX = 'qqq-font-20261019'
deploy.REVISION = 'stock-controller-' + deploy.SUFFIX
deploy.TAG = 'qqqfonttest'


def prepare():
    before = deploy.current()
    record = deploy.summary(before)
    assert len(deploy.traffic(before)) == 1 and deploy.traffic(before)[0][1] == 100
    assert '@sha256:' in record['image']
    if (deploy.OUT / 'controller_before.json').exists():
        assert deploy.load('controller_before.json')['spec_sha256'] == record['spec_sha256']
    deploy.save('controller_before.json', record)
    deploy.WORK.mkdir(parents=True, exist_ok=True)
    source = SOURCE.read_text(encoding='utf-8')
    assert source.count('size=14, bold=True, background=tint') == 1
    old = source.replace('size=14, bold=True, background=tint', 'size=23, bold=True, background=tint')
    (deploy.WORK / 'expected_old.json').write_text(json.dumps(ast.dump(ast.parse(old))), encoding='utf-8')
    patch = '''import ast,json,py_compile
from pathlib import Path
from stock_analysis.controller import qqq_pullback_panel as panel
paths={Path(panel.__file__),Path('/app/src/stock_analysis/controller/qqq_pullback_panel.py')}
expected=json.loads(Path('/tmp/qqqfont/expected_old.json').read_text())
for path in paths:
    before=path.read_text(encoding='utf-8')
    assert ast.dump(ast.parse(before))==expected,'unexpected font baseline:'+str(path)
    assert before.count('size=23, bold=True, background=tint')==1
    after=before.replace('size=23, bold=True, background=tint','size=14, bold=True, background=tint')
    path.write_text(after,encoding='utf-8');py_compile.compile(str(path),doraise=True)
    print(json.dumps({'path':str(path),'only_change':'fontSize23->14'}))
'''
    (deploy.WORK / 'patch.py').write_text(patch, encoding='utf-8')
    (deploy.WORK / 'Dockerfile').write_text('FROM ' + record['image'] + '\nCOPY . /tmp/qqqfont/\nRUN python /tmp/qqqfont/patch.py\n', encoding='utf-8')
    (deploy.WORK / '.gcloudignore').write_text('__pycache__/\n*.pyc\n', encoding='utf-8')
    deploy.save('package.json', {'files': {p.name: deploy.sha(p) for p in deploy.WORK.iterdir() if p.is_file()}, 'source_sha256': deploy.sha(SOURCE)})
    return deploy.build()


def verify_package():
    record = deploy.load('package.json')
    assert deploy.sha(SOURCE) == record['source_sha256']
    for name, expected in record['files'].items():
        assert deploy.sha(deploy.WORK / name) == expected


def finish():
    deploy.stage()
    deploy.health()
    return deploy.activate()


if __name__ == '__main__':
    os.environ['CLOUDSDK_CONFIG'] = r'C:\Users\ignac\AppData\Roaming\gcloud'
    deploy.OUT.mkdir(parents=True, exist_ok=True)
    deploy.verify_package = verify_package
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['prepare', 'status', 'stage', 'health', 'activate', 'finish'])
    parser.add_argument('--execute', action='store_true')
    args = parser.parse_args()
    if args.action in ('prepare', 'stage', 'activate', 'finish') and not args.execute:
        parser.error('--execute required')
    action = {'prepare': prepare, 'finish': finish}.get(args.action) or getattr(deploy, args.action)
    print(json.dumps(action(), ensure_ascii=False, indent=2))
