import copy,json,hashlib,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT))
from src.local_runner.adaptive_context import model_context
from src.local_runner.adaptive_policy import daily_decision
from src.local_runner.semantic_binding import bind_response
from src.local_runner.adaptive_news_research import attach_news_research
from src.local_runner.review_contract import coverage_issues
from src.local_runner.semantic_report import maintenance_document,reference_document,validation_result,render_document,_validate_geometry
from src.local_runner.semantic_sources import raise_issues
from src.local_runner.plan_scope import project_plan
from src.local_runner.reader_report import apply_selection
from src.local_runner.support_validity import apply_review
RUN=ROOT/'logs/batch/2026-10-18/09-08-40/adaptive';OUT=Path(__file__).parent
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def differences(a,b,p=''):
 if a==b:return []
 if isinstance(a,dict) and isinstance(b,dict):
  return [z for k in sorted(set(a)|set(b)) for z in differences(a.get(k),b.get(k),p+'/'+k)]
 return [p]
rows=[];started=time.monotonic()
for base in sorted(RUN.iterdir()):
 row={'symbol':base.name};rows.append(row)
 try:
  context=read(base/'input.json'); review=read(base/'review.json'); response=read(base/'triage.json');receipt=read(base/'triage.receipt.json');current=read(base/'publish/current_state.json')
  context['guards']=copy.deepcopy(review['guards']);context['itv']=copy.deepcopy(review['itv']);context['review_flags']=copy.deepcopy(review['review_flags'])
  receipt['text']=(base/'triage.response').read_text(encoding='utf-8')
  assert json.loads(receipt['text'])==response,'stored_response_differs_from_triage'
  binding=bind_response(context,receipt,'triage');row['exact_receipt_binding']=True
  attach_news_research(context,base,'triage',receipt,response)
  view=model_context(context);decision=daily_decision(response,context['guards'],view);row['decision']=decision
  assert decision==response['decision'],'decision_changed'
  raise_issues(coverage_issues(response,view));row['coverage_guard']=True
  old=reference_document(context['reference'],verify_projection=True)
  if decision=='update':
   doc=maintenance_document(response,view,binding=binding);val=validation_result(doc);assert val.ok,str(val.errors);row['maintenance_guard']=True
  else:
   assert decision=='retain';doc=project_plan(copy.deepcopy(old),40);row['maintenance_guard']='retain: inherited finance authenticated, no new level rescoring'
  doc['metadata']['reader_format_revision']=40
  apply_selection(doc,old,response.get('reader_review'),revision=40)
  apply_review(doc,old,response.get('support_validity_review'),view)
  _validate_geometry(doc['plan'],view);row['geometry_guard']=True
  row['semantic_differences']=differences(doc,current['semantic_report']['data'])
  md=render_document(doc);published=current['analysis_markdown'];
  if published.startswith('Mantenimiento técnico: Luna · '):published=published.split('\n\n',1)[1]
  row['render_exact']=md.replace('\r\n','\n')==published.replace('\r\n','\n')
  row['ok']=not row['semantic_differences'] and row['render_exact']
 except Exception as exc:row.update(ok=False,error=type(exc).__name__+': '+str(exc))
 if len(rows)%10==0:print(len(rows),sum(bool(r.get('ok')) for r in rows),flush=True)
result={'scope':'Offline pure financial replay; exact frozen receipt binding, recorded guards/ITV and local research reconstruction. No model, network, data refresh, mutation of originals, stage.analyze or publication. Financial judgment remains independently reviewed, not proved by guards.','elapsed_seconds':round(time.monotonic()-started,3),'passed':sum(r.get('ok') is True for r in rows),'total':len(rows),'rows':rows}
(OUT/'financial_guard_replay.json').write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding='utf-8')
print(json.dumps({'passed':result['passed'],'total':len(rows),'errors':[r for r in rows if not r['ok']]}),flush=True)
