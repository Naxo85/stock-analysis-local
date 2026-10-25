"""Offline H03/H04/H11/H12: original receipts, isolated mutations, CAS and readers."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import importlib
import json
from pathlib import Path
import shutil
import sys
from unittest.mock import patch

import pytest
from src.local_runner.receipt_integrity import authenticate_response, text_digest
from src.local_runner.publication_bundle import seal_bundle, verify_bundle
from src.local_runner.publication_contract import (read_committed, digest_json, read_attempt, with_attempt)
from src.local_runner.publication_store import make_manifest, commit, json_text
from src.local_runner.analysis_attempt import record_attempt, record_failure
from src.local_runner import adaptive_stage as stage
from src.local_runner.adaptive_budget import read_json, write_json

ROOT = Path.cwd()
ORIGINAL = ROOT / 'logs/batch/2026-10-16/15-58-24/adaptive'


class FakeStore:
    def __init__(self):
        self.objects = {}
        self.serial = 0
        self.writes = 0
        self.fail_at = None
        self.lose_ack = False
    def read(self, name):
        return self.objects.get(name, (None, 0))
    def write(self, name, body, generation):
        self.writes += 1
        if self.fail_at == self.writes:
            raise RuntimeError('injected_write_failure')
        if self.read(name)[1] != generation:
            raise RuntimeError('precondition_failed')
        self.serial += 1
        self.objects[name] = (body, self.serial)
        if self.lose_ack and name.endswith('/publication.json'):
            self.lose_ack = False
            raise RuntimeError('ack_lost')


def artifacts(label='old'):
    payload = {'symbol': 'CAT', 'analysis_status': 'ok', 'generated_at': '2026-10-16T10:00:00Z',
               'analysis_markdown': label, 'decision': {'score': 8}, 'plan': {}}
    return {'json': json_text(payload), 'md': label, 'html': '<html><body>'+label+'</body></html>',
            'current': json_text(payload), 'anchor': json_text(payload),
            'review': json_text({'reviewed_at': '2026-10-16T11:00:00Z'})}


def committed(store, label):
    values = artifacts(label)
    manifest = make_manifest('CAT', values, {'reviewed_at': label})
    return commit(store, manifest, values, store.read('CAT/publication.json')[1])


def original_copy(tmp_path, symbol='CAT'):
    source = ORIGINAL / symbol
    if not source.exists():
        pytest.skip('local original corpus unavailable')
    work = tmp_path / symbol
    shutil.copytree(source, work)
    review = read_json(work / 'review.json')
    review.pop('published_at', None)
    review.pop('bundle_manifest_sha256', None)
    seal_bundle(work, symbol, review)
    write_json(work / 'review.json', review)
    return work, review


def test_all_original_successful_receipts_authenticate_without_changes():
    accepted = 0
    for base in ('2026-10-14/16-07-07', '2026-10-16/15-58-24'):
        for path in (ROOT / 'logs/batch' / base / 'adaptive').glob('*/*.receipt.json'):
            before = path.read_bytes()
            receipt = json.loads(before)
            if receipt.get('exit_code') == 0:
                assert authenticate_response(path.parent, path.name.split('.')[0], receipt).strip()
                accepted += 1
                assert path.read_bytes() == before
    if not accepted:
        pytest.skip('local original corpus unavailable')
    assert accepted >= 101


@pytest.mark.parametrize('mutation', ['response', 'events', 'call'])
def test_legacy_receipt_independent_corruption_rejected(tmp_path, mutation):
    work, _ = original_copy(tmp_path, 'IBKR')
    receipt = read_json(work / 'report.receipt.json')
    if mutation == 'response':
        path = work / 'report.response'
        path.write_text(path.read_text(encoding='utf-8') + ' altered', encoding='utf-8')
    elif mutation == 'events':
        (work / 'report.events.jsonl').write_text('', encoding='utf-8')
    else:
        path = work / 'report.call.json'
        value = read_json(path); value['model'] = 'changed'; write_json(path, value)
    with pytest.raises(RuntimeError):
        authenticate_response(work, 'report', receipt)


def test_durable_response_digest_rejects_changed_response(tmp_path):
    work, _ = original_copy(tmp_path, 'IBKR')
    receipt = read_json(work / 'report.receipt.json')
    body = (work / 'report.response').read_text(encoding='utf-8')
    receipt['response_sha256'] = text_digest(body)
    assert authenticate_response(work, 'report', receipt) == body
    (work / 'report.response').write_text(body + 'x', encoding='utf-8')
    with pytest.raises(RuntimeError, match='digest_mismatch'):
        authenticate_response(work, 'report', receipt)


@pytest.mark.parametrize('name', ['latest.json', 'latest.md', 'latest.html', 'input.json', 'triage.response', 'policy.json'])
def test_sealed_original_independent_mutations_rejected(tmp_path, name):
    work, review = original_copy(tmp_path)
    verify_bundle(work, 'CAT', review)
    path = work / ('publish/output/CAT/' + name) if name.startswith('latest.') else work / name
    original = path.read_text(encoding='utf-8')
    if name == 'latest.json':
        value = json.loads(original); value['plan']['entry'] = {'lower': 800, 'upper': 810}
        path.write_text(json.dumps(value), encoding='utf-8')
    else:
        path.write_text(original + ' ', encoding='utf-8')
    with pytest.raises(RuntimeError, match='changed'):
        verify_bundle(work, 'CAT', review)


def test_unsealed_legacy_staging_cannot_publish(tmp_path):
    work = tmp_path / 'CAT'; work.mkdir()
    write_json(work / 'review.json', {'analysis_status': 'ok'})
    with patch.object(stage, '_copy_json') as copy, patch.object(stage.one, '_upload') as upload:
        with pytest.raises(RuntimeError, match='requires_receipt_revalidation'):
            stage.publish(tmp_path, work, 'CAT')
        copy.assert_not_called(); upload.assert_not_called()
    assert read_json(work / 'attempt.json')['status'] == 'failed'


@pytest.mark.parametrize('entry', ['analyze', 'publish'])
def test_review_ok_does_not_bypass_freshness(tmp_path, entry):
    work, review = original_copy(tmp_path)
    policy = read_json(work / 'policy.json')
    context = read_json(work / 'input.json')
    future = datetime.fromisoformat(context['prepared_at']) + timedelta(days=3)
    class Clock(datetime):
        @classmethod
        def now(cls, tz=None): return future
    with patch.object(stage, 'datetime', Clock), patch('src.local_runner.publication_authority.committed_payload', return_value=(None,None)), patch.object(stage, 'model_call') as model, patch.object(stage.one, '_upload') as upload:
        with pytest.raises(RuntimeError, match='stale|fresh|snapshot'):
            if entry == 'analyze':
                stage.analyze(tmp_path, work, 'CAT', tmp_path/'budget.json', False)
            else:
                stage.publish(tmp_path, work, 'CAT')
        model.assert_not_called(); upload.assert_not_called()


@pytest.mark.parametrize('fail_at', range(1,8))
def test_each_precommit_failure_keeps_previous_complete_version(fail_at):
    store = FakeStore(); old = committed(store, 'old'); old_generation = store.read('CAT/publication.json')[1]
    values = artifacts('new'); new = make_manifest('CAT', values, {})
    store.fail_at = store.writes + fail_at
    with pytest.raises(RuntimeError, match='injected'):
        commit(store, new, values, old_generation)
    for kind in ('json','md','html','current','anchor','review'):
        body, manifest = read_committed(lambda name: store.read(name)[0], 'CAT', kind)
        assert manifest['version'] == old['version']
        assert body == artifacts('old')[kind]
    store.fail_at = None
    result = commit(store, new, values, old_generation)
    assert result['version'] == new['version']


def test_lost_commit_ack_reuses_exact_version_and_only_finishes_history_receipt():
    store = FakeStore(); values = artifacts('new'); new = make_manifest('CAT',values,{})
    store.lose_ack = True
    with pytest.raises(RuntimeError, match='ack_lost'):
        commit(store,new,values,0)
    writes = store.writes
    result = commit(store,new,values,0)
    assert result['version'] == new['version'] and store.writes == writes + 1
    assert store.read(f"CAT/_versions/{new['version']}/manifest.json")[0] is not None


def test_concurrent_writer_cannot_overwrite_confirmed_version():
    store = FakeStore(); committed(store,'winner')
    loser = artifacts('loser')
    with pytest.raises(RuntimeError, match='concurrent'):
        commit(store,make_manifest('CAT',loser,{}),loser,0)
    assert read_committed(lambda name: store.read(name)[0], 'CAT','md')[0] == 'winner'


@pytest.mark.parametrize('bad', ['malformed_pointer','missing_artifact','wrong_digest'])
def test_present_invalid_manifest_never_falls_back_to_legacy_alias(bad):
    store = FakeStore(); manifest=committed(store,'confirmed')
    store.objects['CAT/latest.json']=(json_text({'unsafe':'legacy alias'}),100)
    if bad=='malformed_pointer': store.objects['CAT/publication.json']=('{}',101)
    elif bad=='missing_artifact': del store.objects[manifest['files']['json']['name']]
    else: store.objects[manifest['files']['json']['name']]=('tampered',102)
    with pytest.raises(ValueError):
        read_committed(lambda name: store.read(name)[0], 'CAT')


def test_failed_attempt_preserves_financial_payload_and_date(tmp_path):
    store=FakeStore(); manifest=committed(store,'dated')
    before=store.read('CAT/publication.json')
    body=read_committed(lambda name:store.read(name)[0],'CAT')[0]
    attempt=record_attempt(tmp_path,tmp_path/'work','CAT','analyze','failed',RuntimeError('validation'),
        policy={'latest_attempt_publication_enabled':True},store=store)
    result=with_attempt(json.loads(body),read_attempt(lambda name:store.read(name)[0],'CAT'),manifest)
    assert result['latest_attempt']['status']=='failed'
    assert result['generated_at']=='2026-10-16T10:00:00Z'
    assert result['analysis_markdown']=='dated'
    assert store.read('CAT/publication.json')==before


def test_old_attempt_cannot_replace_newer_success(tmp_path):
    store=FakeStore(); policy={'latest_attempt_publication_enabled':True}
    record_attempt(tmp_path,tmp_path/'old','CAT','prepare','pending',policy=policy,store=store)
    newer=record_attempt(tmp_path,tmp_path/'new','CAT','publish','succeeded',policy=policy,store=store)
    record_attempt(tmp_path,tmp_path/'old','CAT','analyze','failed',policy=policy,store=store)
    assert json.loads(store.read('CAT/attempt.json')[0])==newer


def test_remote_attempt_switch_is_independent_and_off_by_default(tmp_path):
    with patch('src.local_runner.publication_store.GcsStore', side_effect=AssertionError('NO_REMOTE')):
        record_attempt(tmp_path,tmp_path/'work','CAT','prepare','pending',policy={'publication_protocol':'manifest-v1'})
    assert read_json(tmp_path/'output/CAT/latest_attempt.json')['status']=='pending'


def test_deployed_contract_copies_are_exact():
    source=(ROOT/'src/local_runner/publication_contract.py').read_bytes()
    for path in ('gcp_functions/reports_reader/publication_contract.py','gcp_services/mobile_api/publication_contract.py','gcp_services/stock_controller/src/stock_analysis/publication_contract.py'):
        assert (ROOT/path).read_bytes()==source


def test_legacy_review_replays_original_receipts_without_model_and_preserves_dates(tmp_path):
    work, review = original_copy(tmp_path)
    context = read_json(work/'input.json')
    original_payload = read_json(work/'publish/output/CAT/latest.json')
    receipt_hashes = {p.name:text_digest(p.read_text(encoding='utf-8')) for p in work.glob('*.receipt.json')}
    review.pop('bundle_manifest_sha256'); write_json(work/'review.json',review)
    (work/'bundle.manifest.json').unlink()
    # Corrupt only the derived mirror. Replay must reconstruct from receipts.
    corrupt=deepcopy(original_payload); corrupt['plan']['entry']={'lower':800,'upper':810}
    write_json(work/'publish/output/CAT/latest.json',corrupt)
    frozen=datetime.fromisoformat(context['prepared_at'])+timedelta(minutes=30)
    class Clock(datetime):
        @classmethod
        def now(cls,tz=None): return frozen
    with patch.object(stage,'datetime',Clock), patch.object(stage,'call_codex',side_effect=AssertionError('NO_MODEL')), patch.object(stage,'reserve',side_effect=AssertionError('NO_RESERVATION')):
        result=stage.analyze(tmp_path,work,'CAT',tmp_path/'budget.json',False,reuse_only=True)
    rebuilt=read_json(work/'publish/output/CAT/latest.json')
    assert rebuilt['plan']['entry']==original_payload['plan']['entry']
    assert rebuilt['generated_at']==original_payload['generated_at']
    assert result['reviewed_at']==review['reviewed_at']
    assert rebuilt['last_full_report_at']==original_payload['last_full_report_at']
    assert {p.name:text_digest(p.read_text(encoding='utf-8')) for p in work.glob('*.receipt.json')}==receipt_hashes
    verify_bundle(work,'CAT',result)


def test_manifest_publication_retry_after_alias_failure_keeps_confirmed_dates(tmp_path):
    work, review=original_copy(tmp_path)
    context=read_json(work/'input.json'); policy=read_json(work/'policy.json')
    policy['publication_protocol']='manifest-v1'; write_json(work/'policy.json',policy)
    seal_bundle(work,'CAT',review); write_json(work/'review.json',review)
    payload=read_json(work/'publish/output/CAT/latest.json')
    store=FakeStore()
    frozen=datetime.fromisoformat(context['prepared_at'])+timedelta(minutes=30)
    class Clock(datetime):
        @classmethod
        def now(cls,tz=None): return frozen
    def legacy(uri):
        return context['sol_reference'] if uri.endswith('/reference.json') else context['reference']
    with patch.object(stage,'datetime',Clock), patch.object(stage,'_read_json_gcs',side_effect=legacy), patch('src.local_runner.publication_store.GcsStore',return_value=store), patch.object(stage,'_copy_json'), patch.object(stage.one,'_upload',side_effect=[RuntimeError('alias_failure'),None]):
        with pytest.raises(RuntimeError,match='alias_failure'):
            stage.publish(tmp_path,work,'CAT')
        confirmed=json.loads(store.read('CAT/publication.json')[0])
        assert read_json(work/'attempt.json')['status']=='failed'
        assert read_json(work/'attempt.json')['committed_version']==confirmed['version']
        frozen += timedelta(days=3)
        result=stage.publish(tmp_path,work,'CAT')
        assert result['published_at']==confirmed['committed_at']
    loaded,manifest=read_committed(lambda name:store.read(name)[0],'CAT')
    assert json.loads(loaded)['generated_at']==payload['generated_at']
    assert manifest==confirmed
    assert read_json(work/'attempt.json')['status']=='succeeded'
