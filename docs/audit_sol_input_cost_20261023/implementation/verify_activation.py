"""Read-only activation evidence for the authorized maintenance schema change."""
from pathlib import Path
import hashlib,json,sys
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
from src.local_runner.adaptive_policy import load_policy
from src.local_runner.maintenance_schema_transport import VERSION

HERE=Path(__file__).resolve().parent
path=ROOT/'config/codex_analysis.json'
text=path.read_text(encoding='utf-8');policy=load_policy(ROOT)
assert policy['maintenance_output_schema']==VERSION
assert (policy['triage_model'],policy['triage_effort'])==('gpt-6.1-sol','medium')
assert (policy['report_model'],policy['report_effort'])==('gpt-6.1-sol','high')
line='  "maintenance_output_schema": "'+VERSION+'",\n'
assert text.count(line)==1
before=text.replace(line,'')
before_sha=hashlib.sha256(before.encode()).hexdigest()
assert before_sha=='2836bde9712e17d3a5ddcbf3cdccc34a034b5719dd42cce616344aebf1a0edd2', 'Other config fields changed'
replay=json.loads((HERE/'replay.json').read_text(encoding='utf-8'))
for file,sha in replay['original_hashes'].items():
    assert hashlib.sha256(Path(file).read_bytes()).hexdigest()==sha,file
instructions=json.loads((HERE.parent/'followup/instructions.json').read_text(encoding='utf-8'))
for name,record in instructions['prompt_sources'].items():
    assert hashlib.sha256((ROOT/'prompts'/name).read_text(encoding='utf-8').encode()).hexdigest()==record['sha256'],name
out={'policy_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
    'previous_policy_sha256':before_sha,'only_config_change':{'maintenance_output_schema':VERSION},
    'triage':['gpt-6.1-sol','medium'],'full':['gpt-6.1-sol','high'],
    'original_files_unchanged':len(replay['original_hashes']),
    'prompt_sources_unchanged':len(instructions['prompt_sources']),
    'model_calls':0,'batches':0,'publications':0,
    'limits':'Local activation and offline equivalence; provider admission/token savings await natural use.'}
(HERE/'activation.json').write_text(json.dumps(out,indent=2),encoding='utf-8')
print(json.dumps(out,indent=2))
