import json
from pathlib import Path
import sys
sys.stdout.reconfigure(encoding='utf-8')

ROOT = Path(__file__).resolve().parents[3]
BASE = ROOT / 'logs/batch/2026-10-18/09-08-40/adaptive'
def read(path): return json.loads(path.read_text(encoding='utf-8-sig'))
def dump(value): return json.dumps(value, ensure_ascii=False, indent=2)
def brief_level(v):
    value={k:x for k,x in v.items() if k in ['type','level','date','notes','status','evidence','oi','expiration']}
    if 'evidence' in value:
        value['evidence']={k:{m:n for m,n in x.items() if m not in ['path_evidence','measurement_basis']} for k,x in value['evidence'].items()}
    return value

if len(sys.argv) > 1 and sys.argv[1]=='newzeros':
    for path in sorted(BASE.glob('*/publish/output/*/latest.json')):
        obj=read(path); p=obj['plan']; inp=read(BASE/path.parent.name/'input.json'); ref=inp['reference']['plan']
        for role,prefix in [('entry','entry'),('ambitious_entry','washout')]:
            if p.get(prefix+'_strength_breakdown',{}).get('opciones')==0:
                prev_roles=[x for x in ['entry','ambitious_entry'] if ref.get(x)==p.get(role)]
                print(path.parent.name,role,p[role], 'prior same range',prev_roles)
elif len(sys.argv) > 1 and sys.argv[1]=='gamma':
    for path in sorted(BASE.glob('*/publish/output/*/latest.json')):
        obj=read(path); p=obj['plan']
        for role,prefix in [('entry','entry'),('ambitious_entry','washout')]:
            f=p.get(prefix+'_strength_factors','')
            if any(s in f.lower() for s in ['gamma negativ','régimen gamma','regimen gamma','dealer']):
                print(path.parent.name,role,obj.get('generated_at'),p.get(prefix+'_strength_breakdown'),f)
elif len(sys.argv) > 1 and sys.argv[1]=='auditvol':
    for path in sorted(BASE.glob('*/publish/output/*/latest.json')):
        obj=read(path)
        for role,lv in obj['semantic_report']['data']['plan'].items():
            if isinstance(lv,dict):
                audit=lv.get('volume_calculation_audit')
                if audit: print(path.parent.name,role,dump(audit))
elif len(sys.argv) > 1 and sys.argv[1]=='sources':
    for ticker in sys.argv[2:]:
        inp=read(BASE/ticker/'input.json'); obj=read(BASE/ticker/'publish/output'/ticker/'latest.json'); s=inp['slim']; p=obj['plan']
        print(ticker, 'date', obj.get('generated_at'), 'PLAN',dump({k:v for k,v in p.items() if k in ['entry','ambitious_entry']}))
        print('VP',dump(s.get('volume_profile')))
        print('TECH', dump({k:v for k,v in s['technicals'].items() if k in ['atr10','sma20','sma50','sma200']}))
        for family, levels in s['levels'].items():
            if isinstance(levels,list):
                for lv in levels:
                    if isinstance(lv,dict) and family in ['supports']:
                        print(family,dump(brief_level(lv)))
elif len(sys.argv) > 1 and sys.argv[1]=='zeros':
    for path in sorted(BASE.glob('*/publish/output/*/latest.json')):
        obj=read(path); p=obj['plan']
        for role,prefix in [('entry','entry'),('ambitious_entry','washout')]:
            b=p.get(prefix+'_strength_breakdown',{})
            if b.get('volumen')==0:
                print(path.parent.name, role, dump(p.get(role)), dump(b))
                print(p.get(prefix+'_strength_factors'))
elif len(sys.argv) > 1 and sys.argv[1]=='changes':
    for path in sorted(BASE.glob('*/publish/output/*/latest.json')):
        obj=read(path); p=obj['plan']; inp=read(BASE/path.parent.name/'input.json'); old=inp['reference']['plan']
        for role,prefix in [('entry','entry'),('ambitious_entry','washout')]:
            b=p.get(prefix+'_strength_breakdown',{}); oldb=old.get(prefix+'_strength_breakdown',{})
            if b and b!=oldb and p.get(role)==old.get(role):
                print(path.parent.name, role, dump(p.get(role)), dump(oldb), '=>',dump(b))
                print(p.get(prefix+'_strength_factors'))
elif len(sys.argv) > 1:
    ticker = sys.argv[1]
    obj = read(BASE / ticker / 'publish/output' / ticker / 'latest.json')
    inp = read(BASE / ticker / 'input.json')
    tri = read(BASE / ticker / 'triage.json')
    print('ROOT', list(obj))
    print('PLAN', dump({k:v for k,v in obj.get('plan',{}).items() if 'validity' not in k}))
    print('SEMANTIC KEYS', list(obj.get('semantic_report', {})))
    print('SEMANTIC PLAN KEYS', {k:list(v) for k,v in obj.get('semantic_report',{}).get('data',{}).get('plan',{}).items() if isinstance(v,dict)})
    print('TRIAGE', dump(tri))
    if len(sys.argv) > 2:
        print('SLIM', dump(inp.get('slim')))
else:
    for path in sorted(BASE.glob('*/publish/output/*/latest.json')):
        obj = read(path)
        p=obj.get('plan',{})
        print(path.parent.name)
        print(dump({k:v for k,v in p.items() if 'strength' in k or k in ['entry','ambitious_entry']}))
