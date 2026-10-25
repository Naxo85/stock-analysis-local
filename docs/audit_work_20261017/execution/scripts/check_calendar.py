import sys,json
from pathlib import Path
from datetime import date,timedelta
ROOT=Path(r'E:/stock-analysis-local');sys.path.insert(0,str(ROOT))
from src.local_runner.adaptive_policy import market_session
p=ROOT/'.tmp/audit_execution_20261017/baseline/src/local_runner/adaptive_policy.py'
s=p.read_text(encoding='utf-8');ns={'date':date,'timedelta':timedelta};exec(s[s.index('def _observed'):s.index('def session_age')],ns)
mismatches=[];start=date(1990,1,1);end=date(2040,1,1)
for n in range((end-start).days):
 d=start+timedelta(days=n)
 for extra in [(),('2025-01-09',)]:
  if market_session(d,extra)!=ns['market_session'](d,extra):mismatches.append(str(d))
result={'dates':(end-start).days,'extra_closure_variants':2,'mismatches':mismatches}
(ROOT/'.tmp/audit_execution_20261017/calendar_compatibility.json').write_text(json.dumps(result,indent=2));print(result);assert not mismatches
