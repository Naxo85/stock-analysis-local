"""Deploy earnings display over the active immutable images, preserving runtime."""
import argparse
import ast
import json
import os
import shutil
import subprocess
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import deploy_thesis_links_20261019 as deploy

BASELINE = ROOT / '.tmp/earnings_20261021_base'


def functions(source):
    result = {}
    for node in ast.parse(source).body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            result[node.name] = node
        elif isinstance(node, ast.ClassDef):
            for child in node.body:
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    result[node.name + '.' + child.name] = child
    return result


PATCH = '''import ast,json,py_compile
from pathlib import Path
def functions(source):
    result={}
    for node in ast.parse(source).body:
        if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)):result[node.name]=node
        elif isinstance(node,ast.ClassDef):
            for child in node.body:
                if isinstance(child,(ast.FunctionDef,ast.AsyncFunctionDef)):result[node.name+'.'+child.name]=child
    return result
def transform(before,item):
    lines=before.splitlines(keepends=True);nodes=functions(before);changes=[]
    for edit in item['functions']:
        if edit['old_ast'] is None:
            assert edit['name'] not in nodes,'function already exists:'+edit['name']
        else:
            node=nodes[edit['name']]
            assert ast.dump(node)==edit['old_ast'],'function baseline differs:'+edit['name']
            changes.append((node.lineno-1,node.end_lineno,edit['source']))
    for start,end,source in sorted(changes,reverse=True):lines[start:end]=[source+'\\n']
    after=''.join(lines)
    imports=''.join(item['imports'])
    if imports:
        parsed=ast.parse(after);future=[n for n in parsed.body if isinstance(n,ast.ImportFrom) and n.module=='__future__']
        lines=after.splitlines(keepends=True);at=future[-1].end_lineno if future else 0
        lines[at:at]=[imports];after=''.join(lines)
    for edit in item['functions']:
        if edit['old_ast'] is None:after+='\\n\\n'+edit['source']+'\\n'
    return after
if __name__=='__main__':
    root=Path('/tmp/earningsfix')
    for item in json.loads((root/'manifest.json').read_text()):
        module=item['module']
        if module.startswith('stock_analysis.'):
            import stock_analysis
            paths={Path(stock_analysis.__file__).parent/('/'.join(module.split('.')[1:])+'.py')}
            # Patch the imported installed package. /app/src is an older unused
            # build tree and must not replace or constrain the live module.
        else:paths={Path('/app')/(module+'.py')}
        for path in paths:
            if item['new_module']:
                assert not path.exists(),'new module already exists:'+str(path)
                after=(root/item['file']).read_text(encoding='utf-8')
            else:after=transform(path.read_text(encoding='utf-8'),item)
            path.write_text(after,encoding='utf-8');py_compile.compile(str(path),doraise=True)
            print(json.dumps({'patched':str(path),'unrelated_source_preserved':True}))
'''


def inspect():
    service = deploy.current()
    summary = deploy.summary(service)
    assert len(deploy.traffic(service)) == 1 and deploy.traffic(service)[0][1] == 100
    assert '@sha256:' in summary['image']
    if (deploy.OUT / 'controller_before.json').exists():
        assert deploy.load('controller_before.json')['spec_sha256'] == summary['spec_sha256']
    deploy.save('controller_before.json', summary)
    return summary


def package():
    before = deploy.load('controller_before.json')
    # Packaging is local only. build() and stage() recheck the live baseline.
    deploy.WORK.mkdir(parents=True, exist_ok=True)
    if deploy.SERVICE == 'stock-controller':
        source_root = ROOT / 'gcp_services/stock_controller/src'
        modules = [('stock_analysis.earnings_calendar', None), ('stock_analysis.controller.earnings_sheet', None),
                   ('stock_analysis.analysis_worker.reports', 'reports.py'),
                   ('stock_analysis.analysis_worker.run_sync', 'run_sync.py'),
                   ('stock_analysis.market_worker.run_refresh', 'run_refresh.py')]
        tests = ['test_earnings.py', 'test_market_sheet.py', 'test_global_sheet_sort.py', 'test_normalized_report_link_sort.py', 'test_report_link_persistence.py']
        test_root = ROOT / 'gcp_services/stock_controller/tests'
    else:
        source_root = ROOT / 'gcp_services/mobile_api'
        modules = [('earnings_calendar', None), ('projection', 'projection.py'), ('sources', 'sources.py')]
        tests = ['test_earnings.py', 'test_mobile_api.py', 'test_qqq_pullback.py']
        test_root = source_root / 'tests'
    records, sources = [], {}
    for module, baseline in modules:
        path = source_root / (module.replace('.', '/') + '.py')
        sources[str(path)] = deploy.sha(path)
        after = path.read_text(encoding='utf-8')
        name = module.replace('.', '_') + '.source'
        (deploy.WORK / name).write_text(after, encoding='utf-8')
        edits, imports = [], []
        if baseline:
            before_source = (BASELINE / baseline).read_text(encoding='utf-8')
            before_nodes, after_nodes = functions(before_source), functions(after)
            for key, node in after_nodes.items():
                old = before_nodes.get(key)
                if old is None or ast.dump(old) != ast.dump(node):
                    edits.append({'name': key, 'old_ast': ast.dump(old) if old else None,
                                  'source': ''.join(after.splitlines(keepends=True)[node.lineno-1:node.end_lineno]).rstrip()})
            old_imports = {ast.dump(n) for n in ast.parse(before_source).body if isinstance(n, (ast.Import, ast.ImportFrom))}
            imports = [ast.get_source_segment(after, n) + '\n' for n in ast.parse(after).body
                       if isinstance(n, (ast.Import, ast.ImportFrom)) and ast.dump(n) not in old_imports]
            assert edits
        item = {'module': module, 'file': name, 'functions': edits, 'imports': imports, 'new_module': baseline is None}
        if baseline:
            active_source = (ROOT / 'docs/audit_earnings_20261021/source_baselines' / (module.replace('.', '_') + '.py')).read_text(encoding='utf-8')
            namespace = {'__name__': 'patch_validation'}
            exec(PATCH, namespace)
            patched = namespace['transform'](active_source, item)
            patched_functions = functions(patched)
            assert all(ast.dump(patched_functions[key]) == ast.dump(node) for key, node in functions(after).items())
        records.append(item)
    (deploy.WORK / 'manifest.json').write_text(json.dumps(records), encoding='utf-8')
    (deploy.WORK / 'patch.py').write_text(PATCH, encoding='utf-8')
    for test in tests:
        (deploy.WORK / test).write_bytes((test_root / test).read_bytes())
    docker = ('FROM ' + before['image'] + '\nCOPY . /tmp/earningsfix/\nRUN python /tmp/earningsfix/patch.py\n'
              'RUN PYTHONPATH=/app:/tmp/earningsfix python -m unittest discover -s /tmp/earningsfix -p "test_*.py" -v\n')
    (deploy.WORK / 'Dockerfile').write_text(docker, encoding='utf-8')
    (deploy.WORK / '.gcloudignore').write_text('__pycache__/\n*.pyc\n', encoding='utf-8')
    deploy.save('package.json', {'files': {p.name: deploy.sha(p) for p in deploy.WORK.iterdir() if p.is_file()},
                               'sources': sources, 'base_image': before['image'], 'modules': [r['module'] for r in records]})
    return {'modules': [r['module'] for r in records], 'base_image': before['image']}


