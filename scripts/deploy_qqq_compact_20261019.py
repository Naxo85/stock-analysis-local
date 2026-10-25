"""Present the existing QQQ value as one compact line, preserving active runtime."""
import argparse
import ast
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import deploy_thesis_links_20261019 as deploy


def prepare():
    value = deploy.current()
    before = deploy.summary(value)
    assert len(deploy.traffic(value)) == 1 and deploy.traffic(value)[0][1] == 100
    assert '@sha256:' in before['image']
    if (deploy.OUT / 'controller_before.json').exists():
        assert deploy.load('controller_before.json')['spec_sha256'] == before['spec_sha256']
    deploy.save('controller_before.json', before)
    deploy.WORK.mkdir(parents=True, exist_ok=True)
    if deploy.SERVICE == 'stock-controller':
        name, source = 'panel', ROOT / 'gcp_services/stock_controller/src/stock_analysis/controller/qqq_pullback_panel.py'
        targets = ['controller/qqq_pullback_panel.py']
    else:
        name, source = 'projection', ROOT / 'gcp_services/mobile_api/projection.py'
        targets = ['projection.py']
    old = (ROOT / '.tmp/qqq_compact_20261019/baseline' / (name + '.source')).read_text(encoding='utf-8')
    new = source.read_text(encoding='utf-8')
    (deploy.WORK / 'expected_old.json').write_text(json.dumps(ast.dump(ast.parse(old))), encoding='utf-8')
    (deploy.WORK / 'new.source').write_text(new, encoding='utf-8')
    if name == 'projection':
        start = '    # The controller owns this calculation; the app reads the same typed cells.\n'
        end = '    schedule = mobile_schedule(layout)\n'
        old_block = old[old.index(start):old.index(end)]
        new_block = new[new.index(start):new.index(end)]
        (deploy.WORK / 'blocks.json').write_text(json.dumps({'old': old_block, 'new': new_block}), encoding='utf-8')
    patch = '''import ast,json,py_compile
from pathlib import Path
root=Path('/tmp/qqqcompact')
expected=json.loads((root/'expected_old.json').read_text())
source=(root/'new.source').read_text(encoding='utf-8')
if Path('/app/projection.py').exists():
    paths={Path('/app/projection.py')}
else:
    from stock_analysis.controller import qqq_pullback_panel as panel
    paths={Path(panel.__file__),Path('/app/src/stock_analysis/controller/qqq_pullback_panel.py')}
for path in paths:
    before=path.read_text(encoding='utf-8')
    if path.name=='projection.py':
        blocks=json.loads((root/'blocks.json').read_text())
        assert before.count(blocks['old'])==1,'unexpected projection block'
        after=before.replace(blocks['old'],blocks['new'])
    else:
        assert ast.dump(ast.parse(before))==expected,'unexpected compact baseline:'+str(path)
        after=source
    path.write_text(after,encoding='utf-8');py_compile.compile(str(path),doraise=True)
    print(json.dumps({'path':str(path),'compact_view_only':True}))
'''
    (deploy.WORK / 'patch.py').write_text(patch, encoding='utf-8')
    (deploy.WORK / 'Dockerfile').write_text('FROM '+before['image']+'\nCOPY . /tmp/qqqcompact/\nRUN python /tmp/qqqcompact/patch.py\n', encoding='utf-8')
    (deploy.WORK / '.gcloudignore').write_text('__pycache__/\n*.pyc\n', encoding='utf-8')
    deploy.save('package.json', {'files': {p.name: deploy.sha(p) for p in deploy.WORK.iterdir() if p.is_file()}, 'source': str(source), 'source_sha256': deploy.sha(source)})
    return deploy.build()


def verify_package():
    record = deploy.load('package.json')
    assert deploy.sha(Path(record['source'])) == record['source_sha256']
    for name, expected in record['files'].items():
        assert deploy.sha(deploy.WORK / name) == expected


def finish():
    deploy.stage()
    deploy.health()
    return deploy.activate()


def rebuild():
    if (deploy.OUT / 'build.json').exists():
        old = deploy.load('build.json')
        status = deploy.gc('builds', 'describe', old['id'])
        assert status['status'] in ('SUCCESS', 'FAILURE')
        archived = deploy.OUT / ('build_previous_' + old['id'] + '.json')
        assert not archived.exists()
        archived.write_text(json.dumps(status, indent=2), encoding='utf-8')
        (deploy.OUT / 'build.json').unlink()
    return prepare()


if __name__ == '__main__':
    os.environ['CLOUDSDK_CONFIG'] = r'C:\Users\ignac\AppData\Roaming\gcloud'
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('service', choices=['controller', 'mobile', 'both'])
    parser.add_argument('action', choices=['prepare', 'rebuild', 'status', 'finish'])
    parser.add_argument('--execute', action='store_true')
    args = parser.parse_args()
    if args.action in ('prepare', 'rebuild', 'finish') and not args.execute:
        parser.error('--execute required')
    for service in ('mobile', 'controller') if args.service == 'both' else (args.service,):
        deploy.SERVICE = 'stock-controller' if service == 'controller' else 'stock-mobile-api'
        deploy.OUT = ROOT / 'docs/audit_qqq_pullback_20261019/compact' / service
        deploy.WORK = ROOT / '.tmp/qqq_compact_20261019' / service
        deploy.SUFFIX = 'qqq-compact-20261019'
        deploy.REVISION = deploy.SERVICE + '-' + deploy.SUFFIX
        deploy.TAG = 'qqqcompacttest'
        deploy.OUT.mkdir(parents=True, exist_ok=True)
        deploy.verify_package = verify_package
        action = {'prepare': prepare, 'rebuild': rebuild, 'finish': finish}.get(args.action) or getattr(deploy, args.action)
        print(json.dumps({'service': service, 'result': action()}, ensure_ascii=False), flush=True)
