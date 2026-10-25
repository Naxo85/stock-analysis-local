"""Offline model-admission and changing-order controls; no model/network execution."""
import copy,datetime as dt,json,pathlib,sys,tempfile
root=next(p for p in pathlib.Path(__file__).resolve().parents if (p/'AGENTS.md').exists() and (p/'src').is_dir());sys.path.insert(0,str(root))
from src.local_runner import ibkr_news_capture as c
(root/'.tmp/news_capture_reuse_recheck').mkdir(parents=True,exist_ok=True)
from src.local_runner.ibkr_news_update import _compact_payload
from src.local_runner.adaptive_stage import data_ready
from src.local_runner.adaptive_policy import load_policy
inventory=json.loads((root/'docs/audit_work_20261017/execution/activation/natural_run_20261018/data/raw_acquisitions.json').read_text())
first={}
for row in sorted(inventory,key=lambda x:x['generated_at']):first.setdefault(row['symbol'],row)
policy=load_policy(root);results=[]
with tempfile.TemporaryDirectory() as td:
 for symbol,row in sorted(first.items()):
  old=json.loads((root/'logs/batch/2026-10-18/09-08-40/adaptive'/symbol/'input.json').read_text(encoding='utf-8'))
  p=json.loads((root/row['path']).read_text(encoding='utf-8'));now=dt.datetime.fromisoformat(old['prepared_at'])
  capture=c.get_or_create_capture(pathlib.Path(td),symbol=symbol,provider=p['providerCode'],contract=p['contract'],connection=p['connection'],fetch=lambda:p,now=now,max_age_seconds=86400)
  view=c.derive_probe_payload(capture,start=dt.datetime.fromisoformat(old['news']['window']['start']),window_basis=old['news']['window']['basis'],now=now,max_age_seconds=86400)
  context=copy.deepcopy(old);context['news']=_compact_payload(view)
  data_ready(context,policy,now)
  assert context['news']['items']==old['news']['items'],symbol
  rejected={}
  for name,change in [('partial',lambda x:x['news']['coverage'].update(terminal_received=False)),('stale',lambda x:x['news'].update(provider_fetched_at=(now-dt.timedelta(hours=25)).isoformat())),('window_gap',lambda x:x['news']['window'].update(start=(now+dt.timedelta(days=1)).isoformat()))]:
   bad=copy.deepcopy(context);change(bad)
   try:data_ready(bad,policy,now)
   except RuntimeError as err:rejected[name]=str(err)
   else:raise AssertionError(symbol+':accepted '+name)
  results.append({'symbol':symbol,'admission':'passed','news_items_exact':True,'negative_controls':rejected})
 # Explicitly make a later simulated order contain an additional provider article.
 item=min(inventory,key=lambda x:x['raw_count']);p=json.loads((root/item['path']).read_text(encoding='utf-8'))
 newer=copy.deepcopy(p);cutoff=dt.datetime.fromisoformat(p['generated_at'])+dt.timedelta(hours=1);initial=cutoff.replace(microsecond=0)+dt.timedelta(seconds=1)
 article=copy.deepcopy(p['raw_headlines'][0]);article.update(articleId='offline-new-order-article',headline_raw='Independent offline control: newly arriving article',published_at_raw=cutoff.isoformat())
 newer['raw_headlines'].insert(0,article);newer.update(generated_at=cutoff.isoformat(),raw_headline_count=len(newer['raw_headlines']))
 newer['window']['end']=cutoff.isoformat();cov=newer['coverage'];cov['requested_window']['end']=cutoff.isoformat();cov['initial_cursor_exclusive']=initial.isoformat();cov['returned_count']+=1
 pg=cov['pages'][0];pg.update(cursor_exclusive=initial.isoformat(),wire_start=initial.strftime('%Y-%m-%d %H:%M:%S.0'),latest=cutoff.isoformat(),returned_count=pg['returned_count']+1)
 selected,before,after=c._filtered(newer['raw_headlines'],dt.datetime.fromisoformat(newer['window']['start']),cutoff)
 newer.update(headlines=selected,headline_count=len(selected),filtered_before_start_count=before,filtered_after_end_count=after)
 calls=[]
 args=dict(symbol=p['ticker'],provider=p['providerCode'],contract=p['contract'],connection=p['connection'],now=cutoff+dt.timedelta(seconds=1),max_age_seconds=86400)
 oldcap=c.get_or_create_capture(pathlib.Path(td)/'old_order',fetch=lambda:(calls.append('old'),p)[1],**args)
 newcap=c.get_or_create_capture(pathlib.Path(td)/'new_order',fetch=lambda:(calls.append('new'),newer)[1],**args)
 unchanged=c.get_or_create_capture(pathlib.Path(td)/'old_order',fetch=lambda:(_ for _ in ()).throw(AssertionError('refetch same valid scope')),**args)
 assert calls==['old','new'] and oldcap==unchanged and oldcap['capture_sha256']!=newcap['capture_sha256']
 assert not any(x['articleId']=='offline-new-order-article' for x in oldcap['payload']['raw_headlines'])
 assert any(x['articleId']=='offline-new-order-article' for x in newcap['payload']['raw_headlines'])
result={'status':'passed','natural_context_admission':len(results),'natural_context_negative_controls':3*len(results),'new_order_fetches_new_headline':True,'same_order_keeps_explicit_original_cutoff':True,'historical_artifacts_read_only':True,'models_or_network':False,'cases':results,'limitation':'Changed-news case is a deterministic control of scope behavior, not a fresh provider observation or evidence of financial alpha.'}
(root/'.tmp/news_capture_reuse_recheck/independent_admission_and_orders.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
print(json.dumps({k:v for k,v in result.items() if k!='cases'},indent=2))
