"""Independent rejection controls using an actual original provider payload."""
import copy,datetime as dt,json,pathlib,shutil,sys,tempfile
root=next(p for p in pathlib.Path(__file__).resolve().parents if (p/'AGENTS.md').exists() and (p/'src').is_dir());sys.path.insert(0,str(root))
from src.local_runner import ibkr_news_capture as c
(root/'.tmp/news_capture_reuse_recheck').mkdir(parents=True,exist_ok=True)
inventory=json.loads((root/'docs/audit_work_20261017/execution/activation/natural_run_20261018/data/raw_acquisitions.json').read_text())
item=min(inventory,key=lambda x:x['raw_count'])
p=json.loads((root/item['path']).read_text(encoding='utf-8'))
clock=dt.datetime.fromisoformat(p['generated_at']);checks=[]
identity=dict(symbol=p['ticker'],provider=p['providerCode'],contract=p['contract'],connection=p['connection'])
def call(scope, fetch=lambda:copy.deepcopy(p), now=clock+dt.timedelta(seconds=1), age=86400, **overrides):
 args={**identity,**overrides}
 return c.get_or_create_capture(scope,**args,fetch=fetch,now=now,max_age_seconds=age)
def reject(name,callback):
 try: callback()
 except c.CaptureError as error: checks.append({'name':name,'result':'rejected','error':str(error)})
 else: raise AssertionError(name+' accepted')
with tempfile.TemporaryDirectory() as td:
 base=pathlib.Path(td)
 for name,change in [('terminal_missing',lambda x:x['coverage'].pop('terminal_received')),
  ('has_more_true',lambda x:x['coverage'].update(has_more=True)),
  ('page_terminal_false',lambda x:x['coverage']['pages'][0].update(terminal_received=False)),
  ('legacy_method',lambda x:x['coverage'].update(method='legacy_start_stop')),
  ('wrong_provider',lambda x:x.update(providerCode='BRFUPDN')),
  ('wrong_contract',lambda x:x['contract'].update(conId=x['contract']['conId']+1)),
  ('missing_raw_count',lambda x:x.pop('raw_headline_count'))]:
  bad=copy.deepcopy(p);change(bad);scope=base/name
  reject(name,lambda:call(scope,fetch=lambda:bad))
  assert not list((scope/'keys').glob('*.json'))
  call(scope)
  checks.append({'name':name+'_retry_valid','result':'passed'})
 scope=base/'clock';cap=call(scope)
 for name,now,age in [('future',clock-dt.timedelta(seconds=1),86400),('stale',clock+dt.timedelta(seconds=86401),86400),('zero_age',clock,0),('nan_age',clock,float('nan')),('infinite_age',clock,float('inf')),('bool_age',clock,True)]:
  reject(name,lambda:call(scope,now=now,age=age,fetch=lambda:(_ for _ in ()).throw(AssertionError('must not refetch'))))
 view=c.derive_probe_payload(cap,start=clock-dt.timedelta(days=365),window_basis='older_anchor',now=clock+dt.timedelta(minutes=30),max_age_seconds=86400)
 assert view['generated_at']==p['generated_at'] and view['window']['end']==p['window']['end'] and view['coverage']==p['coverage']
 view['raw_headlines'].clear()
 assert call(scope)['payload']['raw_headlines']==p['raw_headlines']
 checks.append({'name':'derive_original_clock_and_no_shared_mutable_reference','result':'passed'})
 copied=base/'copied';shutil.copytree(scope,copied)
 reject('scope_copy_rejected',lambda:call(copied))
 obj=next((scope/'objects').glob('*.json'));body=json.loads(obj.read_text());body['payload']['headline_count']+=1;obj.write_text(json.dumps(body))
 reject('changed_object_no_refetch',lambda:call(scope,fetch=lambda:(_ for _ in ()).throw(AssertionError('must not refetch'))))
 count=[]
 for name in ('order_a','order_b'):
  call(base/name,fetch=lambda:(count.append(1),copy.deepcopy(p))[1])
 assert len(count)==2;checks.append({'name':'different_orders_acquire_independently','result':'passed'})
result={'status':'passed','controls':len(checks),'fixture':item['path'],'checks':checks,'historical_artifacts_read_only':True,'network_or_models':False}
(root/'.tmp/news_capture_reuse_recheck/independent_core_negative.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'status':result['status'],'controls':len(checks)}))
