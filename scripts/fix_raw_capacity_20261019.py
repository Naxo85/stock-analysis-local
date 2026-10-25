"""Give source41 a bounded instance ceiling; preserve its exact active image.

No model or financial publication. Staging changes service max1->3 immediately;
the candidate revision also uses max3 so neither scope retains the old bottleneck.
"""
import argparse
from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from scripts.deploy_support_origins_v41 import gc, digest, runtime, traffic, tags, summary
OUT=ROOT/'docs/audit_lrcx_capacity_20261019'
SERVICE='support-resistances-raw';REGION='europe-southwest1'
REVISION=SERVICE+'-capacity41-20261019';TAG='capacity41'
API_URL='https://run.googleapis.com/v2/projects/recipe-generator-429817/locations/'+REGION+'/services/'+SERVICE

def save(name,value): (OUT/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def load(name): return json.loads((OUT/name).read_text(encoding='utf-8'))
def current(): return gc('run','services','describe',SERVICE,'--region='+REGION)
def without_max(value):
    result=deepcopy(runtime(value))
    annotations=result['metadata'].get('annotations',{})
    annotations.pop('autoscaling.knative.dev/maxScale',None)
    # APIv2 materializes these unchanged platform defaults on the v1 readback.
    for key,default in (('autoscaling.knative.dev/minScale','0'),
            ('run.googleapis.com/cpu-throttling','true'),('run.googleapis.com/sessionAffinity','false')):
        if annotations.get(key)==default: annotations.pop(key)
    return result

def api():
    # The installed SDK485 predates --max. Use the documented Admin API with
    # the same pinned existing login, an exact field mask and optimistic etag.
    import requests
    result=subprocess.run(['cmd.exe','/d','/c',shutil.which('gcloud.cmd'),
        'auth','print-access-token','--account=ignacioanefra@gmail.com',
        '--project=recipe-generator-429817'],capture_output=True,text=True,timeout=60)
    if result.returncode:raise RuntimeError('existing_gcloud_token_unavailable')
    headers={'Authorization':'Bearer '+result.stdout.strip()}
    def call(method,url,**kwargs):
        response=requests.request(method,url,headers=headers,timeout=60,**kwargs)
        if response.status_code!=200:
            error=response.json().get('error',{})
            save('service-scaling-api-error.json',{'http_status':response.status_code,'error':error})
            raise RuntimeError('service_scaling_api_http_'+str(response.status_code)+':'+str(error.get('message')))
        return response.json()
    return call

def wait_operation(call,operation):
    deadline=time.monotonic()+150
    while not operation.get('done'):
        if time.monotonic()>=deadline:raise RuntimeError('scaling_operation_pending_check_before_retry')
        time.sleep(2)
        operation=call('GET','https://run.googleapis.com/v2/'+operation['name'])
    if operation.get('error'):raise RuntimeError('service_scaling_operation_failed:'+str(operation['error'].get('code')))

def set_capacity():
    call=api();url=API_URL;before=call('GET',url)
    if before.get('scaling',{}).get('maxInstanceCount')!=1:raise RuntimeError('service_scaling_changed')
    body={'name':before['name'],'etag':before['etag'],'scaling':{'maxInstanceCount':3},
          'template':{'revision':REVISION,'scaling':{'maxInstanceCount':3}}}
    mask='scaling.maxInstanceCount,template.revision,template.scaling.maxInstanceCount'
    call('PATCH',url,params={'updateMask':mask,'validateOnly':'true'},json=body)
    operation=call('PATCH',url,params={'updateMask':mask},json=body)
    save('service-scaling-operation.json',{'name':operation['name'],'previous_max':1,'new_max':3})
    wait_operation(call,operation)
    after=call('GET',url)
    if after.get('scaling',{}).get('maxInstanceCount')!=3:raise RuntimeError('service_scaling_not_applied')
    save('service-scaling.json',{'before':before.get('scaling'),'after':after.get('scaling'),
        'generation':after.get('generation'),'checked_at':datetime.now(timezone.utc).isoformat()})

def update_traffic(activate=False):
    call=api();before=call('GET',API_URL)
    targets=deepcopy(before['traffic'])
    if activate:
        for row in targets:row['percent']=100 if row.get('tag')==TAG else 0
    else:
        if any(row.get('tag')==TAG for row in targets):raise RuntimeError('candidate_tag_already_exists')
        targets.append({'type':'TRAFFIC_TARGET_ALLOCATION_TYPE_REVISION','revision':REVISION,'tag':TAG,'percent':0})
    operation=call('PATCH',API_URL,params={'updateMask':'traffic'},
        json={'name':before['name'],'etag':before['etag'],'traffic':targets})
    wait_operation(call,operation)
def verify_baseline(value):
    baseline=load('raw-before.json')
    if digest(value['spec'])!=baseline['spec_sha256'] or value['metadata']['annotations'].get('run.googleapis.com/maxScale')!='1':
        raise RuntimeError('raw_changed_since_diagnosis')
    return baseline

def stage():
    before=current();baseline=verify_baseline(before)
    save('raw-runtime-baseline.json',{'without_max_sha256':digest(without_max(before))})
    set_capacity()
    update_traffic()
    return finish_stage(before,baseline)

def complete_stage():
    before=current();baseline=load('raw-before.json')
    if (digest(without_max(before))!=load('raw-runtime-baseline.json')['without_max_sha256']
            or before['spec']['template']['metadata']['name']!=REVISION
            or before['metadata']['annotations'].get('run.googleapis.com/maxScale')!='3'
            or traffic(before)!=sorted((r['revisionName'],r['percent'])for r in baseline['traffic']if r.get('percent'))):
        raise RuntimeError('incomplete_stage_does_not_match_expected_capacity_only_change')
    update_traffic()
    return finish_stage(before,baseline)

def finish_stage(before,baseline):
    after=current()
    if (without_max(after)!=without_max(before) or traffic(after)!=traffic(before)
            or after['spec']['template']['spec']['containers'][0]['image']!=baseline['image']
            or after['metadata']['annotations'].get('run.googleapis.com/maxScale')!='3'
            or after['spec']['template']['metadata']['annotations'].get('autoscaling.knative.dev/maxScale')!='3'
            or any(tags(after).get(k)!=v for k,v in tags(before).items())):
        raise RuntimeError('unexpected_capacity_stage_change')
    tag=next(row for row in after['status']['traffic'] if row.get('tag')==TAG)
    if tag['revisionName']!=REVISION: raise RuntimeError('wrong_candidate_revision')
    result={**summary('raw',after),'revision':REVISION,'tag_url':tag['url'],
            'service_max':3,'revision_max':3,'other_runtime_preserved':True,
            'without_max_sha256':digest(without_max(after))}
    save('raw-staged.json',result);return result

def probe():
    import requests
    value=load('raw-staged.json')
    if digest(current()['spec'])!=value['spec_sha256']: raise RuntimeError('stage_changed')
    response=requests.get(value['tag_url'],timeout=40,allow_redirects=False)
    if response.status_code!=400 or 'symbol' not in response.json().get('error',''):
        raise RuntimeError('candidate_missing_symbol_probe_failed')
    result={'revision':REVISION,'http_status':response.status_code,'body':response.json(),
            'provider_and_mirror_not_called':True,'checked_at':datetime.now(timezone.utc).isoformat()}
    save('raw-probe.json',result);return result

def activate():
    before=current();stage=load('raw-staged.json')
    if digest(before['spec'])!=stage['spec_sha256'] or load('raw-probe.json')['revision']!=REVISION:
        raise RuntimeError('unverified_or_changed_stage')
    update_traffic(activate=True)
    after=current()
    if (traffic(after)!=[(REVISION,100)] or without_max(before)!=without_max(after)
            or tags(after)!=tags(before) or after['metadata']['annotations'].get('run.googleapis.com/maxScale')!='3'):
        raise RuntimeError('unexpected_activation_change')
    result={**summary('raw',after),'service_max':3,'revision_max':3,'other_runtime_preserved':True}
    save('raw-active.json',result);return result

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=['stage','complete_stage','probe','activate']);p.add_argument('--execute',action='store_true');a=p.parse_args()
    if a.action!='probe' and not a.execute:p.error('--execute required')
    print(json.dumps(globals()[a.action](),ensure_ascii=False,indent=2))
