"""Installed-CLI transport regression, local fake model only; no quota/auth."""
import sys, json, threading, tempfile, os
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.local_runner import adaptive_codex as codex, adaptive_sessions as sessions
from test_adaptive_analysis import triage
from src.local_runner.adaptive_policy import TRIAGE_SCHEMA
calls=[]
class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args): pass
    def do_POST(self):
        body=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        calls.append(body)
        text=json.dumps(triage())
        item={'type':'message','id':'msg_local_'+str(len(calls)),'role':'assistant','content':[{'type':'output_text','text':text}],'status':'completed'}
        events=[{'type':'response.created','response':{'id':'resp_local','status':'in_progress'}},
                {'type':'response.output_item.done','output_index':0,'item':item},
                {'type':'response.completed','response':{'id':'resp_local','status':'completed','output':[item],
                    'usage':{'input_tokens':100,'output_tokens':10,'total_tokens':110,'input_tokens_details':{'cached_tokens':0}}}}]
        self.send_response(200); self.send_header('Content-Type','text/event-stream'); self.end_headers()
        for event in events: self.wfile.write(('data: '+json.dumps(event)+'\n\n').encode())

server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
threading.Thread(target=server.serve_forever,daemon=True).start()
tmp=Path(tempfile.mkdtemp(prefix='codex-session-test-'))
env=dict(os.environ)
env['CODEX_HOME']=str(tmp/'home')
(tmp/'home').mkdir()
for key in ('OPENAI_API_KEY','CODEX_API_KEY','OPENAI_BASE_URL','CODEX_THREAD_ID'): env.pop(key,None)
overrides={'model_provider':'session_test','model_providers.session_test.name':'Local session test',
 'model_providers.session_test.base_url':f'http://127.0.0.1:{server.server_port}/v1',
 'model_providers.session_test.requires_openai_auth':False,'model_providers.session_test.wire_api':'responses',
 'model_providers.session_test.request_max_retries':0,'model_providers.session_test.stream_max_retries':0,
 'model_providers.session_test.supports_websockets':False}
extra=[]
for key,value in overrides.items():extra.extend(['-c',key+'='+json.dumps(value)])
def remove_login(args):
    result=[]; n=0
    while n<len(args):
        if args[n]=='-c' and args[n+1].startswith('forced_login_method='):n+=2;continue
        result.append(args[n]);n+=1
    return result
real_run=codex.run_bounded
real_reset=sessions.reset_session
def fake_transport(command,**kw):
    kw['env']=env
    command=remove_login(command)
    command[2:2]=['--ignore-user-config','--ignore-rules']
    offset=command.index('resume') if 'resume' in command else len(command)-1
    command[offset:offset]=extra
    return real_run(command,**kw)
def local_reset(thread_id,**kw):
    kw['env']=env
    kw['config_args']=remove_login(kw['config_args'])+extra
    return real_reset(thread_id,**kw)
with patch.object(codex,'run_bounded',side_effect=fake_transport),patch.object(sessions,'reset_session',side_effect=local_reset):
    receipts=[]
    groups=[('triage', ('FIRST_SENTINEL','SECOND_SENTINEL','THIRD_SENTINEL'), 'gpt-6-luna','medium',TRIAGE_SCHEMA,False),
            ('report', ('REPORT_FIRST','REPORT_SECOND'), 'gpt-6.1-sol','high',None,True)]
    sentinels=[symbol for group in groups for symbol in group[1]]
    for kind, symbols, model, effort, schema, research in groups:
        instructions=codex.TRIAGE_INSTRUCTIONS if kind=='triage' else codex.report_instructions('Local diagnostic report policy.',research=True)
        for symbol in symbols:
            result=codex.call_codex(workspace=tmp/'workspace',artifacts=tmp/symbol,kind=kind,
                instructions=instructions,data={'symbol':symbol},model=model,effort=effort,
                timeout=30,schema=schema,research=research)
            receipts.append({k:v for k,v in result.items() if k.startswith('session_')})
    print('RECEIPTS',json.dumps(receipts))
    print('REQUESTS',len(calls))
    for body in calls:
        encoded=json.dumps(body.get('input'))
        print('WIRE',body.get('prompt_cache_key'),'items',len(body.get('input',[])),
            'sentinels',[s for s in sentinels if s in encoded])
    assert all(r['session_history_cleared'] for r in receipts), receipts
    assert len(calls)==5
    assert len({b['prompt_cache_key'] for b in calls})==2
    for model in ('gpt-6-luna','gpt-6.1-sol'):
        group=[b for b in calls if b['model']==model]
        assert len({b['prompt_cache_key'] for b in group})==1
        assert all(len(b['input'])==len(group[0]['input']) for b in group)
    assert all(sum(s in json.dumps(b['input']) for s in sentinels)==1 for b in calls)
print('LOCAL_TRANSPORT_PASS',str(tmp))
server.shutdown()
