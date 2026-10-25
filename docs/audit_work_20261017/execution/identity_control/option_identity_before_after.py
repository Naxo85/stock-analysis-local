"""Reproduce before/after with real function ASTs and simulated requests only."""
import ast
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import json
import math
from pathlib import Path
import re
import types
import xml.etree.ElementTree as ET
ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
NAMES = {'_to_float', '_validate_option_chain_identity', '_option_response', '_parse_option_contract',
         '_contract_multiplier', '_tradier_options_chain', '_observe_option_origins'}
CASES = {
    'explicit_other_underlying_and_expiry': '<options><option><symbol>OTHER261030P00100000</symbol><root_symbol>OTHER</root_symbol><underlying>OTHER</underlying><expiration_date>2026-10-30</expiration_date><strike>100</strike><option_type>put</option_type><contract_size>100</contract_size><open_interest>100</open_interest><greeks><gamma>0.01</gamma></greeks></option></options>',
    'unknown_chain_root': '<garbage/>',
    'adjusted_root_consistent': '<options><option><symbol>CAT1261023P00100000</symbol><root_symbol>CAT1</root_symbol><underlying>CAT</underlying><expiration_date>2026-10-23</expiration_date><strike>100</strike><option_type>put</option_type><contract_size>150</contract_size><open_interest>100</open_interest><greeks><gamma>0.01</gamma></greeks></option></options>',
    'legacy_fields_absent': '<options><option><strike>100</strike><option_type>put</option_type><open_interest>100</open_interest><greeks><gamma>0.01</gamma></greeks></option></options>',
    'legitimate_empty': '<options>null</options>',
}
def run(source_path, body):
    source = source_path.read_bytes()
    class Wire:
        text = body
        def raise_for_status(self): pass
    calls = []
    def get(url, **kwargs): calls.append(kwargs.get('params')); return Wire()
    namespace = {'math':math, 're':re, 'date':date, 'datetime':datetime, 'timezone':timezone,
                 'Decimal':Decimal, 'InvalidOperation':InvalidOperation, 'ET':ET,
                 'requests':types.SimpleNamespace(get=get), 'has_request_context':lambda:False,
                 'TRADIER_BASE':'https://offline.invalid','HEADERS_XML':{},'CALLWALL_TOP_EXPIRATIONS':3}
    tree = ast.parse(source.decode('utf-8'))
    subset = ast.Module(body=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in NAMES], type_ignores=[])
    exec(compile(subset,str(source_path),'exec'),namespace)
    namespace['_tradier_option_expirations'] = lambda symbol:['2026-10-23']
    try:
        chain = namespace['_tradier_options_chain']('CAT','2026-10-23')
        origins = namespace['_observe_option_origins']([('put',100.0)],'CAT',100)
        return {'accepted':True,'chain':chain,'origins':origins,'mocked_requests':len(calls)}
    except ValueError as exc:
        return {'accepted':False,'error':str(exc),'mocked_requests':len(calls)}
sources={'before':HERE/'option_identity_before_main.py',
         'after':HERE/'staged_option_identity/gcp_functions/support_resistances_raw/main.py'}
result={'scope':'synthetic_only_no_historical_incident_demonstrated','external_requests':0,
        'sources':{k:{'path':str(p.relative_to(ROOT)),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for k,p in sources.items()},
        'cases':{name:{phase:run(path,body) for phase,path in sources.items()} for name,body in CASES.items()}}
(HERE/'option_identity_before_after.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({name:{phase:values['accepted'] for phase,values in case.items()} for name,case in result['cases'].items()}))