def verify_package():
    record = deploy.load('package.json')
    for name, expected in record['files'].items():
        assert deploy.sha(deploy.WORK / name) == expected, 'package changed:' + name
    for name, expected in record['sources'].items():
        assert deploy.sha(Path(name)) == expected, 'source changed:' + name


def prepare():
    inspect()
    package()
    if (deploy.OUT / 'build.json').exists():
        previous = deploy.load('build.json')
        deploy.save('build_' + previous['id'] + '.json', previous)
    return deploy.build()


def finish():
    deploy.stage()
    deploy.health()
    return deploy.activate()


def resume_finish():
    """Reconcile a completed Cloud Run operation after a local CLI timeout."""
    verify_package()
    before = deploy.load('controller_before.json')
    current = deploy.current()
    assert deploy.digest(deploy.runtime(current)) == before['runtime_sha256']
    old_traffic = sorted((row['revisionName'], row['percent']) for row in before['traffic'] if row.get('percent'))
    assert deploy.traffic(current) == old_traffic
    assert all(deploy.tags(current).get(row['tag']) == row['revisionName'] for row in before['traffic'] if row.get('tag'))
    revision = deploy.gc('run', 'revisions', 'describe', deploy.REVISION, '--region=' + deploy.REGION)
    assert any(c['type'] == 'Ready' and c['status'] == 'True' for c in revision['status']['conditions'])
    built = deploy.status()['images'][0]
    expected = built['name'].rsplit(':', 1)[0] + '@' + built['digest']
    assert current['spec']['template']['spec']['containers'][0]['image'] == expected
    assert revision['spec']['containers'][0]['image'] == expected
    tag = next(row for row in current['status']['traffic'] if row.get('tag') == deploy.TAG)
    assert tag['revisionName'] == deploy.REVISION
    deploy.save('staged.json', {**deploy.summary(current), 'revision': deploy.REVISION,
                              'tag_url': tag['url'], 'reconciled_after_cli_timeout': True})
    deploy.health()
    return deploy.activate()


def logs():
    build = deploy.load('build.json')
    result = subprocess.run(['cmd.exe', '/d', '/c', shutil.which('gcloud.cmd'), 'builds', 'log', build['id'],
        '--account=ignacioanefra@gmail.com', '--project=recipe-generator-429817', '--quiet'],
        capture_output=True, text=True, encoding='utf-8', timeout=120, check=True)
    (deploy.OUT / ('build_' + build['id'] + '.log')).write_text(result.stdout, encoding='utf-8')
    return result.stdout[-10000:]


if __name__ == '__main__':
    os.environ['CLOUDSDK_CONFIG'] = r'C:\Users\ignac\AppData\Roaming\gcloud'
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('service', choices=['controller', 'mobile'])
    parser.add_argument('action', choices=['inspect', 'package', 'prepare', 'status', 'logs', 'finish', 'resume-finish', 'refresh'])
    parser.add_argument('--execute', action='store_true')
    args = parser.parse_args()
    if args.action in ('prepare', 'finish', 'resume-finish', 'refresh') and not args.execute:
        parser.error('--execute required')
    deploy.SERVICE = 'stock-controller' if args.service == 'controller' else 'stock-mobile-api'
    deploy.OUT = ROOT / 'docs/audit_earnings_20261021' / args.service
    deploy.OUT.mkdir(parents=True, exist_ok=True)
    deploy.WORK = ROOT / '.tmp/earnings_deploy_20261021' / args.service
    deploy.SUFFIX = 'earnings-20261021'
    deploy.REVISION = deploy.SERVICE + '-' + deploy.SUFFIX
    deploy.TAG = 'earningstest'
    deploy.verify_package = verify_package
    action = {'inspect': inspect, 'package': package, 'prepare': prepare, 'finish': finish, 'resume-finish': resume_finish, 'logs': logs}.get(args.action) or getattr(deploy, args.action)
    print(json.dumps({'service': args.service, 'result': action()}, ensure_ascii=True), flush=True)
