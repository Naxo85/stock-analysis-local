"""Deploy the reviewed source41 overlay; never run models or publish finance.

Each mutation is explicit. Preserve the current runtime, environment and tags;
build on the currently active immutable image, stage without traffic, then switch.
Evidence contains hashes/references, never plaintext environment secrets.
"""
import argparse
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'docs/audit_support_constraints_20261019/implementation/activation'
WORK = ROOT / '.tmp/support41_deploy'
PROJECT = 'recipe-generator-429817'
ACCOUNT = 'ignacioanefra@gmail.com'
REGION = 'europe-southwest1'
SUFFIX = 'origins41-20261019'
TAG = 'origins41'


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def gc(*args):
    executable = shutil.which('gcloud.cmd')
    if not executable:
        raise RuntimeError('gcloud.cmd unavailable')
    result = subprocess.run(['cmd.exe', '/d', '/c', executable, *args,
        '--account='+ACCOUNT, '--project='+PROJECT, '--format=json', '--quiet'],
        capture_output=True, text=True, encoding='utf-8', timeout=180)
    if result.returncode:
        raise RuntimeError('gcloud_action_failed: ' + result.stderr[-2200:])
    return json.loads(result.stdout) if result.stdout.strip() else {}


def save(name, value):
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT/name).write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')


def load(name):
    return json.loads((OUT/name).read_text(encoding='utf-8'))


def service(kind):
    return gc('run', 'services', 'describe', 'support-resistances-'+kind, '--region='+REGION)


def traffic(value):
    return sorted((row['revisionName'], row['percent']) for row in value['status']['traffic'] if row.get('percent'))


def tags(value):
    return {row['tag']: row['revisionName'] for row in value['status']['traffic'] if row.get('tag')}


def runtime(value):
    template = deepcopy(value['spec']['template'])
    template['metadata'].pop('name', None)
    annotations = template['metadata'].get('annotations', {})
    for key in ('run.googleapis.com/client-name', 'run.googleapis.com/client-version'):
        annotations.pop(key, None)
    for container in template['spec']['containers']:
        container.pop('image', None)
    return template


def summary(kind, value):
    return {'kind': kind, 'at': datetime.now(timezone.utc).isoformat(),
            'spec_sha256': digest(value['spec']), 'runtime_sha256': digest(runtime(value)),
            'traffic': value['status']['traffic'], 'tags': tags(value),
            'url': value['status']['url'], 'image': value['spec']['template']['spec']['containers'][0]['image']}


def inspect(kind):
    value = service(kind)
    active = traffic(value)
    if len(active) != 1 or active[0][1] != 100:
        raise RuntimeError('single_active_revision_required')
    revision = gc('run', 'revisions', 'describe', active[0][0], '--region='+REGION)
    image = revision['spec']['containers'][0]['image']
    if '@sha256:' not in image or value['spec']['template']['spec']['containers'][0]['image'] != image:
        raise RuntimeError('active_template_and_immutable_image_must_match')
    record = summary(kind, value)
    record['active_revision'] = active[0][0]
    record['conditions'] = revision['status']['conditions']
    if (OUT/(kind+'-before.json')).exists():
        if load(kind+'-before.json')['spec_sha256'] != record['spec_sha256']:
            raise RuntimeError('saved_baseline_differs_review_before_replacement')
    else:
        save(kind+'-before.json', record)
    return record


def package(kind):
    before = load(kind+'-before.json')
    value = service(kind)
    if digest(value['spec']) != before['spec_sha256']:
        raise RuntimeError('service_changed_since_inspection')
    dest = WORK/kind
    dest.mkdir(parents=True, exist_ok=True)
    names = ['main.py', 'support_origins.py'] if kind == 'raw' else ['main.py']
    files = {}
    for name in names:
        source = ROOT/'gcp_functions'/('support_resistances_'+kind)/name
        shutil.copyfile(source, dest/name)
        files[source.relative_to(ROOT).as_posix()] = sha(source)
    verifier = ROOT/'scripts/verify_support41_image.py'
    shutil.copyfile(verifier, dest/verifier.name)
    files[verifier.relative_to(ROOT).as_posix()] = sha(verifier)
    docker = 'FROM '+before['image']+'\n'
    docker += ''.join('COPY '+name+' /app/'+name+'\n' for name in names+[verifier.name])
    docker += 'RUN python -m py_compile '+' '.join('/app/'+name for name in names)+'\n'
    docker += 'RUN cd /app && python verify_support41_image.py '+kind+'\n'
    (dest/'Dockerfile').write_text(docker, encoding='utf-8')
    (dest/'.gcloudignore').write_text('__pycache__/\n*.pyc\n', encoding='utf-8')
    record = {'kind': kind, 'base_image': before['image'], 'files': files,
              'dockerfile_sha256': sha(dest/'Dockerfile')}
    save(kind+'-package.json', record)
    return record


