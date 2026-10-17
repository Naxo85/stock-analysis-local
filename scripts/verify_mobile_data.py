"""Read-only verification using existing local authority; no deployment or grants."""
import json
from pathlib import Path
import shutil
import subprocess
import sys
from urllib.parse import quote
from urllib.request import Request,urlopen
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import AuthorizedSession
from google.cloud import storage
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'gcp_services/mobile_api'))
from sources import PublishedSources


def main():
    token=subprocess.run([shutil.which('gcloud.cmd'),'auth','print-access-token'],capture_output=True,text=True,check=True).stdout.strip()
    reader='stock-analysis-sheets@recipe-generator-429817.iam.gserviceaccount.com'
    request=Request(f'https://iamcredentials.googleapis.com/v1/projects/-/serviceAccounts/{quote(reader,safe="")}:generateAccessToken',data=json.dumps({'scope':['https://www.googleapis.com/auth/spreadsheets.readonly'],'lifetime':'600s'}).encode(),headers={'Authorization':f'Bearer {token}','Content-Type':'application/json'})
    with urlopen(request,timeout=30) as response: sheet_token=json.load(response)['accessToken']
    repository=PublishedSources(storage_client=storage.Client(project='recipe-generator-429817',credentials=Credentials(token)),sheets_session=AuthorizedSession(Credentials(sheet_token)))
    data=repository.snapshot()
    destination=ROOT/'.local/mobile';destination.mkdir(exist_ok=True)
    (destination/'dashboard-verified.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
    (destination/'report-verified.json').write_text(json.dumps(repository.report('RKLB'),ensure_ascii=False,indent=2),encoding='utf-8')
    offline=destination/'offline';offline.mkdir(exist_ok=True)
    (offline/'dashboard.json').write_text(json.dumps(data,ensure_ascii=False),encoding='utf-8')
    reports_dir=offline/'reports';reports_dir.mkdir(exist_ok=True)
    for stale in reports_dir.glob('*.json'):
        if stale.stem not in repository.reports:
            if stale.resolve().parent != reports_dir.resolve():
                raise RuntimeError('Unexpected snapshot path')
            stale.unlink()
    for symbol,report in repository.reports.items():
        (reports_dir/f'{symbol}.json').write_text(json.dumps(report,ensure_ascii=False),encoding='utf-8')
    assert len({s['symbol'] for s in data['stocks']})==len(data['stocks'])
    assert data['market']['qqq_day'] is not None
    assert len(data['market']['groups'])==14
    assert all(s['price'] is None or s['price']>0 for s in data['stocks'])
    print(json.dumps({'stocks':len(data['stocks']),'changes':len(data['changes']),'news':len(data['news']),'groups':len(data['market']['groups']),'reports':sum(s['analysis_status']=='ok' for s in data['stocks']),'warnings':data['warnings'],'news_sample':data['news'][:1]},ensure_ascii=True))


if __name__=='__main__':main()
