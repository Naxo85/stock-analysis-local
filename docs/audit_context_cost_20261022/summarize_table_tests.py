import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]

reading=ROOT/'logs/table_reading_test/20261022T144755704687'
maintenance=ROOT/'logs/table_maintenance_test/20261022T145022489730'
out={}
for name,folder in [('reading',reading),('maintenance',maintenance)]:
 file=folder/'results.json'
 if not file.exists():continue
 rows=json.loads(file.read_text(encoding='utf-8'));groups={}
 for encoding in ['original','tabular']:
  selected=[r for r in rows if r['encoding']==encoding];totals={}
  for r in selected:
   for k,v in r.get('usage',{}).items():totals[k]=totals.get(k,0)+v
  groups[encoding]={'calls':len(selected),'usage':totals,
       'seconds':sum(r.get('seconds',0) for r in selected)}
 out[name]={'folder':str(folder),'results':rows,'groups':groups}
target=Path(__file__).with_name('table_test_summary.json')
target.write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(out,ensure_ascii=True,indent=2))
