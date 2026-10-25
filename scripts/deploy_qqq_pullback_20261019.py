"""Deploy the bounded current-Q Q Q panel on each current immutable image.

No models, report publication, IAM changes, config replacement or table refresh.
"""
import argparse
import ast
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import deploy_thesis_links_20261019 as deploy

CONTROLLER_SNIPPET = '''    from stock_analysis.market_worker.relative_pullback import current_pullback
    from stock_analysis.controller.qqq_pullback_panel import build_pullback_requests
    pullback = current_pullback(qqq_data.daily_bars if qqq_data else (), as_of=session.now_et)
    general_requests.extend(build_pullback_requests(layout, pullback))
'''
MOBILE_SNIPPET = '''    # The controller owns this calculation; the app reads the same typed cells.
    qqq_pullback = None
    if value(cells.get((1, 2), {})) == 'QQQ · RETROCESO ACTUAL':
        qqq_pullback = {
            'drawdown': number(value(cells.get((2, 2), {}))),
            'state': text(value(cells.get((2, 5), {}))),
            'threshold_label': text(value(cells.get((3, 5), {}))),
            'peak_label': text(value(cells.get((4, 2), {}))),
            'close_label': text(value(cells.get((5, 2), {}))),
            'basis': text(value(cells.get((6, 2), {}))),
            'note': cells.get((2, 2), {}).get('note', ''),
        }
'''


def semantic(source):
    return hashlib.sha256(ast.dump(ast.parse(source)).encode()).hexdigest()


def inspect():
    value = deploy.current()
    record = deploy.summary(value)
    if len(deploy.traffic(value)) != 1 or deploy.traffic(value)[0][1] != 100 or '@sha256:' not in record['image']:
        raise RuntimeError('single_immutable_active_base_required')
    if (deploy.OUT / 'controller_before.json').exists():
        if deploy.load('controller_before.json')['spec_sha256'] != record['spec_sha256']:
            raise RuntimeError('saved_baseline_differs')
    deploy.save('controller_before.json', record)
    return record