def verify_package(kind):
    record = load(kind+'-package.json')
    for name, expected in record['files'].items():
        if sha(ROOT/name) != expected or sha(WORK/kind/Path(name).name) != expected:
            raise RuntimeError('source_changed_after_packaging:'+name)
    if sha(WORK/kind/'Dockerfile') != record['dockerfile_sha256']:
        raise RuntimeError('dockerfile_changed')
    return record


def build(kind):
    verify_package(kind)
    if digest(service(kind)['spec']) != load(kind+'-before.json')['spec_sha256']:
        raise RuntimeError('service_changed_before_build')
    if (OUT/(kind+'-build.json')).exists():
        raise RuntimeError('build_exists_check_status_instead')
    tag = f'{REGION}-docker.pkg.dev/{PROJECT}/cloud-run-source-deploy/support-resistances-{kind}:{SUFFIX}'
    result = gc('builds', 'submit', str(WORK/kind), '--tag='+tag, '--async')
    save(kind+'-build.json', result)
    return {'kind': kind, 'id': result['id'], 'status': result['status']}


def status(kind):
    result = gc('builds', 'describe', load(kind+'-build.json')['id'])
    save(kind+'-build-status.json', result)
    return {'kind': kind, 'id': result['id'], 'status': result['status'],
            'images': result.get('results', {}).get('images', [])}


def stage(kind):
    verify_package(kind)
    built = status(kind)
    if built['status'] != 'SUCCESS':
        raise RuntimeError('build_not_successful')
    image = built['images'][0]['name'].rsplit(':', 1)[0]+'@'+built['images'][0]['digest']
    before = service(kind)
    if digest(before['spec']) != load(kind+'-before.json')['spec_sha256']:
        raise RuntimeError('service_changed_before_stage')
    gc('run', 'deploy', 'support-resistances-'+kind, '--region='+REGION,
       '--image='+image, '--revision-suffix='+SUFFIX, '--no-traffic', '--tag='+TAG)
    after = service(kind)
    if (runtime(before) != runtime(after) or traffic(before) != traffic(after)
            or any(tags(after).get(key) != val for key, val in tags(before).items())):
        raise RuntimeError('unexpected_runtime_traffic_or_tag_change')
    record = summary(kind, after)
    target = next(row for row in after['status']['traffic'] if row.get('tag') == TAG)
    record.update(revision=target['revisionName'], tag_url=target['url'])
    if record['revision'] != 'support-resistances-'+kind+'-'+SUFFIX or record['image'] != image:
        raise RuntimeError('unexpected_staged_revision')
    save(kind+'-staged.json', record)
    return record


def probe(kind):
    import requests
    staged = load(kind+'-staged.json')
    if digest(service(kind)['spec']) != staged['spec_sha256']:
        raise RuntimeError('service_changed_before_probe')
    response = requests.get(staged['tag_url'], timeout=40, allow_redirects=False)
    if response.status_code != 400 or 'symbol' not in response.json().get('error', ''):
        raise RuntimeError('no_symbol_probe_failed')
    record = {'kind': kind, 'revision': staged['revision'], 'status': response.status_code,
              'body': response.json(), 'no_symbol_no_provider_no_mirror': True}
    save(kind+'-probe.json', record)
    return record


def activate(kind):
    verify_package(kind)
    staged, baseline = load(kind+'-staged.json'), load(kind+'-before.json')
    if load(kind+'-probe.json')['revision'] != staged['revision']:
        raise RuntimeError('staged_revision_not_probed')
    before = service(kind)
    if digest(before['spec']) != staged['spec_sha256']:
        raise RuntimeError('service_changed_before_activation')
    if kind == 'slim':
        if traffic(service('raw')) != [('support-resistances-raw-'+SUFFIX, 100)]:
            raise RuntimeError('raw41_must_be_active_before_slim41')
    gc('run', 'services', 'update-traffic', 'support-resistances-'+kind,
       '--region='+REGION, '--to-revisions='+staged['revision']+'=100')
    after = service(kind)
    if (traffic(after) != [(staged['revision'], 100)]
            or digest(runtime(after)) != baseline['runtime_sha256'] or tags(after) != tags(before)):
        raise RuntimeError('activation_invariant_failure')
    record = summary(kind, after)
    record['runtime_preserved'] = True
    save(kind+'-active.json', record)
    return record


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['inspect', 'package', 'build', 'status', 'stage', 'probe', 'activate'])
    parser.add_argument('kind', choices=['raw', 'slim'])
    parser.add_argument('--execute', action='store_true')
    args = parser.parse_args()
    if args.action in ('build', 'stage', 'activate') and not args.execute:
        parser.error('mutation requires --execute')
    print(json.dumps(globals()[args.action](args.kind), ensure_ascii=False, indent=2))
