"""Offline audit regressions: no real models, publications or source rewrites."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from contextlib import ExitStack
import tempfile
import unittest
from unittest.mock import patch

import test_maintenance_change_v14 as v14
from src.local_runner.adaptive_context import model_context, serialize_model_input, unpack_model_context
from src.local_runner.semantic_sources import source_catalog, resolve_source, normalize_plan
from src.local_runner.semantic_report import reference_document, digest, render_document, publication_fields
from src.local_runner.adaptive_policy import daily_decision
from src.local_runner.adaptive_news_research import collect_news_research
from src.local_runner.maintenance_change import change_justification_only

ROOT = Path(__file__).resolve().parent
BATCH = ROOT / 'logs/batch/2026-10-07/16-35-33/adaptive'


def context():
    raw = v14.prior.data(); raw['routing_revision'] = 15
    return model_context(raw)


def candidate(data):
    value = v14.sparse.candidate(data)
    value['update']['change_review'] = dict(setup=None, conclusion=None, routine_note=None)
    return value


def commentary_review(key='setup', basis='backing_changed', scope='routine_technical'):
    return dict(basis=basis, scope=scope, previous_evidence=['/reference/semantic_data/summary'],
        current_evidence=['/slim'], explanation='Comparacion financiera relevante con fuentes fechadas.')


class Audit15Tests(unittest.TestCase):
    def test_setup_requires_evidence_and_rejects_declared_quote_only(self):
        data = context(); value = candidate(data)
        value['update'].update(setup_score=9.9, setup_reason='Solo cambio un centimo.')
        for review in (None, commentary_review(basis='quote_only')):
            value['update']['change_review']['setup'] = review
            with self.assertRaisesRegex(ValueError, 'change_not_established'):
                v14.v3.document(data, value)
        value['update']['change_review']['setup'] = commentary_review()
        value['update']['setup_reason'] = 'Deterioro relevante comparado con la referencia.'
        doc = v14.v3.document(data, value)
        self.assertEqual(doc['summary']['setup_score'], 9.9)
        old = reference_document(data['reference'])
        for key in old['plan']:
            for field in ('range','strength','reason'):
                self.assertEqual(doc['plan'][key][field], old['plan'][key][field])

    def test_all_commentary_fields_require_reviews_with_correct_scopes(self):
        for key in ('setup', 'conclusion', 'routine_note'):
            data = context(); value = candidate(data)
            if key == 'setup': value['update'].update(setup_score=5, setup_reason='Cambio verificado.')
            elif key == 'conclusion': value['update']['conclusion'] = 'Cambio verificado.'
            else: value['routine_note'] = 'Cambio verificado.'
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, 'missing_review'):
                v14.v3.document(data, value)
            review = commentary_review(key); review['current_evidence'] = ['/reference']
            value['update']['change_review'][key] = review
            with self.assertRaisesRegex(ValueError, 'wrong_scope'):
                v14.v3.document(data, value)

    def test_fundamental_conclusion_scope_routes_sol_even_with_false_risk_flags(self):
        data = context(); value = candidate(data)
        value['update']['conclusion'] = 'La tesis fundamental ha cambiado.'
        value['update']['change_review']['conclusion'] = commentary_review(scope='fundamental_or_structural')
        self.assertFalse(any(value['risk'].values()))
        self.assertEqual(daily_decision(value, [], data), 'escalate')
        with self.assertRaisesRegex(ValueError, 'uncertain_or_critical'): v14.v3.document(data, value)
        value['evidence_gap'] = 'essential_data'
        self.assertEqual(daily_decision(value, [], data), 'blocked')

    def test_empty_update_retain_and_protected_fields(self):
        data = context(); value = candidate(data)
        self.assertEqual(daily_decision(value, [], data), 'retain')
        self.assertEqual(daily_decision(value, ['hard_guard'], data), 'escalate')
        value['update']['thesis_score'] = 0
        with self.assertRaises(ValueError): v14.v3.document(data, value)

    def test_statement_truth_is_not_claimed_by_source_binding(self):
        # Explicitly document the remaining model-judgment boundary, rather
        # than pretending a regex could validate arbitrary financial prose.
        data = context(); value = candidate(data)
        value['update'].update(setup_score=5, setup_reason='A claim requiring model judgment.')
        value['update']['change_review']['setup'] = commentary_review()
        self.assertEqual(v14.v3.document(data, value)['summary']['setup_score'], 5)

    def test_sources_never_expand_prior_audits_as_financial_facts(self):
        data = context(); doc = reference_document(data['reference'])
        doc['plan']['entry']['resolved_facts'] = [{'value': {'resolved_facts': ['AUDIT_ONLY']}}] * 100
        md = data['reference']['analysis_markdown']
        data['reference']['semantic_report'] = dict(version=1, data=doc, data_sha256=digest(doc),
            markdown_sha256=hashlib.sha256(md.encode()).hexdigest())
        data = model_context(data)
        cat = source_catalog(data); handle = v14.handle(data, '/reference/semantic_data/plan/entry')
        self.assertEqual(set(cat[handle]['value']), {'range', 'reason', 'strength'})
        self.assertEqual(resolve_source(data, cat[handle]['pointer']), cat[handle]['value'])
        view = unpack_model_context(json.loads(serialize_model_input(data)))
        self.assertNotIn('semantic_report', view['reference'])
        self.assertNotIn('AUDIT_ONLY', serialize_model_input(data))
        self.assertIn('AUDIT_ONLY', json.dumps(data))
        block = v14.prior.level(doc['plan']['entry']['range']); block.pop('transition')
        block['evidence'] = block['facts'] = [handle]
        normalized, issues = normalize_plan({'entry': block}, doc['plan'], data)
        self.assertFalse(issues)
        self.assertFalse(any('resolved_facts' in x for x in normalized['entry']['facts']))

    def test_corrupt_original_envelope_still_fails(self):
        data = context(); doc = reference_document(data['reference'])
        data['reference']['semantic_report'] = dict(version=1, data=doc, data_sha256='wrong', markdown_sha256='wrong')
        with self.assertRaisesRegex(ValueError, 'integrity'): serialize_model_input(data)

    def test_spcx_real_input_financial_view_small_and_original_untouched(self):
        path = BATCH/'SPCX/input.json'
        if not path.exists(): self.skipTest('Optional original archive')
        original = path.read_bytes(); raw = json.loads(original)
        old = reference_document(raw['reference']); raw['routing_revision'] = 15
        view = unpack_model_context(json.loads(serialize_model_input(model_context(raw))))
        text = serialize_model_input(model_context(raw))
        self.assertLess(len(text), 1048576)
        for side in ('reference', 'sol_reference'):
            self.assertEqual(view[side]['analysis_markdown'], raw[side]['analysis_markdown'])
            self.assertEqual(view[side]['slim_snapshot'], raw[side]['slim_snapshot'])
        for key, block in old['plan'].items():
            for field in ('range','strength','reason'):
                self.assertEqual(view['reference']['semantic_data']['plan'][key][field], block[field])
        self.assertEqual(path.read_bytes(), original)

    def test_real_intc_preserves_search_excerpt_instead_of_total_lines(self):
        folder = BATCH/'INTC'
        if not folder.exists(): self.skipTest('Optional original archive')
        events = (folder/'triage.events.jsonl').read_text(encoding='utf8')
        receipt = json.loads((folder/'triage.receipt.json').read_text(encoding='utf8'))
        payload = json.loads((folder/'triage.json').read_text(encoding='utf8'))
        old = collect_news_research(events,receipt,payload,revision=14)
        new = collect_news_research(events,receipt,payload,revision=15)
        self.assertEqual(old['sources'][0]['excerpt'], 'Total lines: 670')
        row = new['sources'][0]
        self.assertIn('Reuters',row['excerpt'])
        self.assertFalse(row['page_content_available'])
        self.assertTrue(row['verification_required'])
        self.assertEqual(len(row['observations']), 2)

    def test_news_collects_other_assessments_and_distinguishes_page_text(self):
        url='https://example.test/article'
        e=json.dumps({'type':'item.completed','item':{'id':'web1','type':'web_search',
            'results':[{'url':url,'snippet':'Total lines: 42','content':'Actual recorded page text.'}]}})
        receipt=dict(luna_news_events_sha256=hashlib.sha256(e.encode()).hexdigest(),web_search_count=1)
        result=collect_news_research(e,receipt,{'events':{'assessment':url}},revision=15)
        self.assertIsNone(result['sources'][0]['excerpt'])
        self.assertTrue(result['sources'][0]['page_content_available'])
        self.assertEqual(result['sources'][0]['observations'][0]['page_content'],'Actual recorded page text.')

    def test_frozen14_receipts_unchanged(self):
        for ticker in ('INTC','MP'):
            folder=BATCH/ticker
            if not folder.exists(): self.skipTest('Optional original archive')
            raw=json.loads((folder/'input.json').read_text(encoding='utf8'))
            reviewed=json.loads((folder/'review.json').read_text(encoding='utf8'))
            for field in ('guards','itv','review_flags'):raw[field]=reviewed[field]
            raw=model_context(raw);raw.pop('research_memory',None)
            receipt=json.loads((folder/'triage.receipt.json').read_text(encoding='utf8'))
            self.assertEqual(hashlib.sha256(serialize_model_input(raw).encode()).hexdigest(),receipt['input_sha256'])

    def test_repeated_report_sources_have_bounded_fact_graph(self):
        data=context(); sizes=[]
        for _ in range(5):
            value=v14.prior.full(data)
            for key,level in value['plan'].items():
                level.pop('transition')
                level['evidence']=[v14.handle(data,'/slim/levels/supports/0')]
                level['facts']=[v14.handle(data,'/reference/semantic_data/plan/'+key)]
            doc=v14.v3.document(data,value,full=True)
            self.assertLess(max(len(v['facts']) for v in doc['plan'].values()),20)
            md=render_document(doc)
            data['reference'].update(analysis_markdown=md,
                semantic_report=dict(version=1,data=doc,data_sha256=digest(doc),
                    markdown_sha256=hashlib.sha256(md.encode()).hexdigest()))
            data=model_context(data)
            sizes.append(len(serialize_model_input(data)))
        self.assertLess(max(sizes)-min(sizes),2000)


class AuditPipelineTests(unittest.TestCase):
    def test_new_preparation_freezes_override_for_both_models(self):
        stage=v14.prior.stage;data=context()
        with tempfile.TemporaryDirectory() as directory,ExitStack() as stack:
            work=Path(directory)/'CAT';work.mkdir()
            stack.enter_context(patch.object(stage,'datetime',v14.prior.base.FrozenClock))
            for name,value in {'load_policy':{**v14.prior.base.POLICY,'routing_revision':15},
                'load_reference_payload':data['sol_reference'],'load_current_report':data['reference'],
                'load_research':None}.items():stack.enter_context(patch.object(stage,name,return_value=value))
            for name,value in {'_fetch_slim':data['slim'],'_load_analyst_quality':{},
                'load_compact_analyst_summary':{},'load_recent_analyst_actions':data['analyst_actions'],
                'load_recent_news':data['news'],'_load_system_prompt':'legacy'}.items():
                stack.enter_context(patch.object(stage.one,name,return_value=value))
            stack.enter_context(patch.object(stage,'call_codex',side_effect=AssertionError('NO MODEL')))
            stage.prepare(ROOT,work,'CAT',False,'tracking')
            for filename in ('instructions.md','triage_instructions.md'):
                text=(work/filename).read_text(encoding='utf8')
                self.assertIn('REVISION15 OVERRIDE',text)
                self.assertIn('maintenance_handoff',text)
            self.assertEqual(json.loads((work/'policy.json').read_text())['routing_revision'],15)

    def run_pipeline(self, bases=('prior_error',), **kwargs):
        old_verdict,old_full=v14.prior.verdict,v14.prior.full
        choices=iter(bases)
        def verdict(data,decision='update'):
            basis=next(choices)
            if basis=='retain': return old_verdict(data,'retain')
            value=old_verdict(data,decision)
            if value.get('update'):
                value['update']['change_review']={k:commentary_review(k,basis=basis)
                    if k!='routine_note' or value['routine_note'].strip() else None
                    for k in ('setup','conclusion','routine_note')}
                for key,level in value['update']['plan'].items():
                    level['evidence']=[v14.handle(data,'/slim/levels/supports/0')]
                    level['change_review']=v14.review(data,key,basis)
            return value
        def full(data):
            value=old_full(data)
            for level in value['plan'].values():level['evidence']=[v14.handle(data,'/slim/levels/supports/0')]
            return value
        with patch.object(v14.prior,'verdict',side_effect=verdict),patch.object(v14.prior,'full',side_effect=full):
            return v14.prior.SemanticPipelineTests().run_case(revision=15,**kwargs)

    def test_full_handoff_includes_both_rejected_proposals_and_all_issues(self):
        result,_,calls=self.run_pipeline(('missing_from_snapshot','missing_from_snapshot'),
            initial_bad=True,repair_bad=True)
        self.assertEqual(result['status'],'regenerated')
        handoff=calls[-1][1]['maintenance_handoff']
        self.assertEqual(handoff['status'],'rejected_unpublished_proposals')
        self.assertEqual(len(handoff['attempts']),2)
        for attempt in handoff['attempts']:
            self.assertGreater(len(attempt['validation_details']['issues']),1)
            self.assertIn('update',attempt['rejected_response'])
            self.assertEqual(attempt['rejected_response']['decision'],'update')
        self.assertEqual([kind for kind,_ in calls],['triage','triage_repair','report'])

    def test_pure_unjustified_edit_does_not_buy_sol(self):
        with self.assertRaisesRegex(RuntimeError,'change_justification_failed_no_sol'):
            self.run_pipeline(('quote_only','quote_only'))

    def test_correction_can_withdraw_without_redating(self):
        result,payload,calls=self.run_pipeline(('quote_only','retain'))
        self.assertEqual(result['status'],'retained')
        self.assertEqual(payload['generated_at'],v14.prior.data()['reference']['generated_at'])
        self.assertEqual([kind for kind,_ in calls],['triage','triage_repair'])

    def test_valid_update_and_itv(self):
        result,_,calls=self.run_pipeline()
        self.assertEqual(result['status'],'updated')
        self.assertEqual([kind for kind,_ in calls],['triage'])
        result,_,calls=self.run_pipeline((),due=True)
        self.assertEqual(result['status'],'regenerated')
        self.assertEqual([kind for kind,_ in calls],['report'])


if __name__ == '__main__': unittest.main()
