"""Read auth mode only; never print credentials."""
import os,json,sys,subprocess,tempfile,queue,threading
import tomllib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from src.local_runner.codex_generator import require_codex
from src.local_runner.codex_rate_limits import _send_message,_read_until_response,_stop_app_server
env=dict(os.environ)
env['CODEX_HOME']=str(Path.home()/'.codex')
cfg=tomllib.loads((Path.home()/'.codex/config.toml').read_text(encoding='utf-8'))
print(json.dumps({'credential_store':cfg.get('cli_auth_credentials_store'),
                  'forced_login':cfg.get('forced_login_method')}))
for k in ['OPENAI_API_KEY','CODEX_API_KEY','OPENAI_BASE_URL']:env.pop(k,None)
print(json.dumps({'cli':require_codex(),'codex_home':env.get('CODEX_HOME'),
                  'api_env_present':[k for k in ['OPENAI_API_KEY','CODEX_API_KEY'] if os.environ.get(k)]}))
with tempfile.TemporaryFile(mode='w+',encoding='utf-8') as err:
 p=subprocess.Popen([require_codex(),'app-server','--stdio','-c','forced_login_method="chatgpt"',
                     '-c','cli_auth_credentials_store="file"'],
    cwd=ROOT,env=env,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=err,text=True,
    encoding='utf-8',creationflags=subprocess.CREATE_NO_WINDOW)
 q=queue.Queue()
 def collect():
  for l in p.stdout:q.put(l)
  q.put(None)
 threading.Thread(target=collect,daemon=True).start();lines=[]
 try:
  _send_message(p,{'id':1,'method':'initialize','params':{'clientInfo':{'name':'auth_mode_check','version':'1'}}})
  _read_until_response(q,lines,response_id=1,timeout=30)
  _send_message(p,{'method':'initialized','params':{}})
  _send_message(p,{'id':2,'method':'account/read','params':{'refreshToken':False}})
  _read_until_response(q,lines,response_id=2,timeout=30)
  r=next(json.loads(l) for l in reversed(lines) if json.loads(l).get('id')==2)
  print(json.dumps({'account_type':(r.get('result',{}).get('account') or {}).get('type'),
                    'requires_auth':r.get('result',{}).get('requiresOpenaiAuth'), 'error':r.get('error')}))
 finally:_stop_app_server(p)
for directory in [Path.home()/'.codex', Path(env['CODEX_HOME']) if env.get('CODEX_HOME') else Path.home()/'.codex']:
 f=directory/'auth.json'
 if f.exists():
  d=json.loads(f.read_text(encoding='utf-8'));print(json.dumps({'auth_file':str(f),'auth_mode':d.get('auth_mode'),
       'has_chatgpt_tokens':bool(d.get('tokens'))}))
