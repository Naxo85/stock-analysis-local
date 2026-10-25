"""Lossless output contracts, source restrictions and receipt recovery; no models."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from src.local_runner import adaptive_stage as stage
from src.local_runner.adaptive_maintenance import maintenance_schema
from src.local_runner.adaptive_policy import load_policy, validate_policy
from src.local_runner.maintenance_schema_transport import VERSION, output_schema, share_definitions

ROOT = Path(__file__).resolve().parents[1]
def wire(v): return json.dumps(v, ensure_ascii=False, separators=(',', ':'), allow_nan=False)
def expanded(schema, original):
    names = set(schema.get('$defs', {})) - set(original.get('$defs', {}))
    def visit(v):
        if isinstance(v, list): return [visit(x) for x in v]
        if not isinstance(v, dict): return deepcopy(v)
        if set(v) == {'$ref'} and v['$ref'].removeprefix('#/$defs/') in names:
            return visit(schema['$defs'][v['$ref'].split('/')[-1]])
        return {k:visit(x) for k,x in v.items()}
    result=deepcopy(schema)
    for name in names: del result['$defs'][name]
    if '$defs' not in original: result.pop('$defs',None)
    return visit(result)

def context(repair=False):
    data={'symbol':'TEST','routing_revision':41,'prepared_at':'2026-10-23T12:00:00Z',
        'reference':{},'sol_reference':{},'news':{},'owned':False,
        'slim':{'as_of':'2026-10-23T12:00:00Z','latest_price':100,
                'levels':{'supports':[{'type':'put_wall','level':99}]}}}
    if repair: data['maintenance_repair']={'error':'invalid_source'}
    return data

class SchemaTests(unittest.TestCase):
    def test_order_ref_collisions_and_literal_enum_data(self):
        repeated={'type':'object','properties':{'a':{'type':'string'},'b':{'type':'boolean'}},
            'required':['a','b'],'additionalProperties':False}
        reverse={**deepcopy(repeated),'properties':dict(reversed(list(repeated['properties'].items())))}
        schema={'type':'object','properties':{'first':repeated,'second':deepcopy(repeated),
            'reverse':reverse,'literal':{'enum':[{'properties':{'same':repeated}}]},
            'old':{'$ref':'#/$defs/m1'}},'required':['first','second','reverse','literal','old'],
            'additionalProperties':False,'$defs':{'m1':{'type':'string'}}}
        before=wire(schema); result=share_definitions(schema)
        self.assertEqual(wire(schema),before)
        self.assertEqual(wire(expanded(result,schema)),before)
        self.assertEqual(result['$defs']['m1'],{'type':'string'})
        self.assertEqual(result['properties']['literal'],schema['properties']['literal'])
        self.assertNotEqual(result['properties']['first'],result['properties']['reverse'])
        self.assertLess(len(wire(result)),len(before))
        self.assertEqual(wire(result),wire(share_definitions(schema)))

    def test_real_maintenance_and_directed_source_enums_remain_exact(self):
        for repair in (False,True):
            with self.subTest(repair=repair):
                original=maintenance_schema(context(repair))
                result=output_schema(original,{'routing_revision':41,'maintenance_output_schema':VERSION},
                    kind='triage_repair' if repair else 'triage')
                self.assertEqual(wire(expanded(result,original)),wire(original))
                self.assertLess(len(wire(result)),len(wire(original)))
                if repair:
                    level=expanded(result,original)['properties']['update']['anyOf'][0]['properties']['plan']['properties']['entry']['anyOf'][0]['properties']
                    self.assertEqual(level['evidence']['items']['enum'],['s1'])
                    self.assertEqual(level['facts']['items']['enum'],['s1'])

    def test_frozen_and_full_unchanged_invalid_versions_rejected(self):
        original=maintenance_schema(context())
        self.assertIs(output_schema(original,{},kind='triage'),original)
        enabled={'routing_revision':41,'maintenance_output_schema':VERSION}
        self.assertIs(output_schema(original,enabled,kind='report'),original)
        self.assertIsNone(output_schema(None,enabled,kind='report'))
        for policy in ({**enabled,'routing_revision':40}, {**enabled,'maintenance_output_schema':'other'}):
            with self.subTest(policy=policy), self.assertRaises(ValueError):
                output_schema(original,policy,kind='triage')
        policy=load_policy(ROOT)
        for version,revision in [('other',41),(VERSION,40)]:
            old={**policy,'maintenance_output_schema':version,'routing_revision':revision}
            old.pop('volume_calculation_guidance',None)
            with self.assertRaisesRegex(ValueError,'maintenance_output_schema'):
                validate_policy(old)

class ModelContractTests(unittest.TestCase):
    def test_wire_schema_receipt_recovery_and_legacy_contract_isolation(self):
        for kind in ('triage','triage_repair','report'):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as folder:
                root=Path(folder);work=root/'work';work.mkdir()
                for name in ('triage_instructions.md','instructions.md'):
                    (work/name).write_text('fixed instructions',encoding='utf-8')
                policy=load_policy(ROOT)
                policy.update(maintenance_output_schema=VERSION,luna_news_research_enabled=False,
                    report_web_research_enabled=False)
                data=context(kind=='triage_repair');calls=[]
                def fake_call(**kwargs):
                    calls.append(deepcopy(kwargs));text='{}'
                    schema=kwargs['schema'];instructions=kwargs['instructions']
                    receipt={'text':text,'exit_code':0,'usage':{'input_tokens':1,'output_tokens':1},
                        'model':kwargs['model'],'reasoning_effort':kwargs['effort'],'research_enabled':False,
                        'instructions_sha256':hashlib.sha256(instructions.encode()).hexdigest(),
                        'schema_sha256':hashlib.sha256(json.dumps(schema,sort_keys=True).encode()).hexdigest(),
                        'input_sha256':hashlib.sha256(stage.serialize_model_input(kwargs['data']).encode()).hexdigest(),
                        'response_sha256':hashlib.sha256(text.encode()).hexdigest()}
                    (work/(kind+'.response')).write_text(text,encoding='utf-8')
                    (work/(kind+'.receipt.json')).write_text(json.dumps({k:v for k,v in receipt.items() if k!='text'}),encoding='utf-8')
                    return receipt
                with patch.object(stage,'model_context',side_effect=deepcopy), \
                     patch.object(stage,'load_triage',return_value=None), \
                     patch.object(stage,'save_triage'), patch.object(stage,'reserve',return_value='TEST:'+kind), \
                     patch.object(stage,'finish'), patch.object(stage,'call_codex',side_effect=fake_call):
                    first=stage.model_call(root,work,'TEST',root/'budget.json',policy,kind,data)
                    cached=stage.model_call(root,work,'TEST',root/'budget.json',policy,kind,data,reuse_only=True)
                    self.assertEqual(first['text'],cached['text']);self.assertEqual(len(calls),1)
                    raw=(maintenance_schema(data) if kind!='report' else __import__(
                        'src.local_runner.semantic_report',fromlist=['report_schema']).report_schema(41))
                    self.assertEqual(wire(expanded(calls[0]['schema'],raw)),wire(raw))
                    old={k:v for k,v in policy.items() if k!='maintenance_output_schema'}
                    if kind=='report':
                        stage.model_call(root,work,'TEST',root/'budget.json',old,kind,data,reuse_only=True)
                        self.assertEqual(calls[0]['schema'],raw)
                    else:
                        self.assertNotEqual(first['schema_sha256'],hashlib.sha256(json.dumps(raw,sort_keys=True).encode()).hexdigest())
                        with self.assertRaisesRegex(RuntimeError,'contract_mismatch_no_automatic_retry'):
                            stage.model_call(root,work,'TEST',root/'budget.json',old,kind,data,reuse_only=True)
                    self.assertEqual(len(calls),1)

if __name__=='__main__': unittest.main()
