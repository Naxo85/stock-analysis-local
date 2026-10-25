"""Inventory current prompt sources; do not rewrite or shorten any prompt."""
from pathlib import Path
import hashlib, json
ROOT=Path(__file__).resolve().parents[3]
names=['daily_maintenance_semantic_v41.md','stock_analysis_semantic_v14.md',
       'adaptive_revision41.md','volume_arithmetic_v25.md','evidence_direction_v27.md',
       'report_reader_style_v35.md','strength_evidence_v41.md','reader_report_v35.md',
       'catalyst_editorial_v33.md','volume_rubric_v34.md','support_validity_v37.md',
       'option_origins_v39.md','support_origins_v41.md']
files={}
for name in names:
    text=(ROOT/'prompts'/name).read_text(encoding='utf-8')
    files[name]={'chars':len(text),'sha256':hashlib.sha256(text.encode()).hexdigest()}
financial=(ROOT/'prompts/stock_analysis_semantic_v14.md').read_text(encoding='utf-8')
start=financial.index('ESTADO DE TESIS40 (solo full nuevo')
end=financial.index('CONOCIMIENTO41',start)
state=financial[start:end]
old=json.loads((ROOT/'docs/audit_sol_input_cost_20261023/results.json').read_text(encoding='utf-8'))
means={day:run['calculations']['normalized_current_total_visible_chars']/46 for day,run in old['runs'].items()}
out={'prompt_sources':files,'full_state_section_chars':len(state),
    'full_state_section_fraction_visible_pct':{day:len(state)/n*100 for day,n in means.items()},
    'limits':'Whole section is NOT removable: it includes inherited-state meaning and maintenance risk obligations. These percentages are an unsafe upper bound, not a proposed saving.'}
Path(__file__).with_name('instructions.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(out,ensure_ascii=True,indent=2))
