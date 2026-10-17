"""Guarded, narrow rollout for model-assessed support colors; no analysis calls."""
from copy import deepcopy
import json
import os
from pathlib import Path
import subprocess
import sys
from urllib.parse import quote
from urllib.request import Request,urlopen

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'logs/support_validity36'
PROJECT='recipe-generator-429817'
REGION='europe-southwest1'
SERVICE='stock-controller'
REVISION='stock-controller-support-validity36-20261014'
TAG='supportvaliditytest'
BUILD='102052ff-8de3-4eae-b340-0dcf56c5271d'
os.environ['CLOUDSDK_CONFIG']=r'C:\Users\ignac\AppData\Roaming\gcloud'
os.environ['CLOUDSDK_CORE_DISABLE_FILE_LOGGING']='true'

def save(name,data):
 OUT.mkdir(parents=True,exist_ok=True)
 (OUT/name).write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
def gc(*args):
 p=subprocess.run(['cmd.exe','/c','gcloud.cmd',*args,'--project='+PROJECT,'--format=json'],capture_output=True,text=True,encoding='utf-8',check=True,timeout=90)
 return json.loads(p.stdout)
def describe():return gc('run','services','describe',SERVICE,'--region='+REGION)
def token(kind):
 return subprocess.run(['cmd.exe','/c','gcloud.cmd','auth','print-'+kind+'-token'],capture_output=True,text=True,check=True,timeout=30).stdout.strip()
def request(url,bearer,data=None,method=None):
 headers={'Authorization':'Bearer '+bearer}
 if data is not None:headers['Content-Type']='application/json'
 with urlopen(Request(url,headers=headers,data=data,method=method),timeout=120) as response:return json.load(response)
def runtime(service):
 spec=deepcopy(service['spec']['template']['spec'])
 for c in spec['containers']:c.pop('image',None)
 return spec

def stage():
 build=gc('builds','describe',BUILD);save('build-final.json',build)
 assert build['status']=='SUCCESS','build did not pass'
 image=build['results']['images'][0]['name'].split(':')[0]+'@'+build['results']['images'][0]['digest']
 before=describe();save('service-before.json',before)
 assert any(t.get('revisionName')=='stock-controller-support-only-20261013' and t.get('percent')==100 for t in before['status']['traffic']),'Active service changed; rebase required'
 result=gc('run','deploy',SERVICE,'--image='+image,'--region='+REGION,'--revision-suffix=support-validity36-20261014','--no-traffic','--tag='+TAG,'--async')
 save('stage-result.json',result);print('Staged private revision at zero production traffic.')
def health():
 current=describe();save('service-staged.json',current)
 rev=gc('run','revisions','describe',REVISION,'--region='+REGION);save('revision-staged.json',rev)
 assert all(any(c['type']==name and c['status']=='True' for c in rev['status']['conditions']) for name in ('Ready','ContainerHealthy')),'Revision not healthy yet'
 url=next(t['url'] for t in current['status']['traffic'] if t.get('tag')==TAG)
 result=request(url+'/health',token('identity'));save('health-staged.json',result)
 assert runtime(current)==runtime(json.loads((OUT/'service-before.json').read_text(encoding='utf-8'))),'Runtime configuration changed'
 print(json.dumps(result))
def activate():
 before=json.loads((OUT/'service-before.json').read_text(encoding='utf-8'))
 staged=json.loads((OUT/'service-staged.json').read_text(encoding='utf-8'))
 assert (OUT/'health-staged.json').exists(),'Authenticated health check required'
 current=describe();assert current['spec']==staged['spec'],'Service changed after staging'
 gc('run','services','update-traffic',SERVICE,'--region='+REGION,'--to-revisions='+REVISION+'=100')
 gc('run','services','update-traffic',SERVICE,'--region='+REGION,'--remove-tags='+TAG)
 active=describe();save('service-active.json',active)
 assert runtime(active)==runtime(before)
 assert any(t.get('revisionName')==REVISION and t.get('percent')==100 for t in active['status']['traffic'])
 old_tags={t['tag']:t['revisionName'] for t in before['status']['traffic'] if t.get('tag')}
 new_tags={t['tag']:t['revisionName'] for t in active['status']['traffic'] if t.get('tag')}
 assert new_tags==old_tags
 print('Verified active 100%; original runtime, secrets and existing tags preserved.')
def layout():
 bearer=token('access');bucket='stock-analysis-system-naxo85';name='runtime/config/market_sheet_layout.json'
 url='https://storage.googleapis.com/storage/v1/b/'+bucket+'/o/'+quote(name,safe='')
 meta=request(url,bearer);before=request(url+'?alt=media&generation='+meta['generation'],bearer)
 save('layout-before.json',before);save('layout-metadata-before.json',meta)
 after=deepcopy(before)
 inside=next(rule for rule in before['format_rules']['entry_proximity'] if rule['state']=='inside_range')
 after['format_rules']['entry_proximity']=[inside]
 uploaded=request('https://storage.googleapis.com/upload/storage/v1/b/'+bucket+'/o?uploadType=media&name='+quote(name,safe='')+'&ifGenerationMatch='+meta['generation'],bearer,json.dumps(after,ensure_ascii=False).encode('utf-8'),'POST')
 actual=request(url+'?alt=media&generation='+uploaded['generation'],bearer)
 assert actual==after;save('layout-after.json',actual);save('layout-metadata-after.json',uploaded)
 print('Only entry_proximity changed: phosphorescent or normal; no lower percent rule.')
def refresh():
 active=describe();assert any(t.get('revisionName')==REVISION and t.get('percent')==100 for t in active['status']['traffic'])
 result=request(active['status']['url']+'/analysis/refresh',token('identity'),b'','POST')
 save('refresh-result.json',result);print(json.dumps(result))

if __name__=='__main__':globals()[sys.argv[1]]()
