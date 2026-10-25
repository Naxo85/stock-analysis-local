"""Authenticate archived calls and replay routing classifiers, never model calls."""
import hashlib
import json
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from src.local_runner.adaptive_context import unpack_model_context
from src.local_runner.semantic_sources import raise_issues, source_selection_only
from src.local_runner.review_contract import review_contract_only
from src.local_runner.maintenance_change import change_justification_only
from src.local_runner.volume_arithmetic import arithmetic_only

BATCH = ROOT / 'logs/batch/2026-10-23/14-18-22/adaptive'
CLASSIFIERS = {'arithmetic_only': arithmetic_only, 'review_contract_only': review_contract_only,
    'change_justification_only': change_justification_only, 'source_selection_only': source_selection_only}

def classify(issues):
    try:
        raise_issues(issues)
    except ValueError as exc:
        return {name: bool(fn(exc)) for name, fn in CLASSIFIERS.items()}
    raise AssertionError('Expected rejected issues')

results, hashes = {}, {}
for symbol in ('AMD', 'AMAT', 'SNDK', 'ASTS'):
    work = BATCH / symbol
    files = ['input.json', 'policy.json', 'update_rejected.json']
    files += [kind+suffix for kind in ('triage','triage_repair','report')
              for suffix in ('.input.json','.receipt.json','.response')]
    for name in files:
        path = work/name
        hashes[str(path)] = hashlib.sha256(path.read_bytes()).hexdigest()
    calls = {}
    for kind in ('triage','triage_repair','report'):
        receipt = json.loads((work/(kind+'.receipt.json')).read_text(encoding='utf-8'))
        assert hashes[str(work/(kind+'.input.json'))] == receipt['input_sha256']
        assert hashes[str(work/(kind+'.response'))] == receipt['response_sha256']
        calls[kind] = {'model': receipt['model'], 'effort':receipt['reasoning_effort'],
            'input_receipt_verified':True, 'response_receipt_verified':True}
        if kind != 'report':
            payload = json.loads((work/(kind+'.response')).read_text(encoding='utf-8'))
            calls[kind].update({key:payload[key] for key in ('decision','risk','uncertainty','evidence_gap')})
            calls[kind]['critical_news_groups'] = [g for g in payload.get('news_review',[]) if g.get('outcome')=='critical_change']
    frozen = unpack_model_context(json.loads((work/'report.input.json').read_text(encoding='utf-8')))
    handoff = frozen['maintenance_handoff']
    attempts = []
    for attempt in handoff['attempts']:
        issues = attempt['validation_details']['issues']
        aggregate = classify(issues)
        individuals = [{'issue':issue,'classifiers':classify([issue])} for issue in issues]
        assert all(any(row['classifiers'].values()) for row in individuals)
        if attempt['attempt'] == 2:
            assert not any(aggregate.values())
        attempts.append({'attempt':attempt['attempt'], 'recorded_reason':attempt['reason'],
            'issues':issues,'aggregate_classifiers':aggregate,'individual_classifiers':individuals})
    assert frozen['guards'] == []
    assert frozen['itv']['due'] is False
    assert all(calls[k]['decision']=='update' and not any(calls[k]['risk'].values())
               and calls[k]['uncertainty'] is False and calls[k]['evidence_gap']=='none'
               and not calls[k]['critical_news_groups'] for k in ('triage','triage_repair'))
    rejection = json.loads((work/'update_rejected.json').read_text(encoding='utf-8'))
    assert rejection['next']=='sol_review'
    assert rejection['reason']==attempts[-1]['recorded_reason']
    results[symbol] = {'calls':calls,'guards':frozen['guards'],'itv':frozen['itv'],
        'attempts':attempts,'next':rejection['next']}
assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==digest for p,digest in hashes.items())
output = {'scope':'archived_receipts_and_error_routing_classifiers_only',
    'original_files_unchanged':len(hashes),'sha256':hashes,'tickers':results}
Path(__file__).with_name('escalations_20261023.json').write_text(json.dumps(output,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'tickers':list(results),'authenticated_calls':12,'original_files_unchanged':len(hashes),
    'second_attempt_issue_counts':{s:len(r['attempts'][1]['issues']) for s,r in results.items()},
    'all_individual_issues_block_sol_but_mixed_set_does_not':True},ensure_ascii=True))
