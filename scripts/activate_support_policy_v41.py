"""Check source41 integration and atomically enable new local preparations only."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import deploy_support_origins_v41 as deploy

OUT = deploy.OUT


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_sources():
    records = {}
    for kind in ('raw', 'slim'):
        deploy.verify_package(kind)
        value = deploy.service(kind)
        expected = 'support-resistances-'+kind+'-'+deploy.SUFFIX
        if deploy.traffic(value) != [(expected, 100)]:
            raise RuntimeError('source41_not_active:'+kind)
        if deploy.digest(deploy.runtime(value)) != deploy.load(kind+'-before.json')['runtime_sha256']:
            raise RuntimeError('runtime_changed:'+kind)
        records[kind] = deploy.summary(kind, value)
    return records


def capture():
    """One technical request, no model/report/batch; raw technical mirror is normal."""
    from src.local_runner import run_one
    from src.local_runner.support_origins import require_support_origins
    from src.local_runner.technical_preparation import require_capture, require_price_history
    path = OUT/'live_cls_capture.json'
    if path.exists():
        raise RuntimeError('capture_exists_no_duplicate_probe')
    requested = [{'type': 'range_bottom_3_6m', 'level': 290.88, 'date': '2026-08-19', 'touches': 2}]
    slim = run_one._fetch_slim('CLS', support_origins=requested)
    path.write_text(json.dumps(slim, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    require_capture(slim)
    require_price_history(slim)
    require_support_origins(slim, requested)
    observation = slim['levels']['support_origins'][0]
    result = {'verified_at': datetime.now(timezone.utc).isoformat(), 'symbol': 'CLS',
              'as_of': slim['as_of'], 'source_revision': slim['data_contract_revision'],
              'status': observation['status'], 'level': observation['level'],
              'reason': observation['observation_reason'], 'source': observation['source_record'],
              'capture_sha256': sha(path), 'model_calls': 0, 'financial_publications': 0,
              'technical_requests': 1, 'technical_mirror_may_refresh': True}
    deploy.save('live_verification.json', result)
    return {key: value for key, value in result.items() if key != 'source'}


def activate():
    from src.local_runner.adaptive_policy import validate_policy
    records = verify_sources()
    live = deploy.load('live_verification.json')
    if live['source_revision'] < 41 or sha(OUT/'live_cls_capture.json') != live['capture_sha256']:
        raise RuntimeError('source41_live_verification_missing')
    tests = ET.parse(OUT.parent/'tests.xml').getroot()
    suites = tests.findall('testsuite') if tests.tag == 'testsuites' else [tests]
    count = sum(int(suite.get('tests', '0')) for suite in suites)
    if count < 300 or any(int(suite.get(key, '0')) for suite in suites for key in ('errors', 'failures', 'skipped')):
        raise RuntimeError('final_test_suite_not_complete')
    policy_path = ROOT/'config/codex_analysis.json'
    expected = json.loads((ROOT/'.tmp/support41_baseline/config/codex_analysis.json').read_text(encoding='utf-8'))
    before = json.loads(policy_path.read_text(encoding='utf-8'))
    if before != expected or before['routing_revision'] != 40:
        raise RuntimeError('policy_changed_before_activation')
    current_hash = sha(policy_path)
    after = dict(before, routing_revision=41)
    validate_policy(after)
    temp = policy_path.with_name('codex_analysis41.pending.json')
    if temp.exists():
        raise RuntimeError('pending_activation_exists_review_before_retry')
    with temp.open('x', encoding='utf-8', newline='\n') as handle:
        handle.write(json.dumps(after, ensure_ascii=False, indent=2)+'\n')
        handle.flush()
        os.fsync(handle.fileno())
    if sha(policy_path) != current_hash:
        raise RuntimeError('policy_changed_during_activation')
    os.replace(temp, policy_path)
    if json.loads(policy_path.read_text(encoding='utf-8')) != after:
        raise RuntimeError('policy_readback_mismatch')
    result = {'activated_at': datetime.now(timezone.utc).isoformat(), 'routing_revision': 41,
              'before_sha256': current_hash, 'after_sha256': sha(policy_path),
              'only_policy_change': 'routing_revision:40->41', 'tests': count,
              'sources': records, 'models_and_weights_unchanged': True,
              'frozen_orders_reused_unchanged': True, 'model_calls': 0, 'financial_publications': 0}
    deploy.save('policy_activation.json', result)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['capture', 'activate'])
    parser.add_argument('--execute', action='store_true')
    args = parser.parse_args()
    if not args.execute:
        parser.error('explicit --execute required')
    print(json.dumps(globals()[args.action](), ensure_ascii=False, indent=2))
