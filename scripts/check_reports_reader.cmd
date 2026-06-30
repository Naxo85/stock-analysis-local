@echo off
setlocal

set "SYMBOL=%~1"
if "%SYMBOL%"=="" set "SYMBOL=MU"

python -c "import json,sys,urllib.request; sym=sys.argv[1].upper(); url='https://reports-714254943648.europe-southwest1.run.app?symbol='+sym; data=json.load(urllib.request.urlopen(url, timeout=60)); summary=data.get('analyst_ratings_summary') or {}; print(json.dumps({'symbol': data.get('symbol'), 'generated_at': data.get('generated_at'), 'analyst_ratings_summary': summary}, indent=2, sort_keys=True))" "%SYMBOL%"

endlocal
