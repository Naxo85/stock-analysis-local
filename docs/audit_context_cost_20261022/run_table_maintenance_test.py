"""Four authorized historical maintenance evaluations, no web/full/publication."""
from copy import deepcopy
from datetime import datetime,timezone
import hashlib,json,sys,time
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from audit import table_pack,table_unpack
from run_table_reading_test import save
from src.local_runner import adaptive_codex as codex
from src.local_runner.adaptive_context import model_context,serialize_model_input,compact_json,unpack_model_context,TRANSPORT_INSTRUCTIONS
from src.local_runner.adaptive_policy import load_policy,daily_decision
from src.local_runner.adaptive_news_research import news_research_instructions
from src.local_runner.adaptive_maintenance import maintenance_schema
from src.local_runner.diff_transport import select_transport,INSTRUCTIONS as DIFF_INSTRUCTIONS
from src.local_runner.semantic_binding import bind_response
from src.local_runner import semantic_binding
from src.local_runner.semantic_report import check_schema,maintenance_document,validation_result,render_document
from src.local_runner.review_contract import coverage_issues
from src.local_runner.adaptive_preflight import check
from src.local_runner.codex_rate_limits import read_codex_rate_limits

TABLE_INSTRUCTIONS='''
TABLE TRANSPORT FOR HISTORICAL EVALUATION: Decode an object with exactly
$table_columns and $table_rows as the ORIGINAL array of objects. Each row cell
belongs to the column at the same position. Decode tables recursively BEFORE
resolving _context_aliases and pointer diffs. Original logical paths, dates,
source IDs and numeric values do not change. No row-position guesses for s IDs.
The configured evaluator is gpt-6-luna high. Earlier model-name references describe
legacy roles, not an instruction to switch models. This is evaluation_only:
use the supplied prepared_at/as_of chronology, never today's date. No tools or
external research. Return the maintenance schema; do not generate a full report.
'''

def run(gate):
 gate=Path(gate);first=json.loads((gate/'results.json').read_text(encoding='utf-8'))
 assert len(first)==8 and all(r['passed'] for r in first)
 folder=ROOT/'logs/table_maintenance_test'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%f')
 folder.mkdir(parents=True,exist_ok=False);print('ARTIFACTS',folder,flush=True)
 policy=load_policy(ROOT);policy['luna_news_research_enabled']=False
 save(folder/'policy.json',policy);save(folder/'preflight.json',check(ROOT,policy))
 save(folder/'quota_before.json',read_codex_rate_limits(cwd=ROOT))
 plan={'gate':str(gate),'tickers':['LEU','TSLA'],'model':'gpt-6-luna','effort':'high',
       'calls':4,'web':False,'repairs':False,'fallback':False,'publication':False,
       'evaluation':'Historical21Oct; format comparison, not a current review or predictive test.'}
 save(folder/'plan.json',plan);results=[]
 for i,ticker in enumerate(plan['tickers']):
  source=ROOT/f'logs/batch/2026-10-21/06-52-46/adaptive/{ticker}'
  context=json.loads((source/'input.json').read_text(encoding='utf-8'))
  reviewed=json.loads((source/'review.json').read_text(encoding='utf-8'))
  context.update(evaluation_only=True,guards=reviewed['guards'],itv=reviewed['itv'],review_flags=reviewed.get('review_flags',[]))
  view=model_context(context);view.pop('research_memory',None);select_transport(view,policy)
  instructions=(source/'triage_instructions.md').read_text(encoding='utf-8')
  instructions=news_research_instructions(instructions,enabled=False,revision=41)
  instructions+='\n\n'+TRANSPORT_INSTRUCTIONS+'\n\n'+DIFF_INSTRUCTIONS+'\n\n'+TABLE_INSTRUCTIONS
  schema=maintenance_schema(view)
  original_wire=serialize_model_input(view);tabular=table_pack(json.loads(original_wire))
  assert table_unpack(tabular)==json.loads(original_wire)
  assert unpack_model_context(table_unpack(tabular))==unpack_model_context(json.loads(original_wire))
  save(folder/ticker/'frozen_context.json',context)
  save(folder/ticker/'source_hashes.json',{name:hashlib.sha256((source/name).read_bytes()).hexdigest()
       for name in ['input.json','policy.json','triage_instructions.md','triage.input.json','triage.receipt.json']})
  for encoding in (['original','tabular'] if i==0 else ['tabular','original']):
   work=folder/ticker/encoding;work.mkdir(parents=True,exist_ok=False)
   wire=original_wire if encoding=='original' else compact_json(tabular)
   # Scope the experimental serializer to THIS process/call. No production code
   # or receipt binding is weakened: both verify the exact actual transformed wire.
   def serialize(data):
    original=serialize_model_input(data)
    if encoding=='original':return original
    transformed=table_pack(json.loads(original))
    assert table_unpack(transformed)==json.loads(original)
    return compact_json(transformed)
   assert serialize(view)==wire
   started=time.monotonic();print('RUN',ticker,encoding,flush=True)
   try:
    with patch.object(codex,'serialize_model_input',side_effect=serialize):
     receipt=codex.call_codex(workspace=work/'workspace',artifacts=work,kind='triage',
       instructions=instructions,data=view,model='gpt-6-luna',effort='high',timeout=240,
       schema=schema,research=False,max_parallel=1)
    value=json.loads(receipt['text']);check_schema(value,schema)
    errors=[];decision=None
    try:
     with patch.object(semantic_binding,'serialize_model_input',side_effect=serialize):
      binding=bind_response(context,receipt,'triage',policy=policy)
     decision=daily_decision(value,context['guards'],model_context(context))
     if decision in ['retain','update']:
      errors.extend(coverage_issues(value,model_context(context)))
     if decision=='update':
      doc=maintenance_document(value,model_context(context),binding=binding)
      valid=validation_result(doc)
      if not valid.ok:errors.extend(valid.errors)
      (work/'candidate.md').write_text(render_document(doc),encoding='utf-8')
    except Exception as exc:
     errors.append({'error':str(exc),'details':getattr(exc,'maintenance_details',None)})
    row={'ticker':ticker,'encoding':encoding,'decision':decision,'validated':not errors,
       'errors':errors,'reason':value.get('reason'),'flags':value.get('risk'),
       'usage':receipt['usage'],'seconds':round(time.monotonic()-started,3),
       'model':receipt['model'],'effort':receipt['reasoning_effort'],
       'research_enabled':receipt['research_enabled'],'wire_characters':len(wire)}
    save(work/'validation.json',row)
   except Exception as exc:
    row={'ticker':ticker,'encoding':encoding,'execution_error':str(exc),'validated':False}
   results.append(row);save(folder/'results.json',results)
   print('DONE',ticker,encoding,'VALID' if row['validated'] else 'INVALID',row.get('decision'),flush=True)
   if 'execution_error' in row:return
 save(folder/'quota_after.json',read_codex_rate_limits(cwd=ROOT))
 print(json.dumps({'calls':len(results),'validated':sum(r['validated'] for r in results),
       'decisions':[(r['ticker'],r['encoding'],r['decision']) for r in results]}),flush=True)

if __name__=='__main__':
 sys.stdout.reconfigure(encoding='utf-8');run(sys.argv[1])
