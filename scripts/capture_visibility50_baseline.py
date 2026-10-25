"""Read the two presentation modules from the immutable live image."""
import json
from pathlib import Path
import shutil
import subprocess
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts.deploy_support_origins_v41 import gc
OUT=ROOT/'docs/audit_visibility50_20261022'
WORK=ROOT/'.tmp/visibility50_baseline'
if sys.argv[1]=='start':
    WORK.mkdir(parents=True,exist_ok=True)
    image=json.loads((OUT/'controller_before.json').read_text())['image']
    script='''import json
from pathlib import Path
from stock_analysis.controller import analysis_sheet
from stock_analysis.analysis_worker import run_sync
for module in [analysis_sheet,run_sync]:
 print('SOURCE_RECORD:'+json.dumps({'module':module.__name__,'source':Path(module.__file__).read_text()}))
'''
    (WORK/'read.py').write_text(script,encoding='utf-8')
    config={'steps':[{'name':'gcr.io/cloud-builders/docker','args':['run','--rm','-v','/workspace:/diag',image,'python','/diag/read.py']}]}
    (WORK/'cloudbuild.json').write_text(json.dumps(config),encoding='utf-8')
    result=gc('builds','submit',str(WORK),'--config='+str(WORK/'cloudbuild.json'),'--async')
    (OUT/'baseline_build.json').write_text(json.dumps(result),encoding='utf-8')
    print(result['id'])
else:
    build=json.loads((OUT/'baseline_build.json').read_text())
    status=gc('builds','describe',build['id'])['status']
    if status!='SUCCESS':print(status);sys.exit(0)
    run=subprocess.run(['cmd.exe','/d','/c',shutil.which('gcloud.cmd'),'builds','log',build['id'],
        '--account=ignacioanefra@gmail.com','--project=recipe-generator-429817','--quiet'],capture_output=True,text=True,encoding='utf-8',timeout=120,check=True)
    for line in run.stdout.splitlines():
        if 'SOURCE_RECORD:' in line:
            data=json.loads(line.split('SOURCE_RECORD:',1)[1])
            (OUT/(data['module']+'.py')).write_text(data['source'],encoding='utf-8')
            print(data['module'])
