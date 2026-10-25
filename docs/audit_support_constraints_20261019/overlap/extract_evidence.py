"""Read frozen originals only; write this audit's compact evidence, never runtime data."""
import hashlib
import json
from pathlib import Path
import sys

sys.stdout.reconfigure(encoding='utf-8')
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
BASE = ROOT / 'logs/batch/2026-10-18/09-08-40/adaptive'

def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))

def source_brief(source):
    value = source.get('value', {})
    if not isinstance(value, dict):
        return None
    evidence = value.get('evidence')
    if not isinstance(evidence, dict):
        return None
    return {
        'pointer': source.get('pointer'),
        'level': value.get('level'), 'type': value.get('type'), 'date': value.get('date'),
        'evidence': {
            key: {k:v for k,v in child.items() if k not in ('path_evidence','measurement_basis')}
            for key,child in evidence.items() if isinstance(child,dict)
        }
    }

rows, same_range_changes, manifest = [], [], []
for path in sorted(BASE.glob('*/publish/output/*/latest.json')):
    report = read(path)
    ticker = report['symbol']
    inp_path = BASE / ticker / 'input.json'
    inp = read(inp_path)
    plan, old = report['plan'], inp['reference']['plan']
    sem = report['semantic_report']['data']['plan']
    for source_path in [path,inp_path]:
        manifest.append({'path':source_path.relative_to(ROOT).as_posix(),
                         'sha256':hashlib.sha256(source_path.read_bytes()).hexdigest()})
    for role,prefix in [('entry','entry'),('ambitious_entry','washout')]:
        if plan.get(role) is None:
            continue
        lv = sem[role]
        b = plan[prefix+'_strength_breakdown']
        row = {'ticker':ticker,'role':role,'report_path':path.relative_to(ROOT).as_posix(),
               'report_generated_at':report['generated_at'], 'range':plan[role],
               'score':plan[prefix+'_strength_score'],'components':b,
               'factors':plan[prefix+'_strength_factors'],
               'volume_calculation_audit':lv.get('volume_calculation_audit'),
               'scoring_evidence_pointers':lv.get('evidence',[])}
        rows.append(row)
        if plan[role]==old.get(role) and b!=old.get(prefix+'_strength_breakdown',{}):
            same_range_changes.append({'ticker':ticker,'role':role,'range':plan[role],
                                       'before':old.get(prefix+'_strength_breakdown',{}),'after':b})

audits=[x for x in rows if x['volume_calculation_audit']]
binding=[x for x in audits if sum(x['volume_calculation_audit']['parts'].values())>x['volume_calculation_audit']['expected']]
result={'scope':'18Oct committed local reports, frozen references; no current quote downloads or recomputation of finance',
        'reports':len(manifest)//2,'zones':len(rows),'zero_volume_count':sum(x['components']['volumen']==0 for x in rows),
        'retained_or_current_volume_audit_count':len(audits),'binding_volume_ceiling_count':len(binding),
        'same_range_component_changes_against_frozen_CURRENT':same_range_changes,'rows':rows,'original_manifest':manifest}
(HERE/'evidence.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({k:v for k,v in result.items() if k not in ['rows','original_manifest']},ensure_ascii=False,indent=2))
