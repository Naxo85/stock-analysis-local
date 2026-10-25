"""Offline exact-source reader prototype, not a model context or runtime tool."""
from copy import deepcopy
from pathlib import Path
import hashlib, json, sys
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
from src.local_runner.adaptive_context import unpack_model_context, resolve_evidence, compact_json

class FrozenSources:
    def __init__(self, context, binding):
        self._catalog=deepcopy(context['source_catalog'])
        self._binding=binding
        for handle,record in self._catalog.items():
            assert compact_json(resolve_evidence(context,record['pointer']))==compact_json(record['value']),handle
    def read(self, handles, *, runner_binding):
        # runner_binding belongs to the client lease/receipt, never a model arg.
        if runner_binding!=self._binding: raise ValueError('different_frozen_input')
        if not isinstance(handles,list) or not handles: raise ValueError('invalid_source_request')
        if any(type(h) is not str or h not in self._catalog for h in handles):
            raise ValueError('unknown_source_handle')
        return [{'source':h,**deepcopy(self._catalog[h])} for h in handles]

def rejects(fn):
    try:fn()
    except ValueError:return 1
    raise AssertionError('invalid source request admitted')

out={'contexts':0,'exact_source_records':0,'rejections':0,
    'limits':'Reader preserves records, not proof of discovery, financial completeness, fewer tokens or model quality.'}
for day,hour in [('2026-10-21','06-52-46'),('2026-10-22','12-32-48')]:
    for file in sorted((ROOT/'logs/batch'/day/hour/'adaptive').glob('*/triage.input.json')):
        raw=file.read_bytes();binding=hashlib.sha256(raw).hexdigest()
        context=unpack_model_context(json.loads(raw))
        store=FrozenSources(context,binding)
        handles=list(context['source_catalog'])
        records=store.read(handles,runner_binding=binding)
        for record in records:
            h=record.pop('source')
            assert compact_json(record)==compact_json(context['source_catalog'][h])
        out['exact_source_records']+=len(records);out['contexts']+=1
        out['rejections']+=rejects(lambda:store.read(handles,runner_binding='other-input'))
        out['rejections']+=rejects(lambda:store.read(['unknown'],runner_binding=binding))
        out['rejections']+=rejects(lambda:store.read(['/slim/levels/0'],runner_binding=binding))
        out['rejections']+=rejects(lambda:store.read([],runner_binding=binding))
        # Returned values cannot mutate the frozen store or input.
        first=store.read([handles[0]],runner_binding=binding)
        first[0]['value']=None
        assert store.read([handles[0]],runner_binding=binding)[0]['value']==context['source_catalog'][handles[0]]['value']
        assert hashlib.sha256(file.read_bytes()).hexdigest()==binding
Path(__file__).with_name('sources.json').write_text(json.dumps(out,indent=2),encoding='utf-8')
print(json.dumps(out,indent=2))
