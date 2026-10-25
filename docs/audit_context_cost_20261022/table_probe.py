import json
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from src.local_runner.adaptive_context import unpack_model_context
p=ROOT/'logs/batch/2026-10-21/06-52-46/adaptive/LEU/triage.input.json'
d=unpack_model_context(json.loads(p.read_text(encoding='utf-8')))
def visit(v,path,depth=0):
    if isinstance(v,dict):
        for k,x in v.items():visit(x,path+'/'+k,depth+1)
    if isinstance(v,list) and len(v)>=3 and all(isinstance(x,dict) for x in v):
        print(path,len(v),list(v[0])[:15],str(v[0])[:450])
visit(d['slim'],'/slim')
