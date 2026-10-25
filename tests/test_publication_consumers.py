"""End-to-end producer/reader contract using memory-only GCS, never cloud."""
import importlib.util
import json
from pathlib import Path
import sys
from unittest.mock import patch
import pytest
from google.api_core.exceptions import NotFound
from src.local_runner.publication_contract import read_committed
from src.local_runner.analysis_attempt import record_attempt
from src.local_runner.publication_store import json_text

ROOT=Path.cwd()
spec=importlib.util.spec_from_file_location('publication_fixtures',ROOT/'tests/test_publication_integrity.py')
fixture=importlib.util.module_from_spec(spec);spec.loader.exec_module(fixture)

class Blob:
    def __init__(self,bucket,name): self.bucket=bucket;self.name=name
    @property
    def generation(self): return self.bucket.store.read(self.name)[1]
    def download_as_bytes(self,**kwargs):
        body,_=self.bucket.store.read(self.name)
        if body is None: raise NotFound(self.name)
        return body.encode('utf-8')
    def download_as_text(self,**kwargs): return self.download_as_bytes().decode('utf-8')
    def exists(self): return self.bucket.store.read(self.name)[0] is not None

class Bucket:
    def __init__(self,store): self.store=store
    def blob(self,name): return Blob(self,name)
    def list_blobs(self,prefix): return [self.blob(name) for name in self.store.objects if name.startswith(prefix)]

class Client:
    def __init__(self,store): self.store=store
    def bucket(self,name): return Bucket(self.store)


def modules(client):
    sys.path.insert(0,str(ROOT/'gcp_functions/reports_reader'))
    spec=importlib.util.spec_from_file_location('integrity_reports_reader',ROOT/'gcp_functions/reports_reader/main.py')
    reader=importlib.util.module_from_spec(spec)
    with patch('google.cloud.storage.Client',return_value=client): spec.loader.exec_module(reader)
    sys.path.insert(0,str(ROOT/'gcp_services/mobile_api'))
    from sources import PublishedSources
    from projection import project
    from stock_analysis.analysis_worker.reports import GcsAnalysisReportStore,parse_analysis_report
    from stock_analysis.controller.analysis_sheet import _score_cell
    return reader,PublishedSources,project,GcsAnalysisReportStore,parse_analysis_report,_score_cell


@pytest.mark.parametrize('status',['pending','failed','blocked'])
def test_producer_attempt_reaches_all_readers_without_redating(tmp_path,status):
    store=fixture.FakeStore();manifest=fixture.committed(store,'confirmed')
    store.objects['CAT/latest.json']=(json_text({'symbol':'CAT','analysis_status':'ok','generated_at':'2099','analysis_markdown':'UNCONFIRMED ALIAS'}),100)
    store.objects['CAT/latest.md']=('UNCONFIRMED ALIAS',101)
    store.objects['CAT/latest.html']=('UNCONFIRMED ALIAS',102)
    store.objects['runtime/analysis-reports/CAT.json']=(fixture.artifacts('UNCONFIRMED MIRROR')['json'],103)
    reader,Mobile,project,Sheet,parse,score_cell=modules(Client(store))
    sheet=Sheet('system',storage_client=Client(store));before=sheet.index(('CAT',))
    attempt=record_attempt(tmp_path,tmp_path/'work','CAT','analyze',status,
        policy={'latest_attempt_publication_enabled':True},store=store)
    web=reader._read_latest_json('CAT')
    assert web['analysis_markdown']=='confirmed' and web['generated_at']=='2026-10-16T10:00:00Z'
    assert web['latest_attempt']['status']==status
    assert 'último intento' in reader._read_latest_text('CAT','md')
    assert '<aside role="status">' in reader._read_latest_text('CAT','html')
    assert 'UNCONFIRMED' not in reader._read_latest_text('CAT','html')
    _,mobile,mirror,_=Mobile(storage_client=Client(store),sheets_session=object()).report_pair('CAT')
    assert mobile['publication_version']==manifest['version'] and mirror is None
    layout={'blocks':[],'groups':[{'id':'g','tickers':['CAT']}],
            'general_panel':{'start_row':2,'column':'A','lines':[]}}
    stock=project(layout,{}, {},{}, {'CAT':mobile},{},[])['stocks'][0]
    assert stock['last_attempt_status']==status and stock['last_attempt_at']==attempt['at']
    assert stock['analysis_at']=='2026-10-16T10:00:00Z' and stock['attempt_notice']
    after=sheet.index(('CAT',));assert after.version!=before.version
    payload=sheet.load(after)['CAT']
    assert payload['analysis_markdown']=='confirmed'
    record=parse('CAT',payload,report_url_template='https://example.test/{ticker}')
    cell=score_cell(record,'#FFFFFF')
    assert record.score==8 and record.generated_at.isoformat()=='2026-10-16T10:00:00+00:00'
    assert '⚠' in cell['userEnteredValue']['stringValue'] and 'último intento' in cell['note']


