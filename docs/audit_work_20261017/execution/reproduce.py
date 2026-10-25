"""Reproduce archived-data studies offline, keeping recorded results immutable."""
import hashlib,json,shutil,socket,subprocess,sys,os,contextlib,argparse
from pathlib import Path
from unittest.mock import patch
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2];OUT=ROOT/'.tmp/audit40_reproduction'
if not(ROOT/'src/local_runner').is_dir():raise SystemExit('repository_root_not_found')
OUT.mkdir(parents=True,exist_ok=True);os.chdir(ROOT);sys.path.insert(0,str(ROOT))
manifest=json.loads((HERE/'manifest.json').read_text(encoding='utf8'))
for rel,meta in manifest['files'].items():
 if hashlib.sha256((HERE/rel).read_bytes()).hexdigest()!=meta['sha256']:raise ValueError('recorded_evidence_changed:'+rel)
for name in ['source_baseline.json','original_input_hashes.json','m02_distance_control_design.json']:
 shutil.copyfile(HERE/'results'/name,OUT/name)
base=OUT/'baseline/src/local_runner';base.mkdir(parents=True,exist_ok=True)
for name in ['semantic_report.py','adaptive_repair.py','adaptive_policy.py']:shutil.copyfile(HERE/'baseline_contracts'/name,base/name)
original=json.loads((OUT/'original_input_hashes.json').read_text(encoding='utf8'))
missing=[p for p in original if not(ROOT/p).is_file()]
if missing:raise SystemExit('Local original corpus required; no downloading. Missing files:'+str(len(missing)))
changed=[p for p,d in original.items() if hashlib.sha256((ROOT/p).read_bytes()).hexdigest()!=d]
if changed:raise SystemExit('Original artifact hash mismatch:'+repr(changed[:3]))
def denied(*args,**kwargs):raise RuntimeError('OFFLINE_STUDY_EXTERNAL_ACCESS_FORBIDDEN')
scripts=['evaluate_local','comparison_extensions','data_volume_original_replay','data_m01_replay','financial_geometry_corpus','check_financial_frozen','check_calendar','path_context_budget','option_persistence_c01','methodology_adversarial_check']
if(HERE/'scripts/m02_distance_control.py').is_file():scripts.append('m02_distance_control')
parser=argparse.ArgumentParser();parser.add_argument('--only',choices=scripts);args=parser.parse_args()
if args.only:scripts=[args.only]
completed=[]
with patch.object(socket.socket,'connect',denied),patch.object(socket.socket,'connect_ex',denied),patch.object(subprocess,'Popen',denied):
 for name in scripts:
  p=HERE/'scripts'/(name+'.py');source=p.read_text(encoding='utf8')
  # Only portability/output substitutions; no calculation or sample-rule changes.
  source=source.replace('E:/stock-analysis-local',ROOT.as_posix()).replace('.tmp/audit_execution_20261017','.tmp/audit40_reproduction')
  print('RUN',name,flush=True)
  with (OUT/(name+'.log')).open('w',encoding='utf8') as log,contextlib.redirect_stdout(log):
   exec(compile(source,str(p),'exec'),{'__name__':'__main__','__file__':str(p)})
  completed.append(name)
recorded=[];different=[]
for p in sorted(OUT.glob('*.json')):
 prior=HERE/'results'/p.name
 if prior.is_file():
  same=json.loads(p.read_text(encoding='utf8'))==json.loads(prior.read_text(encoding='utf8'))
  (recorded if same else different).append(p.name)
result={'status':'finished','scripts':completed,'verified_originals':len(original),'equal_recorded_json':recorded,'different_recorded_json':different,'interpretation':'Differences require inspection; never overwrite recorded evidence or treat a match as predictive validation.'}
(OUT/'reproduction_result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8');print(json.dumps(result,ensure_ascii=False,indent=2))
