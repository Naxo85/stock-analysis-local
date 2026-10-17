"""Offline process protocol tests: no Codex model, no cloud writes."""
import json
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path
from unittest.mock import patch
import pytest
from src.local_runner import adaptive_codex as codex, adaptive_preflight as preflight
from src.local_runner.codex_call_evidence import inspect


def events(state='completed', message='{"ok":true}'):
    rows = [{'type':'thread.started','thread_id':str(uuid.uuid4())}, {'type':'turn.started'}]
    if state == 'completed':
        rows += [{'type':'item.completed','item':{'type':'agent_message','text':message}},
                 {'type':'turn.completed','usage':{'input_tokens':100,'output_tokens':10}}]
    elif state == 'failed':
        rows += [{'type':'turn.failed','error':{'message':'connection reset'}}]
    return '\n'.join(json.dumps(row) for row in rows) + '\n'


@pytest.mark.parametrize('state', ['completed','failed','unknown'])
def test_timeout_preserves_and_reconciles_process_evidence(state):
    wire = events(state)
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        def execute(command, **kw):
            kw['stdout'].write(wire); kw['stdout'].flush()
            kw['stderr'].write('partial diagnostic'); kw['stderr'].flush()
            raise subprocess.TimeoutExpired(command, 1)
        with patch.object(codex,'require_codex',return_value='offline'), patch.object(codex,'run_bounded',side_effect=execute) as cli:
            def call():
                return codex.call_codex(workspace=root/'work',artifacts=root/'out',kind='report',
                    instructions='policy',data={},model='gpt-6.1-sol',effort='high',timeout=1)
            if state == 'completed':
                assert call()['text'] == '{"ok":true}'
            else:
                with pytest.raises(RuntimeError,match='model_timeout'): call()
        assert cli.call_count == 1
        receipt = json.loads((root/'out/report.receipt.json').read_text())
        assert receipt['timeout_reconciliation']['state'] == state
        assert receipt['retryable_failure'] == (state == 'failed')
        assert (root/'out/report.events.jsonl').read_text() == wire
        assert (root/'out/report.stderr.txt').read_text() == 'partial diagnostic'
        assert receipt['session_id']
        assert not receipt['session_history_cleared']


@pytest.mark.parametrize('mutation', ['garbage','conflict','second_turn','missing_usage','partial'])
def test_ambiguous_terminal_is_never_success(mutation):
    wire, response = events(), ''
    if mutation == 'garbage': wire += 'not-json'
    elif mutation == 'conflict': response = '{"other":true}'
    elif mutation == 'second_turn': wire += '{"type":"turn.started"}\n'
    elif mutation == 'missing_usage': wire = wire.replace('"input_tokens": 100','"input_tokens": null')
    elif mutation == 'partial': wire = events('unknown')
    assert inspect(wire,response)['state'] == 'unknown'


def test_slow_boot_does_not_consume_execution_budget():
    with tempfile.TemporaryDirectory() as tmp:
        code = "import time,json; time.sleep(.7); print(json.dumps({'type':'turn.started'}),flush=True); time.sleep(.5); print('finished',flush=True)"
        result = codex._run_recorded([sys.executable,'-u','-c',code],artifacts=Path(tmp),kind='test',
                                    timeout=.8,text=True,encoding='utf-8')
        assert result.returncode == 0 and 'finished' in result.stdout


@pytest.mark.parametrize('signal', [False,True])
def test_boot_and_execution_both_remain_bounded(signal):
    with tempfile.TemporaryDirectory() as tmp:
        start = "print('{\"type\":\"turn.started\"}',flush=True); " if signal else ''
        code = 'import time; ' + start + 'time.sleep(8)'
        with pytest.raises(subprocess.TimeoutExpired) as exc:
            codex._run_recorded([sys.executable,'-u','-c',code],artifacts=Path(tmp),kind='test',
                               timeout=.6,text=True,encoding='utf-8')
        assert exc.value.phase == ('execution' if signal else 'startup')


def test_read_only_preflight_reconnects_once_never_retries_mutation_or_auth():
    with patch.object(preflight,'_rpc_once',side_effect=[TimeoutError('startup'),{'ok':True}]) as rpc, patch.object(preflight.time,'sleep'):
        assert preflight.rpc('account/rateLimits/read',{},Path('.')) == {'ok':True}
        assert rpc.call_count == 2
    for method,error in [('account/read',RuntimeError('codex_app_server_error: auth')),
                         ('turn/start',TimeoutError('startup'))]:
        with patch.object(preflight,'_rpc_once',side_effect=error) as rpc:
            with pytest.raises(type(error)):preflight.rpc(method,{},Path('.'))
            assert rpc.call_count == 1

@pytest.mark.parametrize('state,tamper', [('completed',None),('failed',None),('unknown',None),('failed','input_sha256'),('failed','events')])
def test_stage_timeout_reuse_retry_or_quarantine(tmp_path,state,tamper):
    from test_adaptive_analysis import StageTests, POLICY
    from src.local_runner import adaptive_stage as stage, adaptive_budget as budget
    root=tmp_path; work=root/'CAT'; work.mkdir()
    (work/'instructions.md').write_text('stable')
    policy={**POLICY,'report_timeout_seconds':1}; ledger=root/'budget.json'
    context=StageTests().context()
    wire=events(state)
    def execute(command,**kw):
        kw['stdout'].write(wire);kw['stdout'].flush()
        raise subprocess.TimeoutExpired(command,1)
    with patch.object(budget,'read_codex_rate_limits',return_value={'primary':{'used_percent':20}}), patch.object(codex,'require_codex',return_value='offline'), patch.object(codex,'run_bounded',side_effect=execute) as cli:
        if state=='completed':
            first=stage.model_call(root,work,'CAT',ledger,policy,'report',context)
            again=stage.model_call(root,work,'CAT',ledger,policy,'report',context)
            assert first['text']==again['text']; assert cli.call_count==1
            return
        with pytest.raises(RuntimeError,match='model_timeout'):
            stage.model_call(root,work,'CAT',ledger,policy,'report',context)
    if tamper=='input_sha256':
        r=stage.read_json(work/'report.receipt.json');r[tamper]='changed';stage.write_json(work/'report.receipt.json',r)
    elif tamper=='events':
        (work/'report.events.jsonl').write_text(events('unknown'))
    def success(command,**kw):
        Path(command[command.index('--output-last-message')+1]).write_text('{"ok":true}')
        return subprocess.CompletedProcess(command,0,events(),'')
    with patch.object(budget,'read_codex_rate_limits',return_value={'primary':{'used_percent':20}}), patch.object(codex,'require_codex',return_value='offline'), patch.object(codex,'run_bounded',side_effect=success) as cli, patch('src.local_runner.adaptive_sessions.reset_session'):
        if state=='failed' and tamper is None:
            stage.model_call(root,work,'CAT',ledger,policy,'report',context)
            stage.model_call(root,work,'CAT',ledger,policy,'report',context)
            assert cli.call_count==1
            assert len(stage.read_json(ledger)['failed_call_history']['CAT:report'])==1
            assert len(list((work/'failed_calls').glob('*/report.events.jsonl')))==1
        else:
            with pytest.raises(RuntimeError,match='already_reserved'):
                stage.model_call(root,work,'CAT',ledger,policy,'report',context)
            cli.assert_not_called()