def package():
    before = deploy.load('controller_before.json')
    if deploy.digest(deploy.current()['spec']) != before['spec_sha256']:
        raise RuntimeError('service_changed')
    deploy.WORK.mkdir(parents=True, exist_ok=True)
    if deploy.SERVICE == 'stock-controller':
        source_root = ROOT / 'gcp_services/stock_controller/src'
        modules = ['stock_analysis.market_worker.run_refresh',
                   'stock_analysis.market_worker.relative_pullback',
                   'stock_analysis.controller.qqq_pullback_panel']
    else:
        source_root = ROOT / 'gcp_services/mobile_api'
        modules = ['projection']
    manifest = []
    for module in modules:
        legacy = deploy.WORK / (module.replace('.', '_') + '.py')
        if legacy.exists():
            legacy.unlink()  # Only an exact generated file in this deployment workspace.
        path = source_root / (module.replace('.', '/') + '.py')
        source = path.read_text(encoding='utf-8')
        old = source
        if module.endswith('.run_refresh'):
            assert source.count(CONTROLLER_SNIPPET) == 1
            old = source.replace(CONTROLLER_SNIPPET, '')
        elif module == 'projection':
            assert source.count(MOBILE_SNIPPET) == 1
            old = source.replace(MOBILE_SNIPPET, '').replace(
                "'groups':groups,\n            'qqq_pullback': qqq_pullback},", "'groups':groups},")
            assert 'qqq_pullback' not in old
        target = module.replace('.', '_') + '.source'
        (deploy.WORK / target).write_text(source, encoding='utf-8')
        manifest.append({'module': module, 'file': target,
                         'old': semantic(old) if old != source else None,
                         'new': semantic(source),
                         'insertion': CONTROLLER_SNIPPET if module.endswith('.run_refresh') else MOBILE_SNIPPET if module == 'projection' else None})
    (deploy.WORK / 'manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
    patch = '''import ast,hashlib,importlib,json,py_compile
from pathlib import Path
root=Path('/tmp/qqqfix')
def semantic(source):return hashlib.sha256(ast.dump(ast.parse(source)).encode()).hexdigest()
records=[]
for item in json.loads((root/'manifest.json').read_text()):
    module=item['module'];source=(root/item['file']).read_text(encoding='utf-8')
    assert semantic(source)==item['new']
    if item['old']:
        paths={Path('/app/projection.py')} if module=='projection' else {Path(importlib.import_module(module).__file__)}
        other=Path('/app/src')/(module.replace('.','/')+'.py')
        if other.exists():paths.add(other)
        for path in paths:
            old=path.read_text(encoding='utf-8')
            assert 'qqq_pullback' not in old and 'current_pullback' not in old,'already patched:'+str(path)
            if module=='projection':
                anchor="    qqq = quote_map.get('QQQ', {})\\n"
                tail="'groups':groups},"
                assert old.count(anchor)==1 and old.count(tail)==1,'unexpected projection anchors'
                after=old.replace(anchor,anchor+item['insertion']).replace(tail,"'groups':groups,\\n            'qqq_pullback': qqq_pullback},")
            else:
                anchor='    general_requests = build_general_panel_requests(layout, snapshot)\\n'
                assert old.count(anchor)==1,'unexpected refresh anchor'
                after=old.replace(anchor,anchor+item['insertion'])
            path.write_text(after,encoding='utf-8');py_compile.compile(str(path),doraise=True)
            records.append({'path':str(path),'old':semantic(old),'new':semantic(after),'preserved_other_source':True})
    else:
        import stock_analysis
        package=Path(stock_analysis.__file__).parent
        paths={package/('/'.join(module.split('.')[1:])+'.py')}
        other=Path('/app/src')/(module.replace('.','/')+'.py')
        if other.parent.exists():paths.add(other)
        for path in paths:
            assert not path.exists(),'new module already exists:'+str(path)
            path.write_text(source,encoding='utf-8');py_compile.compile(str(path),doraise=True)
            records.append({'path':str(path),'new':item['new']})
print(json.dumps({'exact_overlay':records}))
'''
    (deploy.WORK / 'patch.py').write_text(patch, encoding='utf-8')
    docker = 'FROM ' + before['image'] + '\nCOPY . /tmp/qqqfix/\nRUN python /tmp/qqqfix/patch.py\n'
    if deploy.SERVICE == 'stock-controller':
        test = ROOT / 'gcp_services/stock_controller/tests/test_qqq_pullback.py'
        (deploy.WORK / test.name).write_bytes(test.read_bytes())
        docker += 'RUN python -m unittest discover -s /tmp/qqqfix -p test_qqq_pullback.py -v\n'
    else:
        test = ROOT / 'gcp_services/mobile_api/tests/test_qqq_pullback.py'
        (deploy.WORK / test.name).write_bytes(test.read_bytes())
        docker += 'RUN PYTHONPATH=/app python -m unittest discover -s /tmp/qqqfix -p test_qqq_pullback.py -v\n'
    (deploy.WORK / 'Dockerfile').write_text(docker, encoding='utf-8')
    (deploy.WORK / '.gcloudignore').write_text('__pycache__/\n*.pyc\n', encoding='utf-8')
    result = {'base_image': before['image'], 'modules': manifest,
              'files': {p.name: deploy.sha(p) for p in deploy.WORK.iterdir() if p.is_file()}}
    deploy.save('package.json', result)
    return {'base_image': before['image'], 'modules': [i['module'] for i in manifest]}


def verify_package():
    record = deploy.load('package.json')
    for name, expected in record['files'].items():
        if deploy.sha(deploy.WORK / name) != expected:
            raise RuntimeError('package_changed:' + name)


def logs():
    build = deploy.load('build.json')
    result = subprocess.run(['cmd.exe', '/d', '/c', shutil.which('gcloud.cmd'),
        'builds', 'log', build['id'], '--account=ignacioanefra@gmail.com',
        '--project=recipe-generator-429817', '--quiet'], capture_output=True,
        text=True, encoding='utf-8', errors='replace', timeout=120)
    output = result.stdout + result.stderr
    (deploy.OUT / 'build.log').write_text(output, encoding='utf-8')
    return {'exit_code': result.returncode, 'tail': output[-6000:]}


if __name__ == '__main__':
    os.environ['CLOUDSDK_CONFIG'] = r'C:\Users\ignac\AppData\Roaming\gcloud'
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('service', choices=['controller', 'mobile', 'both'])
    parser.add_argument('action', choices=['inspect', 'package', 'prepare', 'build', 'status', 'logs', 'stage', 'health', 'activate'])
    parser.add_argument('--execute', action='store_true')
    args = parser.parse_args()
    if args.action in ('prepare', 'build', 'stage', 'activate') and not args.execute:
        parser.error('--execute required')
    for service in ('controller', 'mobile') if args.service == 'both' else (args.service,):
        deploy.SERVICE = 'stock-controller' if service == 'controller' else 'stock-mobile-api'
        deploy.OUT = ROOT / 'docs/audit_qqq_pullback_20261019' / service
        deploy.WORK = ROOT / '.tmp/qqq_pullback_20261019' / service
        deploy.SUFFIX = 'qqq-pullback-20261019'
        deploy.REVISION = deploy.SERVICE + '-' + deploy.SUFFIX
        deploy.TAG = 'qqqtest'
        deploy.OUT.mkdir(parents=True, exist_ok=True)
        deploy.verify_package = verify_package
        if args.action == 'prepare':
            inspect()
            package()
            result = deploy.build()
        else:
            action = {'inspect': inspect, 'package': package, 'logs': logs}.get(args.action) or getattr(deploy, args.action)
            result = action()
        print(json.dumps({'service': service, 'result': result}, ensure_ascii=False, indent=2), flush=True)
