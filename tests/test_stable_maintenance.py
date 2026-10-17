"""Revision12 offline: sparse maintenance and input-local source selection."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import unittest
from unittest.mock import patch

import test_semantic_report as prior
import test_semantic_contract_v3 as v3
from src.local_runner.adaptive_context import model_context, serialize_model_input
from src.local_runner.adaptive_maintenance import maintenance_schema
from src.local_runner.adaptive_policy import daily_decision
from src.local_runner.adaptive_repair import repair_context
from src.local_runner.semantic_report import reference_document, digest
from src.local_runner.semantic_sources import source_catalog, source_pointer

ROOT = Path(__file__).resolve().parents[1]

def context():
    data = prior.data(); data['routing_revision'] = 12
    return model_context(data)

def candidate(data):
    value = v3.candidate(data); value['routine_note'] = ''
    value['update'] = {'setup_score': None, 'setup_reason': None,
        'plan': {key: None for key in prior.EDITABLE}, 'conclusion': None}
    return value

def block(data, zone):
    value = prior.level(zone); value.pop('transition')
    key = next(k for k,r in source_catalog(data).items() if r['pointer'] == '/slim/levels/supports/1')
    value['evidence'] = [key]; value['facts'] = [key]
    return value

class StableMaintenanceTests(unittest.TestCase):
    def test_short_keys_exact_frozen_and_not_model_catalog_authority(self):
        data = context(); cat = source_catalog(data)
        self.assertTrue(all(k.startswith('s') and k[1:].isdigit() for k in cat))
        key = next(k for k,r in cat.items() if r['pointer'] == '/slim/levels/supports/0')
        data['source_catalog'][key]['pointer'] = '/slim/levels/supports/1'
        self.assertEqual(source_pointer(key, source_catalog(data), revision=12), '/slim/levels/supports/0')
        data['slim']['levels']['supports'].reverse()
        self.assertEqual(source_catalog(data)[key]['value'], cat[key]['value'])

    def test_stable_normal_schema_and_constrained_repair(self):
        data = context(); schema = maintenance_schema(data)
        self.assertEqual(schema, maintenance_schema({'routing_revision': 12, 'symbol':'OTHER'}))
        feedback = repair_context(data, candidate(data), 'update_not_allowed_unknown_source_handle: s999')
        strict = maintenance_schema(feedback)
        level = strict['properties']['update']['anyOf'][0]['properties']['plan']['properties']['entry']['anyOf'][0]
        self.assertEqual(level['properties']['facts']['items']['enum'], list(source_catalog(data)))
        self.assertNotIn('s999', level['properties']['facts']['items']['enum'])
        self.assertEqual(serialize_model_input(data), serialize_model_input(model_context(data)))

    def test_state_change_preserves_all_financial_judgments(self):
        data = context(); original = deepcopy(data); value = candidate(data)
        value['update']['conclusion'] = 'El mid ha entrado; esperar defensa.'
        old = reference_document(data['reference']); doc = v3.document(data, value)
        self.assertEqual(doc['summary'], old['summary'])
        self.assertEqual(doc['conclusion'], value['update']['conclusion'])
        for key in old['plan']:
            for field in ('range','reason','strength'):
                self.assertEqual(doc['plan'][key][field], old['plan'][key][field])
        self.assertEqual(data, original)
        self.assertTrue(prior.validation_result(doc).ok)

    def test_news_only_does_not_force_plan_or_setup_rewrite(self):
        data = context(); value = candidate(data)
        value['routine_note'] = 'Aclaración necesaria de una fecha verificada.'
        doc = v3.document(data,value); old = reference_document(data['reference'])
        self.assertEqual(doc['summary'], old['summary'])
        self.assertEqual(doc['conclusion'], old['conclusion'])
        self.assertEqual(doc['routine_note'], value['routine_note'])

    def test_inherited_audit_not_relabelled_as_live(self):
        data = context(); old = reference_document(data['reference'])
        old['plan']['entry']['resolved_facts'] = [{'pointer':'/slim/latest_price',
            'value':91, 'historical':False, 'as_of':'2026-10-02T10:00:00Z'}]
        md = data['reference']['analysis_markdown']
        data['reference']['semantic_report'] = {'version':1,'data':old,'data_sha256':digest(old),
            'markdown_sha256':hashlib.sha256(md.encode()).hexdigest()}
        value = candidate(data); value['update']['conclusion'] = 'Esperar.'
        fact = v3.document(data,value)['plan']['entry']['resolved_facts'][0]
        self.assertTrue(fact['historical'])
        self.assertEqual(fact['value'],91)
        self.assertEqual(fact['as_of'],'2026-10-02T10:00:00Z')
        self.assertEqual(fact['retained_from_report']['markdown_sha256'],hashlib.sha256(md.encode()).hexdigest())

    def test_one_changed_block_keeps_other_levels_and_scores(self):
        data = context(); value = candidate(data); old = reference_document(data['reference'])
        value['update']['plan']['entry'] = block(data,{'lower':80,'upper':82})
        doc = v3.document(data,value)
        self.assertEqual(doc['plan']['entry']['range'],{'lower':80,'upper':82})
        self.assertEqual(doc['summary'],old['summary'])
        for key in ('ambitious_entry','resistance','target'):
            for field in ('range','reason','strength'):
                self.assertEqual(doc['plan'][key][field],old['plan'][key][field])

    def test_empty_proposal_retains_but_never_overrides_real_risk(self):
        data = context(); value = candidate(data)
        self.assertEqual(daily_decision(value,[],data),'retain')
        value['risk']['critical_catalyst'] = True
        self.assertEqual(daily_decision(value,[],data),'escalate')

    def test_bad_setup_or_unproven_zone_still_rejected(self):
        data = context(); value = candidate(data); value['update']['setup_score'] = 6
        with self.assertRaisesRegex(ValueError,'missing_reason'): v3.document(data,value)
        value = candidate(data); value['update']['plan']['entry'] = block(data,{'lower':93,'upper':94})
        with self.assertRaisesRegex(ValueError,'unproven_current_level_origin'): v3.document(data,value)

    def test_prior_contract_unchanged(self):
        data = v3.context()
        self.assertTrue(all('_' in k for k in source_catalog(data)))
        self.assertNotEqual(maintenance_schema(data),maintenance_schema(context()))
        self.assertEqual(v3.document(data,v3.candidate(data))['plan']['entry']['range'],{'lower':90,'upper':92})

    def test_source_only_failure_not_disguised_as_full_sol_research(self):
        from src.local_runner.semantic_sources import raise_issues, source_selection_only
        try:
            raise_issues([{'field':'/plan/entry/facts','source':'s999',
                'error':'update_not_allowed_source_reference: update_not_allowed_unknown_source_handle: s999'}])
        except ValueError as error:
            self.assertTrue(source_selection_only(error))
            with patch('src.local_runner.semantic_report.maintenance_document',side_effect=error), \
                 patch.object(prior,'full',side_effect=AssertionError('NO SOL FOR SOURCE TRANSCRIPTION')):
                with self.assertRaisesRegex(RuntimeError,'maintenance_source_selection_failed_no_sol'):
                    prior.SemanticPipelineTests().run_case(revision=12)
            error.maintenance_details['issues'].append({'field':'/plan',
                'error':'update_not_allowed_target_below_entry'})
            self.assertFalse(source_selection_only(error))

    def test_prompt_stability_policy(self):
        prompt = (ROOT/'prompts/daily_maintenance_semantic_v4.md').read_text(encoding='utf-8')
        for rule in ('SPARSE OUTPUT','CURRENT reference','Do NOT update merely',
                     'No arbitrary percentage threshold','SOURCE SELECTION v4'):
            self.assertIn(rule,prompt)
        self.assertEqual((ROOT/'prompts/stock_analysis_semantic_v4.md').read_text(encoding='utf-8').strip(),
                         (ROOT/'prompts/stock_analysis_semantic_v3.md').read_text(encoding='utf-8').strip())

    def test_original_asml_new_contract_copy_without_editing_old_receipts(self):
        work = ROOT/'logs/batch/2026-10-07/10-28-09/adaptive/ASML'
        if not work.exists(): self.skipTest('Original ASML fixture not present')
        paths = [work/name for name in ('input.json','triage_repair.response','triage_repair.receipt.json','review.json')]
        originals = {path:path.read_bytes() for path in paths}
        old = json.loads(originals[paths[0]]); data = deepcopy(old); data['routing_revision'] = 12
        review = json.loads(originals[paths[3]])
        for key in ('guards','itv','review_flags'): data[key] = review[key]
        value = json.loads(originals[paths[1]]); original_value = deepcopy(value)
        legacy, catalog = source_catalog(old), source_catalog(data)
        for level in value['update']['plan'].values():
            for field in ('facts','evidence'):
                selected = []
                for token in level[field]:
                    # Explicit fixture translation, NEVER a production fuzzy resolver.
                    if token == '/source_catalog/current_resistances_7d7da527ca6c8c/value/level':
                        token = '/source_catalog/current_resistances_7d7da527ca6c8c2c/value/level'
                    pointer = source_pointer(token,legacy,revision=11)
                    matches = [(len(row['pointer']),key) for key,row in catalog.items()
                        if pointer == row['pointer'] or pointer.startswith(row['pointer']+'/')]
                    self.assertTrue(matches,pointer)
                    selected.append(max(matches)[1])
                level[field] = list(dict.fromkeys(selected))
        doc = v3.document(model_context(data),value)
        for key,level in original_value['update']['plan'].items():
            self.assertEqual(doc['plan'][key]['range'],level['range'])
            self.assertEqual(doc['plan'][key]['strength'],level['strength'])
        self.assertEqual(doc['summary']['setup_score'],original_value['update']['setup_score'])
        self.assertEqual({path:path.read_bytes() for path in paths},originals)

    def test_new_preparation_freezes_v4_without_changing_old_contracts(self):
        import test_semantic_sources as source_tests
        source_tests.SourceContractTests().check_preparation(12)

    def test_sparse_pipeline_repair_sol_itv_retention_and_integrity(self):
        original_verdict, original_full = prior.verdict, prior.full
        def verdict(data, decision='update'):
            value = original_verdict(data,decision)
            if decision == 'update':
                catalog = source_catalog(data)
                key = next(k for k,r in catalog.items() if r['pointer'] == '/slim/levels/supports/0')
                value['update']['plan']['entry']['evidence'] = [key]
                for name in ('ambitious_entry','resistance','target'): value['update']['plan'][name] = None
            return value
        def full(data):
            value = original_full(data); key = next(iter(source_catalog(data)))
            for item in value['plan'].values(): item['evidence'] = [key]
            return value
        fixture = prior.SemanticPipelineTests()
        with patch.object(prior,'verdict',side_effect=verdict), patch.object(prior,'full',side_effect=full):
            for options, kinds in (({},['triage']),({'initial_bad':True},['triage','triage_repair']),
                    ({'initial_bad':True,'repair_bad':True},['triage','triage_repair','report']),
                    ({'due':True},['report']),({'retain':True},['triage']),
                    ({'escalate':True},['triage','report'])):
                with self.subTest(options=options):
                    review,payload,calls = fixture.run_case(revision=12,**options)
                    self.assertEqual([kind for kind,_ in calls],kinds)
                    self.assertEqual(review['last_full_report_at'],
                        prior.base.COMPLETED.isoformat() if review['status']=='regenerated'
                        else prior.data()['sol_reference']['generated_at'])
            fixture.run_case(revision=12,corrupt=True)
