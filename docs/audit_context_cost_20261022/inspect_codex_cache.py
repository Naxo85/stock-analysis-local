"""Inspect installed CLI metadata/schema only: no model, login or network."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import os

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from src.local_runner.codex_generator import require_codex


def main():
    cli=require_codex()
    def run(args):
        result=subprocess.run([cli,*args],capture_output=True,text=True,encoding='utf-8',
            errors='replace',timeout=60,creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
        return {'exit_code':result.returncode,'stdout':result.stdout,'stderr':result.stderr}
    result={'binary':cli,'version':run(['--version']), 'help':run(['app-server','generate-json-schema','--help'])}
    with tempfile.TemporaryDirectory() as tmp:
        generated=run(['app-server','generate-json-schema','--experimental','--out',tmp])
        result['schema_generation']=generated
        matches=[];files=list(Path(tmp).rglob('*.json'))
        def walk(obj,path,file):
            if isinstance(obj,dict):
                for k,v in obj.items():
                    if any(s in k.lower().replace('_','').replace('-','') for s in ['promptcache','cacheretention','cachettl']):
                        matches.append({'file':file,'path':path+'/'+k,'value':v})
                    walk(v,path+'/'+k,file)
            elif isinstance(obj,list):
                for i,v in enumerate(obj):walk(v,path+'/'+str(i),file)
        for file in files:
            walk(json.loads(file.read_text(encoding='utf-8')),'',str(file.relative_to(tmp)))
        result['schema_file_count']=len(files);result['cache_setting_matches']=matches
    result['limits']='Schema absence does not establish backend TTL, eviction, or undocumented provider behavior.'
    Path(__file__).with_name('codex_cache_capabilities.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k not in ['help']},indent=2))

if __name__=='__main__':main()
