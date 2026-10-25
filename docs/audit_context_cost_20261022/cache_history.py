"""Observe cache receipts across session gaps; no model calls or input changes."""
import json
from pathlib import Path
from datetime import datetime

ROOT=Path(__file__).resolve().parents[2]

def at(text):return datetime.fromisoformat(text.replace('Z','+00:00'))

def main():
    history=[]
    for day in ['2026-10-20','2026-10-21']:
        for file in (ROOT/'logs/batch'/day).glob('*/adaptive/*/triage.receipt.json'):
            row=json.loads(file.read_text(encoding='utf-8'))
            callfile=file.with_name('triage.call.json')
            if not callfile.exists() or not row.get('usage') or not row.get('session_id'):continue
            call=json.loads(callfile.read_text(encoding='utf-8'))
            if not call.get('started_at') or not row.get('completed_at'):continue
            history.append((at(call['started_at']),row,str(file.relative_to(ROOT))))
    history.sort(key=lambda r:r[0]);previous={};seen21=set();first=[]
    for started,row,file in history:
        session=row['session_id'];old=previous.get(session)
        if '2026-10-21/06-52-46/' in file.replace('\\','/') and session not in seen21:
            seen21.add(session)
            first.append({'ticker':Path(file).parent.name,'started_at':started.isoformat(),
                'session_reused':row.get('session_reused'),
                'input_tokens':row['usage']['input_tokens'],'cached_tokens':row['usage']['cached_input_tokens'],
                'gap_hours':(started-at(old[0]['completed_at'])).total_seconds()/3600 if old else None,
                'previous_receipt':old[1] if old else None,
                'same_contract':all(row.get(k)==old[0].get(k) for k in ['model','reasoning_effort','instructions_sha256','schema_sha256','research_enabled']) if old else None})
        previous[session]=(row,file)
    target=Path(__file__).with_name('cache_gap_observations.json')
    target.write_text(json.dumps(first,indent=2),encoding='utf-8')
    print(json.dumps(first,indent=2))

if __name__=='__main__':main()
