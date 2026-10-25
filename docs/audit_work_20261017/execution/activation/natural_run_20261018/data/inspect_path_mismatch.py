import json, pathlib, sys
r=pathlib.Path.cwd(); sys.path.insert(0,str(r))
from gcp_functions.support_resistances_raw.price_path import horizontal_path_evidence
s=json.loads((r/'logs/batch/2026-10-18/09-08-40/adaptive/AMAT/input.json').read_text())['slim']
a=json.loads(next((r/'data/technical_archive/AMAT').glob('*.json')).read_text())
p=s['levels']['observed_origins'][1]['evidence']['historical_reaction']['path_evidence']
q=horizontal_path_evidence(p['coordinate'],a['daily']['rows'],p['tolerance_abs'])
print(json.dumps({'expected':p['events'],'actual':q['events']},indent=2))
