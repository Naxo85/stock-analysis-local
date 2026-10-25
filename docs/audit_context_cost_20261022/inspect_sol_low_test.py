import json,sys
from pathlib import Path
folder=Path(sys.argv[1])
for symbol in ('AMD','CLS','IREN'):
    case=folder/symbol
    view=json.loads((case/'view.json').read_text(encoding='utf-8'))
    prior=view['reference']['semantic_data']
    print(symbol,'PRIOR',json.dumps({'summary':prior['summary'], 'plan':{
        k:{f:v.get(f) for f in ('range','reason','strength')} for k,v in prior['plan'].items()},
        'quote':view['slim'].get('latest_price')},ensure_ascii=True))
    output=case/'triage.response'
    if output.exists():
        value=json.loads(output.read_text(encoding='utf-8'))
        print(symbol,'OUTPUT',json.dumps(value,ensure_ascii=True))
