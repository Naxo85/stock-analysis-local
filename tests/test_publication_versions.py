"""Historical confirmed versions, pinned Sheet links and strict query semantics."""
import importlib.util
import json
from pathlib import Path
from urllib.parse import urlsplit, parse_qs
import pytest
from src.local_runner.publication_store import commit,make_manifest,json_text
from src.local_runner.publication_contract import (read_committed, validate_manifest,
    InvalidPublicationVersion, PublicationVersionNotFound)
from src.local_runner.analysis_attempt import record_attempt

ROOT=Path.cwd()
spec=importlib.util.spec_from_file_location('version_consumers',ROOT/'tests/test_publication_consumers.py')
consumer=importlib.util.module_from_spec(spec);spec.loader.exec_module(consumer)
fixture=consumer.fixture


def test_sheet_score_and_report_link_stay_on_original_version_after_commit(tmp_path):
    store=fixture.FakeStore();original=fixture.committed(store,'first')
    reader,_,_,Sheet,parse,_=consumer.modules(consumer.Client(store))
    sheet=Sheet('system',storage_client=consumer.Client(store))
    payload=sheet.load(sheet.index(('CAT',)))['CAT']
    record=parse('CAT',payload,report_url_template='https://example.test/read?symbol={ticker}&format=html')
    query=parse_qs(urlsplit(record.report_url).query)
    assert query['version']==[original['version']] and record.score==8
    values=fixture.artifacts('second')
    for kind in ('json','current','anchor'):
        changed=json.loads(values[kind]);changed['decision']['score']=9;values[kind]=json_text(changed)
    commit(store,make_manifest('CAT',values,{}),values,store.read('CAT/publication.json')[1])
    record_attempt(tmp_path,tmp_path/'attempt','CAT','analyze','failed',
                   policy={'latest_attempt_publication_enabled':True},store=store)
    historical=reader._read_latest_json('CAT',version=query['version'][0])
    assert historical['decision']['score']==8 and historical['analysis_markdown']=='first'
    assert historical['latest_attempt']['status']=='failed'
    assert reader._read_latest_json('CAT')['decision']['score']==9
    assert 'first' in reader._read_latest_text('CAT','html',version=original['version'])
    assert 'último intento' in reader._read_latest_text('CAT','md',version=original['version'])


@pytest.mark.parametrize('version',['../latest','../../private','%2e%2e','A'*64,'f'*63,''])
def test_invalid_version_never_reads_any_object(version):
    def forbidden(name): raise AssertionError('must reject before storage')
    with pytest.raises(InvalidPublicationVersion):read_committed(forbidden,'CAT',version=version)


def test_version_query_rejects_symbol_path_traversal():
    with pytest.raises(InvalidPublicationVersion):
        read_committed(lambda name:None,'../CAT',version='f'*64)


def test_missing_historical_manifest_never_returns_latest_or_alias():
    store=fixture.FakeStore();fixture.committed(store,'current')
    store.objects['CAT/latest.json']=(fixture.artifacts('alias')['json'],999)
    with pytest.raises(PublicationVersionNotFound):
        read_committed(lambda name:store.read(name)[0],'CAT',version='f'*64)


def test_historical_manifest_mismatch_is_rejected():
    store=fixture.FakeStore();first=fixture.committed(store,'first');second=fixture.committed(store,'second')
    store.objects[f"CAT/_versions/{first['version']}/manifest.json"]=(json_text(second),999)
    with pytest.raises(ValueError,match='mismatch'):
        read_committed(lambda name:store.read(name)[0],'CAT',version=first['version'])


def test_version_is_bound_to_artifact_hashes():
    values=fixture.artifacts();manifest=make_manifest('CAT',values,{})
    manifest['files']['json']['sha256']='f'*64
    with pytest.raises(ValueError,match='version_content_mismatch'):validate_manifest(manifest,'CAT')


def test_failed_precommit_version_is_not_historical_publication():
    store=fixture.FakeStore();values=fixture.artifacts('uncommitted');manifest=make_manifest('CAT',values,{})
    for kind,body in values.items():store.objects[manifest['files'][kind]['name']]=(body,1)
    with pytest.raises(PublicationVersionNotFound):
        read_committed(lambda name:store.read(name)[0],'CAT',version=manifest['version'])
    store.objects[f"CAT/_versions/{manifest['version']}/manifest.json"]=(json_text(manifest),2)
    with pytest.raises(ValueError,match='uncommitted'):
        read_committed(lambda name:store.read(name)[0],'CAT',version=manifest['version'])


def test_failed_historical_receipt_after_cas_is_recoverable_by_next_writer():
    store=fixture.FakeStore();values=fixture.artifacts('first');first=make_manifest('CAT',values,{})
    store.fail_at=8;observed=[]
    with pytest.raises(RuntimeError,match='injected'):
        commit(store,first,values,0,on_committed=observed.append)
    assert len(observed)==1
    assert read_committed(lambda name:store.read(name)[0],'CAT',version=first['version'])[0]==values['json']
    store.fail_at=None;fixture.committed(store,'second')
    assert read_committed(lambda name:store.read(name)[0],'CAT',version=first['version'])[0]==values['json']


def test_pinned_history_does_not_depend_on_later_current_pointer():
    store=fixture.FakeStore();first=fixture.committed(store,'first')
    store.objects['CAT/publication.json']=('{}',999)
    body,_=read_committed(lambda name:store.read(name)[0],'CAT',version=first['version'])
    assert json.loads(body)['analysis_markdown']=='first'


def test_exact_historical_reversion_is_rejected_before_pointer_commit():
    store = fixture.FakeStore()
    first = fixture.committed(store, 'first')
    second = fixture.committed(store, 'second')
    before = store.read('CAT/publication.json')
    original = fixture.artifacts('first')
    with pytest.raises(RuntimeError, match='publication_version_already_committed'):
        commit(store, make_manifest('CAT', original, {}), original, before[1])
    assert store.read('CAT/publication.json') == before
    assert read_committed(lambda name: store.read(name)[0], 'CAT')[1] == second
    assert read_committed(lambda name: store.read(name)[0], 'CAT', version=first['version'])[1] == first
