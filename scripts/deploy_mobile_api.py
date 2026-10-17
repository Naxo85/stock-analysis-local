"""Provision only the read-only mobile API. Never refreshes Sheets or analyses."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import secrets
import shutil
import subprocess
import time
from urllib.parse import quote
from urllib.request import Request, urlopen
from urllib.error import HTTPError

ROOT=Path(__file__).resolve().parents[1]
PROJECT='recipe-generator-429817'
REGION='europe-southwest1'
SERVICE='stock-mobile-api'
ACCOUNT=f'stock-mobile-reader@{PROJECT}.iam.gserviceaccount.com'
GCLOUD=shutil.which('gcloud.cmd') or 'gcloud'


def gc(*args, check=True):
    result=subprocess.run([GCLOUD,*args,'--quiet'],capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=1200)
    if check and result.returncode:
        raise RuntimeError(result.stderr)
    return result


def api(url,token,data=None):
    req=Request(url,headers={'Authorization':f'Bearer {token}','Content-Type':'application/json'},data=json.dumps(data).encode() if data is not None else None)
    try:
        with urlopen(req,timeout=120) as response:
            return json.load(response)
    except HTTPError as error:
        detail=error.read().decode('utf-8',errors='replace')
        raise RuntimeError(f'Google API {error.code}: {detail}') from None


def main():
    destination=ROOT/'.local/mobile'; destination.mkdir(parents=True,exist_ok=True)
    code_file=destination/'access-code.txt'
    if not code_file.exists(): code_file.write_text(secrets.token_urlsafe(24),encoding='utf-8')
    code=code_file.read_text().strip()
    if gc('iam','service-accounts','describe',ACCOUNT,f'--project={PROJECT}',check=False).returncode:
        gc('iam','service-accounts','create','stock-mobile-reader',f'--project={PROJECT}','--display-name=Growth mobile reader')
    for bucket in ['stock-analysis-system-naxo85','stock-analysis-reports-naxo85']:
        gc('storage','buckets','add-iam-policy-binding',f'gs://{bucket}',f'--member=serviceAccount:{ACCOUNT}','--role=roles/storage.objectViewer')
    print('Read-only GCS access configured',flush=True)
    gc('services','enable','drive.googleapis.com',f'--project={PROJECT}')
    layout=json.loads(gc('storage','cat','gs://stock-analysis-system-naxo85/runtime/config/market_sheet_layout.json').stdout)
    user_token=gc('auth','print-access-token').stdout.strip()
    writer=layout['spreadsheet']['service_account']
    scoped=api(f'https://iamcredentials.googleapis.com/v1/projects/-/serviceAccounts/{quote(writer,safe="")}:generateAccessToken',user_token,{'scope':['https://www.googleapis.com/auth/drive'],'lifetime':'600s'})['accessToken']
    file_id=layout['spreadsheet']['spreadsheet_id']
    permissions=api(f'https://www.googleapis.com/drive/v3/files/{file_id}/permissions?fields=permissions(id,emailAddress,role)',scoped)['permissions']
    if not any(p.get('emailAddress')==ACCOUNT for p in permissions):
        api(f'https://www.googleapis.com/drive/v3/files/{file_id}/permissions?sendNotificationEmail=false',scoped,{'type':'user','role':'reader','emailAddress':ACCOUNT})
    print('Mercado reader permission configured',flush=True)
    digest=hashlib.sha256(code.encode()).hexdigest()
    print('Deploying authenticated mobile API',flush=True)
    result=gc('run','deploy',SERVICE,f'--project={PROJECT}',f'--region={REGION}',f'--source={ROOT / "gcp_services/mobile_api"}',f'--service-account={ACCOUNT}','--allow-unauthenticated','--ingress=all','--memory=512Mi','--cpu=1','--min-instances=0','--max-instances=2','--concurrency=8','--timeout=120',f'--set-env-vars=ACCESS_TOKEN_SHA256={digest},SYSTEM_BUCKET=stock-analysis-system-naxo85,REPORT_BUCKET=stock-analysis-reports-naxo85')
    (destination/'deploy.log').write_text(result.stdout+result.stderr,encoding='utf-8')
    url=gc('run','services','describe',SERVICE,f'--project={PROJECT}',f'--region={REGION}','--format=value(status.url)').stdout.strip()
    (destination/'deployment.json').write_text(json.dumps({'url':url,'service':SERVICE,'region':REGION},indent=2),encoding='utf-8')
    for attempt in range(6):
        try:
            snapshot=api(url+'/v1/dashboard',code)
            break
        except RuntimeError as error:
            if attempt == 5 or not any(marker in str(error) for marker in ['API 401:', 'API 403:', 'API 503:']):
                raise
            print('Waiting for new service permissions to propagate',flush=True)
            time.sleep(10)
    (destination/'dashboard.json').write_text(json.dumps(snapshot,ensure_ascii=False),encoding='utf-8')
    print(json.dumps({'url':url,'stocks':len(snapshot['stocks']),'changes':len(snapshot['changes']),'news':len(snapshot['news']),'warnings':snapshot['warnings']},ensure_ascii=True))
    print('Activation code saved locally; not embedded in the APK:',code_file)


if __name__=='__main__': main()
