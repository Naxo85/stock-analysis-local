import json,sys
from pathlib import Path
folder=Path(sys.argv[1])
out={}
for symbol,expected in [('AMD',507.93),('CLS',269.01),('IREN',25.51)]:
    view=json.loads((folder/symbol/'view.json').read_text(encoding='utf-8'))
    session=next(s for s in view['slim']['price_history']['sessions'] if s['date']=='2026-10-22')
    assert abs(session['close']-expected)<0.00001
    if symbol in ('AMD','CLS'):assert view['owned'] is True
    out[symbol]={'owned':view['owned'],'session':session,'quote':view['slim']['latest_price']}
(folder/'manual_review_facts.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(out,ensure_ascii=True))