@pytest.mark.parametrize('reader_kind',['web','mobile','sheet'])
def test_consumers_reject_corrupt_committed_artifact_without_using_alias(reader_kind):
    store=fixture.FakeStore();manifest=fixture.committed(store,'confirmed')
    store.objects[manifest['files']['json']['name']]=('tampered',200)
    store.objects['CAT/latest.json']=(fixture.artifacts('legacy')['json'],201)
    store.objects['runtime/analysis-reports/CAT.json']=(fixture.artifacts('mirror')['json'],202)
    reader,Mobile,_,Sheet,_,_=modules(Client(store))
    with pytest.raises(ValueError):
        if reader_kind=='web': reader._read_latest_json('CAT')
        elif reader_kind=='mobile': Mobile(storage_client=Client(store),sheets_session=object()).report_pair('CAT')
        else:
            sheet=Sheet('system',storage_client=Client(store));sheet.load(sheet.index(('CAT',)))


def test_runner_anchor_and_current_use_same_confirmed_version_not_alias(tmp_path):
    store=fixture.FakeStore();fixture.committed(store,'confirmed')
    from src.local_runner.publication_authority import committed_payload
    from src.local_runner.analysis_state import load_reference_payload
    with patch('src.local_runner.analysis_state.read_text_gcs',side_effect=lambda uri:store.read(uri.split('/',3)[3])[0]):
        anchor,am=committed_payload('CAT','anchor');current,cm=committed_payload('CAT','current')
        assert anchor['analysis_markdown']==current['analysis_markdown']=='confirmed'
        assert am['version']==cm['version']
        assert load_reference_payload('CAT')==anchor


def test_sheet_index_pins_version_when_new_commit_arrives_before_load():
    store=fixture.FakeStore();fixture.committed(store,'first')
    _,_,_,Sheet,_,_=modules(Client(store));sheet=Sheet('system',storage_client=Client(store))
    index=sheet.index(('CAT',));fixture.committed(store,'second')
    assert sheet.load(index)['CAT']['analysis_markdown']=='first'
    assert sheet.load(sheet.index(('CAT',)))['CAT']['analysis_markdown']=='second'


@pytest.mark.parametrize('protocol',['legacy','manifest-v1'])
def test_staging_mutation_during_remote_read_never_changes_publication(tmp_path,protocol):
    from src.local_runner import adaptive_stage as stage
    from src.local_runner.publication_bundle import seal_bundle
    from src.local_runner.adaptive_budget import read_json,write_json
    from datetime import datetime,timedelta
    work,review=fixture.original_copy(tmp_path)
    policy=read_json(work/'policy.json');policy['publication_protocol']=protocol
    write_json(work/'policy.json',policy);seal_bundle(work,'CAT',review);write_json(work/'review.json',review)
    context=read_json(work/'input.json');expected=read_json(work/'publish/output/CAT/latest.json')
    store=fixture.FakeStore();seen=[]
    frozen=datetime.fromisoformat(context['prepared_at'])+timedelta(minutes=30)
    class Clock(datetime):
        @classmethod
        def now(cls,tz=None): return frozen
    def remote(uri):
        changed=dict(expected);changed['plan']=dict(expected['plan'],entry={'lower':800,'upper':810})
        write_json(work/'publish/output/CAT/latest.json',changed)
        (work/'publish/output/CAT/latest.md').write_text('unvalidated mutation',encoding='utf-8')
        return context['sol_reference'] if uri.endswith('/reference.json') else context['reference']
    def upload(snapshot_root,*args,**kwargs):
        seen.append(read_json(snapshot_root/'output/CAT/latest.json'))
        assert (snapshot_root/'output/CAT/latest.md').read_text(encoding='utf-8')==expected['analysis_markdown']
    with patch.object(stage,'datetime',Clock),patch.object(stage,'_read_json_gcs',side_effect=remote),patch('src.local_runner.publication_authority.committed_payload',return_value=(None,None)),patch('src.local_runner.publication_store.GcsStore',return_value=store),patch.object(stage.one,'_upload',side_effect=upload),patch.object(stage,'_copy_json'):
        stage.publish(tmp_path,work,'CAT')
    assert seen==[expected]
    if protocol=='manifest-v1':
        payload,_=read_committed(lambda name:store.read(name)[0],'CAT')
        current,_=read_committed(lambda name:store.read(name)[0],'CAT','current')
        assert json.loads(payload)['plan']==json.loads(current)['plan']==expected['plan']


def test_expiration_during_uploads_rejected_before_commit():
    from src.local_runner.publication_store import commit,make_manifest
    store=fixture.FakeStore();prior=fixture.committed(store,'old')
    values=fixture.artifacts('expired');manifest=make_manifest('CAT',values,{})
    def expired(): raise RuntimeError('snapshot_expired_during_upload')
    with pytest.raises(RuntimeError,match='expired'):
        commit(store,manifest,values,store.read('CAT/publication.json')[1],before_commit=expired)
    assert json.loads(store.read('CAT/publication.json')[0])==prior
    # Confirmed retries need no new freshness admission or writes.
    old=fixture.artifacts('old');confirmed=make_manifest('CAT',old,{'reviewed_at':'old'})
    assert commit(store,confirmed,old,0,before_commit=expired)==prior


