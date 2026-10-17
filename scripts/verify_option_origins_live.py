"""One technical source capture only; no model, financial report or batch.

The existing endpoint has its normal technical-JSON mirror side effect.
Requested identities derive from the authenticated original APP incident base.
"""
import argparse
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from src.local_runner.technical_preparation import option_origins,require_option_origins,require_capture,require_price_history
from src.local_runner.run_one import _fetch_slim

def main():
    p=argparse.ArgumentParser();p.add_argument('--execute',action='store_true');a=p.parse_args()
    assert a.execute,'explicit technical capture required'
    original=ROOT/'logs/batch/2026-10-16/15-58-24/adaptive/APP/input.json'
    frozen=original.read_bytes();context=json.loads(frozen)
    identities=option_origins(context['reference'])
    assert ('put',250.0) in identities
    data=_fetch_slim('APP',option_origins=identities)
    require_capture(data);require_price_history(data);require_option_origins(data,identities)
    assert original.read_bytes()==frozen
    dest=ROOT/'logs/deploy_origins39/live-source.json'
    dest.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
    rows=data['levels']['option_origins']
    result={'as_of':data['as_of'],'requested':identities,
            'top_strikes':[r['level'] for r in data['levels']['put_walls_top']],
            'observations':[{'strike':r['level'],'status':r['status'],
                             'expirations':r['option_details']['sampled_expirations']}
                            for r in rows]}
    (dest.parent/'live-source-verification.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result),flush=True)

if __name__=='__main__':main()
