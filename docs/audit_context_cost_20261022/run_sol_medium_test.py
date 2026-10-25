"""Authorized three-call medium comparator, reusing exact low fixture bytes."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
from run_sol_low_test import ROOT, save, execute

LOW=ROOT/'logs/sol_low_test/20261023T160954879936'

def prepare():
    folder=ROOT/'logs/sol_medium_test'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%f')
    folder.mkdir(parents=True,exist_ok=False)
    hashes=json.loads((LOW/'original_hashes.json').read_text(encoding='utf-8'))
    # Account for independent authorized daily configuration work, if any.
    config=ROOT/'config/codex_analysis.json'
    hashes[str(config)]=hashlib.sha256(config.read_bytes()).hexdigest()
    comparisons={}
    for symbol in ('AMD','CLS','IREN'):
        before=LOW/symbol
        case=folder/symbol
        case.mkdir()
        comparisons[symbol]={}
        for name in ('frozen_context.json','view.json','schema.json','expected.input.json'):
            data=(before/name).read_bytes()
            (case/name).write_bytes(data)
            digest=hashlib.sha256(data).hexdigest()
            comparisons[symbol][name]=digest
            assert hashlib.sha256((case/name).read_bytes()).hexdigest()==digest
        for name in ('frozen_context.json','view.json','schema.json','expected.input.json',
                     'instructions.md','policy.json','triage.input.json','triage.response','triage.receipt.json'):
            path=before/name
            hashes[str(path)]=hashlib.sha256(path.read_bytes()).hexdigest()
        policy=json.loads((before/'policy.json').read_text(encoding='utf-8'))
        assert policy['triage_model']=='gpt-6.1-sol' and policy['triage_effort']=='low'
        policy['triage_effort']='medium'
        save(case/'policy.json',policy)
        instructions=(before/'instructions.md').read_text(encoding='utf-8')
        target='EVALUATION ONLY: gpt-6.1-sol with low reasoning.'
        assert instructions.count(target)==1
        instructions=instructions.replace(target,'EVALUATION ONLY: gpt-6.1-sol with medium reasoning.')
        (case/'instructions.md').write_text(instructions,encoding='utf-8')
    save(folder/'original_hashes.json',hashes)
    save(folder/'identical_fixtures.json',comparisons)
    save(folder/'plan.json',{'model':'gpt-6.1-sol','effort':'medium','tickers':['AMD','CLS','IREN'],
        'maximum_model_calls':3,'research':False,'repairs':False,'full':False,'publication':False,
        'baseline':str(LOW),'controlled_changes':['reasoning_effort low to medium','matching evaluation footer effort label'],
        'scope':'Historical same-input maintenance comparator, never recovery/current publication.'})
    print('PREPARED',folder,flush=True)

if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    if sys.argv[1:2]==['--execute']:execute(sys.argv[2])
    else:prepare()