def test_anchor_local_fallback_does_not_advance_on_upload_failure(tmp_path):
    from src.local_runner.analysis_state import save_reference_payload
    path=tmp_path/'data/analysis_state/CAT/reference.json';path.parent.mkdir(parents=True)
    path.write_text('{"old":true}',encoding='utf-8')
    with patch('src.local_runner.analysis_state.require_gcloud',return_value='mock'),patch('src.local_runner.analysis_state.subprocess.run',side_effect=RuntimeError('upload_failure')):
        with pytest.raises(RuntimeError):save_reference_payload(tmp_path,'CAT',{'new':True})
    assert json.loads(path.read_text(encoding='utf-8'))=={'old':True}


@pytest.mark.parametrize('provider_at,coverage,status',[
    ('2026-10-10T00:00:00Z',{'status':'complete','terminal_received':True,'has_more':False},'ok'),
    (None,{'status':'complete','terminal_received':True,'has_more':False},'ok'),
    ('2026-10-17T10:00:00Z',{'status':'unknown'},'ok'),
    ('2026-10-17T10:00:00Z',{'status':'complete','terminal_received':True,'has_more':False},'failed')])
def test_new_analyst_wrapper_does_not_hide_old_unknown_or_failed_provider(tmp_path,provider_at,coverage,status):
    from src.local_runner.analyst_recent_actions import load_recent_analyst_actions
    from src.local_runner import adaptive_stage as stage
    from datetime import datetime,timezone
    state={'as_of':'2026-10-17T10:00:00Z','status':status,'firms':{},
           'last_update':{'provider_fetched_at':provider_at,'coverage':coverage}}
    path=tmp_path/'data/analyst_ratings/CAT/current.json';path.parent.mkdir(parents=True)
    path.write_text(json.dumps(state),encoding='utf-8')
    analyst=load_recent_analyst_actions(tmp_path,'CAT',since='2026-10-01T00:00:00Z',limit=None)
    assert analyst['provider_fetched_at']==provider_at and analyst['coverage']==coverage
    assert analyst['status']==status
    context={'symbol':'CAT','routing_revision':3,'prepared_at':state['as_of'],
             'slim':{'as_of':state['as_of'],'latest_price':100,'levels':{'supports':[{'level':99}]}},
             'news':{'status':'ok','items':[],'generated_at':state['as_of']},
             'analyst_actions':analyst,'reference':{},'sol_reference':{}}
    with pytest.raises(RuntimeError):stage.data_ready(context,{'max_snapshot_age_hours':24},datetime(2026,10,17,10,tzinfo=timezone.utc))


@pytest.mark.parametrize('status', ['pending', 'failed', 'blocked'])
def test_first_attempt_without_valid_report_remains_visible_without_finance(tmp_path, status):
    from flask import Flask, request
    store = fixture.FakeStore()
    attempt = record_attempt(tmp_path, tmp_path/'first', 'CAT', 'prepare', status,
        policy={'latest_attempt_publication_enabled': True}, store=store)
    reader, Mobile, project, Sheet, parse, score_cell = modules(Client(store))
    with Flask('first-attempt').test_request_context('/?symbol=CAT'):
        response = reader.read_stock_report(request)
        assert response.status_code == 404
        body = response.get_json()
        assert body['latest_attempt'] == attempt and body['analysis_status'] == 'unavailable'
        assert body['generated_at'] is None and 'Todavía no hay' in body['attempt_notice']
        assert 'Se conserva' not in body['attempt_notice']
    _, mobile, mirror, _ = Mobile(storage_client=Client(store), sheets_session=object()).report_pair('CAT')
    layout = {'blocks': [], 'groups': [{'id': 'g', 'tickers': ['CAT']}],
              'general_panel': {'start_row': 2, 'column': 'A', 'lines': []}}
    stock = project(layout, {}, {}, {}, {'CAT': mobile}, {'CAT': mirror}, [])['stocks'][0]
    assert stock['last_attempt_status'] == status and stock['last_attempt_at'] == attempt['at']
    assert stock['analysis_at'] is None and stock['analysis_status'] == 'unavailable'
    assert stock['decision']['score'] is None and not stock['plan']
    assert 'Todavía no hay' in stock['attempt_notice']
    sheet = Sheet('system', storage_client=Client(store))
    record = parse('CAT', sheet.load(sheet.index(('CAT',)))['CAT'], report_url_template='https://example.test/{ticker}')
    assert record.generated_at is None and record.score is None and record.entry is None
    cell = score_cell(record, '#FFFFFF', thesis=True)
    assert cell['userEnteredValue']['stringValue'] == 'Ver ⚠'
    assert 'Todavía no hay' in cell['note'] and 'informe histórico' not in cell['note']
