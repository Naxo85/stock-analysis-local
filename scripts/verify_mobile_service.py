"""Check the deployed read-only mobile service without printing its access code."""
from datetime import datetime, timezone
from collections import Counter
import json
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError

ROOT = Path(__file__).resolve().parents[1]
PERSONAL = ROOT / '.local/mobile'


def main():
    url = json.loads((PERSONAL / 'deployment.json').read_text())['url']
    code = (PERSONAL / 'access-code.txt').read_text().strip()

    def request(path, token=None, method='GET'):
        headers = {'Authorization': f'Bearer {token}'} if token else {}
        try:
            with urlopen(Request(url + path, headers=headers, method=method), timeout=120) as response:
                return response.status, {k.lower():v for k,v in response.headers.items()}, json.load(response)
        except HTTPError as error:
            return error.code, dict(error.headers), error.read().decode('utf-8', errors='replace')

    assert request('/v1/dashboard')[0] == 401
    assert request('/v1/dashboard', 'invalid-private-code-xxxxxxxxxxxx')[0] == 401
    assert request('/v1/reports/RKLB')[0] == 401
    assert request('/v1/dashboard', code, 'POST')[0] == 405
    status, headers, dashboard = request('/v1/dashboard', code)
    assert status == 200, f'Dashboard returned {status}'
    assert headers.get('cache-control') == 'no-store', headers
    assert dashboard['schema_version'] == 1 and not dashboard['stale']
    assert not dashboard['warnings'], dashboard['warnings']
    assert len(dashboard['stocks']) >= 40
    assert len({s['symbol'] for s in dashboard['stocks']}) == len(dashboard['stocks'])
    market=dashboard['market']
    assert market['session'] in {'regular','pre-market','post-market','closed'},market
    assert isinstance(market['refresh_interval_minutes'],int) and 1 <= market['refresh_interval_minutes'] <= 60,market
    assert 15 <= market['poll_after_seconds'] <= market['refresh_interval_minutes']*60,market
    allowed_kinds={'catalyst','event','score','analyst'}
    assert all(item.get('kind') in allowed_kinds and item.get('change_type') for item in dashboard['changes'])
    status, _, report = request('/v1/reports/RKLB', code)
    assert status == 200 and report['symbol'] == 'RKLB' and report['analysis_status'] == 'ok'
    assert len(report['analysis_markdown']) > 1000
    assert request('/v1/reports/UNKNOWN123', code)[0] == 404
    result = {
        'verified_at': datetime.now(timezone.utc).isoformat(), 'url': url,
        'stocks': len(dashboard['stocks']), 'groups': len(dashboard['market']['groups']),
        'changes': len(dashboard['changes']), 'change_kinds':dict(Counter(item['kind'] for item in dashboard['changes'])), 'news': len(dashboard['news']),
        'snapshot_at': dashboard['generated_at'], 'report_at': report['generated_at'],
        'market_session':market['session'],'refresh_interval_minutes':market['refresh_interval_minutes'],
        'poll_after_seconds':market['poll_after_seconds'],
        'checks': ['unauthenticated_401', 'wrong_code_401', 'post_405', 'dashboard', 'report', 'unknown_404', 'no_store','session_cadence','material_change_feed'],
    }
    (PERSONAL / 'live-verification.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
