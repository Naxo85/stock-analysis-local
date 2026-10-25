import ast, json, pathlib, math, statistics, logging, sys
sys.path.insert(0,str(pathlib.Path.cwd()))
from datetime import datetime, date, timedelta, timezone
from gcp_functions.support_resistances_raw.market_sessions import is_completed_session
root=pathlib.Path.cwd()
source=root/'gcp_functions/support_resistances_raw/main.py'
selected={'_complete_daily_bars','_volume_20d_package','_to_float','_median','_trend_bias_confidence_1_2w'}
functions=[n for n in ast.parse(source.read_text(encoding='utf8')).body if isinstance(n,ast.FunctionDef) and n.name in selected]
ns={'math':math,'statistics':statistics,'datetime':datetime,'date':date,'timedelta':timedelta,'timezone':timezone,'is_completed_session':is_completed_session,'tlogger':logging.getLogger('offline')}
exec(compile(ast.Module(body=functions,type_ignores=[]),str(source),'exec'),ns)
rows=[]
for path in sorted((root/'logs/batch/2026-10-16/15-58-24/adaptive').glob('*/input.json')):
    ctx=json.loads(path.read_text(encoding='utf8')); slim=ctx['slim']
    asof=datetime.fromisoformat(slim['as_of'].replace('Z','+00:00'))
    ns['_snapshot_time']=lambda:asof
    history=slim['price_history']['sessions']
    fixed=ns['_volume_20d_package'](history)['last_complete_day']
    assert fixed['date']==history[-1]['date']
    previous=slim['technicals']['volume_last_complete_day']
    def contribution(ratio):
        result=ns['_trend_bias_confidence_1_2w'](slim['latest_price'],{'volume':{'last_complete_day':{'rel_to_20d':ratio}}},{},{},[],[])
        return result['components']['D_volume_tape']['score']
    old,corrected=contribution(previous['rel_to_20d']),contribution(fixed['rel_to_20d'])
    rows.append({'symbol':slim.get('symbol',path.parent.name),'as_of':slim['as_of'],'prior':previous,'corrected':fixed,'legacy_D_original':old,'legacy_D_corrected':corrected})
summary={'captures':len(rows),'partial_as_completed':sum(r['prior']['date']!=r['corrected']['date'] for r in rows),'legacy_auxiliary_D_changed':sum(r['legacy_D_original']!=r['legacy_D_corrected'] for r in rows),'note':'Source40 does not emit directional trend score. This comparison isolates historical propagation of the volume defect; it does not re-score a financial report.'}
(root/'.tmp/audit_execution_20261017/data_volume_original_replay.json').write_text(json.dumps({'summary':summary,'cases':rows},indent=2),encoding='utf8')
print(json.dumps(summary,indent=2))
