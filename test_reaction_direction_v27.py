"""Original incident and negative controls; no model calls."""
from copy import deepcopy
import json
from pathlib import Path
import pytest
from src.local_runner.adaptive_context import model_context, unpack_model_context
from src.local_runner.semantic_binding import bind_response
from src.local_runner.semantic_report import full_document, reference_document
from src.local_runner.reaction_direction import reaction_direction, applicable_reaction
from src.local_runner.volume_arithmetic import validate
from src.local_runner.semantic_sources import source_catalog
ROOT = Path(__file__).resolve().parent
BATCH = ROOT / 'logs/batch/2026-10-12/20-42-28/adaptive'

def original():
    p = BATCH / 'IONQ'
    c = json.loads((p/'input.json').read_text(encoding='utf8'))
    sent = unpack_model_context(json.loads((p/'report.input.json').read_text(encoding='utf8')))
    for key in ('guards','review_flags','itv','triage','news'): c[key] = sent[key]
    r = json.loads((p/'report.receipt.json').read_text(encoding='utf8'))
    r['text'] = (p/'report.response').read_text(encoding='utf8')
    return c, r

def test_ionq_original_passes_without_changing_financial_content():
    c,r = original(); value=json.loads(r['text']); before=deepcopy((c,r,value))
    doc=full_document(value,model_context(c),binding=bind_response(c,r,'report'))
    assert (c,r,value) == before
    for key,level in value['plan'].items():
        for field in ('range','strength','reason'):
            assert doc['plan'][key][field] == level[field]
    assert doc['summary'] == value['summary']
    assert doc['conclusion'] == value['conclusion']
    assert doc['plan']['resistance']['strength']['components']['volumen'] == 2

def test_42_published_projections_remain_authentic():
    files=list(BATCH.glob('*/publish/output/*/latest.json')); assert len(files)==42
    for path in files:
        before=path.read_bytes()
        reference_document(json.loads(before),verify_projection=True)
        assert path.read_bytes()==before

def test_new_context_adds_direction_without_changing_frozen26():
    from src.local_runner.adaptive_repair import repair_context
    c,r=original(); old=model_context(c); new=model_context(dict(c,routing_revision=27))
    assert new['comparison']['contract']=='adaptive-semantic-context-v27'
    assert source_catalog(new)==source_catalog(old)
    records=new['comparison']['volume_rubric']['records']
    assert records and any(v['reaction_direction']=='support' for v in records.values())
    assert all('reaction_direction' not in v for v in old['comparison']['volume_rubric']['records'].values())
    assert model_context(c)==old
    assert 'Revision27:' in repair_context({'routing_revision':27},{},'test')['maintenance_repair']['instruction']
    assert 'Revision27:' not in repair_context({'routing_revision':26},{},'test')['maintenance_repair']['instruction']

def test_support_rebound_cannot_be_resistance_arithmetic():
    c,r=original(); binding=bind_response(c,r,'report'); c=model_context(c)
    doc=full_document(json.loads(r['text']),c,binding=binding)
    level=doc['plan']['resistance']; catalog=source_catalog(c)
    row=next(h for h,v in catalog.items() if v['pointer'] in level['evidence'] and
        reaction_direction(v['value'],v['pointer'])=='support' and
        v['value'].get('evidence',{}).get('historical_reaction',{}).get('status')=='available')
    level['volume_calculation']=dict(profile_source=row,reaction_source=row)
    with pytest.raises(ValueError,match='reaction_direction_not_applicable'):
        validate(level,'resistance',c,None)
    level['volume_calculation']=None
    with pytest.raises(ValueError,match='select_profile_and_reaction_sources'):
        validate(level,'entry',c,None)

@pytest.mark.parametrize('method,direction,pointer,expected', [
    ('daily_level_tests_collapsed_then_max_high_5_sessions','resistance','/slim/levels/put_walls_top/0','support'),
    (None,None,'/slim/levels/supports/0','support'),
    ('unknown',None,'/slim/levels/supports/0',None),
    (None,None,'/slim/levels/call_walls_top/0',None),
    ('downward_rejections','resistance','/slim/levels/resistances/0','resistance')])
def test_direction_is_measurement_not_current_role(method,direction,pointer,expected):
    value={'evidence':{'historical_reaction':{'method':method,'direction':direction}}}
    assert reaction_direction(value,pointer)==expected
    assert applicable_reaction(value,pointer,'resistance')==(expected=='resistance')
    assert applicable_reaction(value,pointer,'entry')==(expected=='support')

def test_recovery_routing_authenticates_frozen_input_and_keeps_original_age(tmp_path):
    import shutil
    from src.local_runner.adaptive_stage import receipt_itv
    for name in ('triage.input.json','triage.receipt.json'):
        shutil.copy2(BATCH/'IONQ'/name,tmp_path/name)
    assert receipt_itv(tmp_path)['age_sessions']==2
    with (tmp_path/'triage.input.json').open('a') as f: f.write(' ')
    with pytest.raises(RuntimeError,match='not_authenticated'): receipt_itv(tmp_path)
