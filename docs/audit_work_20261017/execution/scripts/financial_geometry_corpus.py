import json
from pathlib import Path
from src.local_runner.semantic_report import _validate_geometry
root=Path.cwd()
sets=[('full36_14oct',root/'logs/batch/2026-10-14/16-07-07/adaptive','*/report.response'),('published38_16oct',root/'logs/batch/2026-10-16/15-58-24/adaptive','*/publish/output/*/latest.json')]
result=[]
for label,folder,pattern in sets:
 rows=[]
 for path in sorted(folder.glob(pattern)):
  record=json.loads(path.read_text(encoding='utf8'))
  plan=record['plan'] if path.name=='report.response' else record['semantic_report']['data']['plan']
  try:_validate_geometry(plan,{'routing_revision':40});outcome='accepted'
  except ValueError as exc:outcome=str(exc)
  rows.append({'symbol':path.parent.name,'outcome':outcome,'active_zones':sum(plan[k]['range'] is not None for k in ('entry','ambitious_entry'))})
 result.append({'set':label,'reports':len(rows),'rejected':sum(r['outcome']!='accepted' for r in rows),'rows':rows})
(root/'.tmp/audit_execution_20261017/financial_geometry_corpus.json').write_text(json.dumps(result,indent=2))
print(json.dumps([{k:v for k,v in r.items() if k!='rows'} for r in result]))
