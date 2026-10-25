"""Three authorized, isolated Sol6.1 low evaluations; never publish or repair."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import time

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from src.local_runner.adaptive_context import model_context, unpack_model_context, serialize_model_input, TRANSPORT_INSTRUCTIONS
from src.local_runner.diff_transport import select_transport, INSTRUCTIONS as DIFF_INSTRUCTIONS
from src.local_runner.adaptive_policy import validate_policy, daily_decision
from src.local_runner.adaptive_maintenance import maintenance_schema
from src.local_runner.adaptive_news_research import news_research_instructions
from src.local_runner.adaptive_preflight import check
from src.local_runner.adaptive_codex import call_codex
from src.local_runner.semantic_binding import bind_response
from src.local_runner.semantic_report import maintenance_document, render_document, validation_result
from src.local_runner.review_contract import coverage_issues
from src.local_runner.codex_rate_limits import read_codex_rate_limits

def save(path, value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')

def prepare():
    folder=ROOT/'logs/sol_low_test'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%f')
    folder.mkdir(parents=True,exist_ok=False)
    print('ARTIFACTS',folder,flush=True)
    hashes={}
    for symbol in ('AMD','CLS','IREN'):
        print('PREPARE',symbol,flush=True)
        source=ROOT/'logs/batch/2026-10-23/14-18-22/adaptive'/symbol
        context=json.loads((source/'input.json').read_text(encoding='utf-8'))
        wire=unpack_model_context(json.loads((source/'triage.input.json').read_text(encoding='utf-8')))
        original_receipt=json.loads((source/'triage.receipt.json').read_text(encoding='utf-8'))
        assert original_receipt.get('web_search_count',0)==0
        context.update(evaluation_only=True)
        for key in ('guards','itv','review_flags'):
            if key in wire: context[key]=wire[key]
        policy=json.loads((source/'policy.json').read_text(encoding='utf-8'))
        policy.update(triage_model='gpt-6.1-sol',triage_effort='low',luna_news_research_enabled=False)
        validate_policy(policy)
        # Keep the original frozen policy/instructions otherwise: the later
        # volume guidance is deliberately absent, isolating model/effort changes.
        assert policy.get('volume_calculation_guidance') is None
        view=model_context(context)
        view.pop('research_memory',None)
        select_transport(view,policy)
        instructions=news_research_instructions((source/'triage_instructions.md').read_text(encoding='utf-8'),enabled=False,revision=41)
        instructions+='\n\n'+TRANSPORT_INSTRUCTIONS+'\n\n'+DIFF_INSTRUCTIONS
        instructions+='\n\nEVALUATION ONLY: gpt-6.1-sol with low reasoning. Use the supplied frozen prepared_at/as_of chronology. Legacy Luna/Sol role labels do not change the selected model. No tools, external research, full report, repair or publication. Return the ordinary maintenance JSON; retain/update/escalate/blocked keep their existing meanings. Do not force retention or suppress a real risk.'
        case=folder/symbol
        save(case/'frozen_context.json',context)
        save(case/'policy.json',policy)
        save(case/'schema.json',maintenance_schema(view))
        save(case/'view.json',view)
        (case/'instructions.md').write_text(instructions,encoding='utf-8')
        (case/'expected.input.json').write_text(serialize_model_input(view),encoding='utf-8')
        for name in ('input.json','policy.json','triage_instructions.md','triage.input.json','triage.receipt.json','triage.response'):
            path=source/name;hashes[str(path)]=hashlib.sha256(path.read_bytes()).hexdigest()
    path=ROOT/'config/codex_analysis.json'
    hashes[str(path)]=hashlib.sha256(path.read_bytes()).hexdigest()
    save(folder/'original_hashes.json',hashes)
    save(folder/'plan.json',{'model':'gpt-6.1-sol','effort':'low','tickers':['AMD','CLS','IREN'],
        'maximum_model_calls':3,'research':False,'repairs':False,'full':False,'publication':False,
        'baseline':'Original Luna high23Oct; no fresh same-input Sol medium comparator.',
        'scope':'Historical same-source first-call financial maintenance, not recovery or current financial advice.'})
    print('PREPARED',folder,flush=True)

def execute(folder):
    folder=Path(folder).resolve()
    plan=json.loads((folder/'plan.json').read_text(encoding='utf-8'))
    effort=plan['effort']
    assert effort in ('low','medium')
    assert folder.is_relative_to((ROOT/'logs'/('sol_'+effort+'_test')).resolve())
    policy=json.loads((folder/plan['tickers'][0]/'policy.json').read_text(encoding='utf-8'))
    save(folder/'preflight.json',check(ROOT,policy))
    save(folder/'quota_before.json',read_codex_rate_limits(cwd=ROOT))
    rows=[]
    for symbol in plan['tickers']:
        case=folder/symbol
        assert not (case/'triage.call.json').exists() and not (case/'triage.response').exists()
        context=json.loads((case/'frozen_context.json').read_text(encoding='utf-8'))
        view=json.loads((case/'view.json').read_text(encoding='utf-8'))
        schema=json.loads((case/'schema.json').read_text(encoding='utf-8'))
        print('CALL',symbol,'gpt-6.1-sol',effort,flush=True)
        started=time.monotonic()
        try:
            receipt=call_codex(workspace=case/'workspace',artifacts=case,kind='triage',
                instructions=(case/'instructions.md').read_text(encoding='utf-8'),data=view,
                model='gpt-6.1-sol',effort=effort,timeout=240,schema=schema,research=False,max_parallel=1)
        except Exception as exc:
            rows.append({'ticker':symbol,'execution_error':str(exc),'validated':False})
            save(folder/'results.json',rows)
            print('STOP execution error',str(exc),flush=True)
            break
        print('RESPONSE',symbol,round(time.monotonic()-started,2),'seconds; validating',flush=True)
        assert (case/'triage.input.json').read_bytes()==(case/'expected.input.json').read_bytes()
        value=json.loads(receipt['text'])
        errors=[];decision=None
        try:
            print('BIND',symbol,flush=True)
            binding=bind_response(context,receipt,'triage',policy=policy)
            print('ROUTE',symbol,flush=True)
            projected=model_context(context)
            decision=daily_decision(value,context['guards'],projected)
            if decision in ('retain','update'):
                errors.extend(coverage_issues(value,projected))
            if decision=='update':
                print('FINANCIAL VALIDATION',symbol,flush=True)
                doc=maintenance_document(value,projected,binding=binding)
                valid=validation_result(doc)
                if not valid.ok:errors.extend(valid.errors)
                save(case/'candidate.semantic.json',doc)
                (case/'candidate.md').write_text(render_document(doc),encoding='utf-8')
        except Exception as exc:
            errors.append({'error':str(exc),'details':getattr(exc,'maintenance_details',None)})
        row={'ticker':symbol,'model':receipt['model'],'effort':receipt['reasoning_effort'],
            'decision':decision,'validated':not errors,'errors':errors,'reason':value.get('reason'),
            'risk':value.get('risk'),'usage':receipt['usage'],'seconds':round(time.monotonic()-started,3)}
        rows.append(row);save(case/'validation.json',row);save(folder/'results.json',rows)
        print('DONE',symbol,decision,'VALID' if not errors else 'INVALID',flush=True)
    save(folder/'quota_after.json',read_codex_rate_limits(cwd=ROOT))
    hashes=json.loads((folder/'original_hashes.json').read_text(encoding='utf-8'))
    assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==digest for p,digest in hashes.items())
    save(folder/'originals_unchanged.json',{'verified_files':len(hashes)})
    print('RESULTS',json.dumps(rows,ensure_ascii=True),flush=True)

if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    if sys.argv[1:2]==['--execute']:execute(sys.argv[2])
    else:prepare()
