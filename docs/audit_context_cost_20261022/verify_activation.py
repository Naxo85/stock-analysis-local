"""Read back active policy and replay transport on46 frozen model views."""
from copy import deepcopy
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from src.local_runner.adaptive_context import serialize_model_input, unpack_model_context
from src.local_runner.adaptive_policy import load_policy
from src.local_runner.diff_transport import FIELD,VERSION,INSTRUCTIONS

policy=load_policy(ROOT)
assert policy['maintenance_context_transport']==VERSION
assert (policy['triage_model'],policy['triage_effort'])==('gpt-6-luna','high')
assert (policy['report_model'],policy['report_effort'])==('gpt-6.1-sol','high')
assert policy['priority_itv_sessions']==policy['watchlist_itv_sessions']==5
files=sorted((ROOT/'logs/batch/2026-10-21/06-52-46/adaptive').glob('*/triage.input.json'))
assert len(files)==46
old_chars=new_chars=0
for file in files:
    raw=file.read_bytes()
    frozen_policy=json.loads(file.with_name('policy.json').read_text(encoding='utf-8'))
    assert 'maintenance_context_transport' not in frozen_policy
    original=unpack_model_context(json.loads(raw))
    original_wire=serialize_model_input(original)
    compact=deepcopy(original);compact[FIELD]=VERSION
    text=serialize_model_input(compact)
    assert unpack_model_context(json.loads(text))==compact
    assert serialize_model_input(original)==original_wire
    assert file.read_bytes()==raw
    old_chars+=len(original_wire);new_chars+=len(text)
result={'cases':len(files),'policy':{k:policy[k] for k in ['routing_revision','triage_model','triage_effort',
    'maintenance_context_transport','report_model','report_effort','priority_itv_sessions','watchlist_itv_sessions']},
    'legacy_reserialized_characters':old_chars,'compact_characters':new_chars,
    'input_character_reduction_pct':100*(1-new_chars/old_chars),
    'additional_instruction_characters_per_call':len(INSTRUCTIONS)+2,
    'character_reduction_after_instruction_overhead_pct':100*(1-(new_chars+len(files)*(len(INSTRUCTIONS)+2))/old_chars),
    'note':'Character counts, not measured tokens or quota. No model/publication performed.'}
Path(__file__).with_name('activation.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps(result,indent=2))
