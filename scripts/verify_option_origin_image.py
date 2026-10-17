"""Small offline image gate; no credentials, market fetch or model."""
import ast
import math
from pathlib import Path
import re
import sys
import types
import xml.etree.ElementTree as ET

kind=sys.argv[1]
source=Path('/app/main.py').read_text(encoding='utf-8')
if kind=='raw':
    tree=ast.parse(source)
    selected=[n for n in tree.body if isinstance(n,ast.FunctionDef)
              and n.name in {'_parse_option_origins','_observe_option_origins','_to_float'}]
    ns=dict(math=math,re=re,ET=ET,CALLWALL_TOP_EXPIRATIONS=3,
            HEADERS_XML={},TRADIER_BASE='offline',
            _tradier_option_expirations=lambda s:['2030-01-01'])
    exec(compile(ast.Module(body=selected,type_ignores=[]),'<image-helpers>','exec'),ns)
    for xml,status,oi in [
        ('<options/>','not_observed',None),
        ('<options><option><strike>250</strike><option_type>put</option_type><open_interest>0</open_interest><greeks><gamma>1</gamma></greeks></option></options>','available',0),
        ('<options><option><strike>250</strike><option_type>put</option_type></option></options>','available',None),
    ]:
        ns['_option_response']=lambda *a,**k:types.SimpleNamespace(text=xml)
        row=ns['_observe_option_origins']([('put',250.0)],'TEST',270)[0]
        assert row['status']==status
        assert row['option_details']['by_expiration'][0]['aggregate_oi']==oi
    assert ns['_parse_option_origins']('put:250,put:250.0')==[('put',250.0)]
else:
    ns={};exec(compile(source,'<image-slim>','exec'),ns)
    row={'type':'option_origin_observation','level':250,'status':'not_observed',
         'reason':'not_observed_in_sampled_expirations',
         'option_details':{'option_type':'put','strike':250,'sampled_expirations':[],
                           'by_expiration':[],'scope':'parsed_contracts_in_sampled_expirations'}}
    result=ns['_build_slim']({'symbol':'TEST','latest_price':270,'option_origins':[row]})
    observed=result['levels']['option_origins'][0]
    assert observed['status']=='not_observed' and observed['option_details']==row['option_details']
    assert 'option_origins' not in ns['_build_slim']({})['levels']
print(kind+': offline image origin checks passed')
