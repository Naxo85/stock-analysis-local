"""Read source modules from the two immutable deployment bases, without deploying."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.deploy_support_origins_v41 import gc
OUT = ROOT / 'docs/audit_earnings_20261021'
WORK = ROOT / '.tmp/earnings_baseline_capture'


def start():
    WORK.mkdir(parents=True, exist_ok=True)
    script = '''import importlib.util,json,sys
from pathlib import Path
sys.path.insert(0, '/app')
for module in sys.argv[1:]:
    path=Path(importlib.util.find_spec(module).origin)
    print('SOURCE_RECORD:'+json.dumps({'module':module,'source':path.read_text(encoding='utf-8')}))
'''
    (WORK / 'read.py').write_text(script, encoding='utf-8')
    steps = []
    for service, modules in [('controller', ['stock_analysis.analysis_worker.reports', 'stock_analysis.analysis_worker.run_sync', 'stock_analysis.market_worker.run_refresh']),
                              ('mobile', ['projection', 'sources'])]:
        if all((OUT / 'source_baselines' / (m.replace('.', '_') + '.py')).exists() for m in modules):
            continue
        image = json.loads((OUT / service / 'controller_before.json').read_text())['image']
        steps.append({'name': 'gcr.io/cloud-builders/docker',
                      'args': ['run', '--rm', '-v', '/workspace:/diag', image, 'python', '/diag/read.py', *modules]})
    (WORK / 'cloudbuild.json').write_text(json.dumps({'steps': steps}), encoding='utf-8')
    result = gc('builds', 'submit', str(WORK), '--config=' + str(WORK / 'cloudbuild.json'), '--async')
    (OUT / ('source_capture_' + result['id'] + '.json')).write_text(json.dumps(result, indent=2), encoding='utf-8')
    (OUT / 'source_capture_build.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    return {'id': result['id'], 'status': result['status']}


def collect():
    build = json.loads((OUT / 'source_capture_build.json').read_text())
    status = gc('builds', 'describe', build['id'])['status']
    if status not in ('SUCCESS', 'FAILURE'):
        return {'status': status}
    run = subprocess.run(['cmd.exe', '/d', '/c', shutil.which('gcloud.cmd'), 'builds', 'log', build['id'],
            '--account=ignacioanefra@gmail.com', '--project=recipe-generator-429817', '--quiet'],
            capture_output=True, text=True, encoding='utf-8', timeout=120, check=True)
    (OUT / ('source_capture_' + build['id'] + '.log')).write_text(run.stdout, encoding='utf-8')
    directory = OUT / 'source_baselines'
    directory.mkdir(exist_ok=True)
    captured = []
    for line in run.stdout.splitlines():
        if 'SOURCE_RECORD:' in line:
            data = json.loads(line.split('SOURCE_RECORD:', 1)[1])
            (directory / (data['module'].replace('.', '_') + '.py')).write_text(data['source'], encoding='utf-8')
            captured.append(data['module'])
    assert captured
    return {'status': status, 'captured': captured}


if __name__ == '__main__':
    os.environ['CLOUDSDK_CONFIG'] = r'C:\Users\ignac\AppData\Roaming\gcloud'
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['start', 'collect'])
    args = parser.parse_args()
    print(json.dumps(globals()[args.action]()))
