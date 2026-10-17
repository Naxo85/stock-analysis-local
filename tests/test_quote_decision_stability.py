"""Revision13: quote observations are not confirmations or plan decisions.

Offline only: original frozen artifacts are read, never changed. Mocked model
choices exercise plumbing, NOT a claim that a future model must choose retain.
"""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import unittest
from unittest.mock import patch

import test_semantic_report as prior
import test_semantic_contract_v3 as v3
import test_stable_maintenance as sparse
import test_semantic_sources as sources
from src.local_runner.adaptive_context import model_context, serialize_model_input, unpack_model_context
from src.local_runner.adaptive_delta import plan_quote_observations
from src.local_runner.adaptive_policy import daily_decision, maintenance_precheck
from src.local_runner.adaptive_maintenance import maintenance_schema
from src.local_runner.semantic_report import reference_document, report_schema
from src.local_runner.semantic_sources import source_catalog

ROOT = Path(__file__).resolve().parents[1]
BATCH = ROOT / 'logs/batch/2026-10-07/11-51-12/adaptive'


def context():
    value = prior.data()
    value['routing_revision'] = 13
    return model_context(value)


class QuoteDecisionTests(unittest.TestCase):
    def original(self, symbol, batch=BATCH):
        path = batch / symbol / 'input.json'
        if not path.exists():
            self.skipTest('Optional original production fixture absent')
        data = json.loads(path.read_text(encoding='utf-8'))
        return path, data

    def test_gev_promotion_was_mid_above_but_spread_straddled_target(self):
        folder = ROOT / 'logs/batch/2026-10-07/10-28-09/adaptive'
        path, data = self.original('GEV', folder)
        original = path.read_bytes()
        data['routing_revision'] = 13
        view = model_context(data)
        observation = view['comparison']['plan_quote_observations']
        self.assertEqual(observation['current_quote']['reference_price'], 1021.375)
        self.assertEqual(observation['current_quote']['bid'], 1018.76)
        self.assertEqual(observation['current_quote']['ask'], 1023.99)
        target = observation['levels']['target']
        self.assertEqual(target['range'], {'lower': 1020, 'upper': 1020})
        self.assertEqual(target['current_quote'], {
            'reference_price_position': 'above', 'bid_position': 'below',
            'ask_position': 'above', 'bid_ask_overlaps_zone': True})
        self.assertTrue(observation['target_above_entries']['entry'])
        self.assertIn('No confirmed breakout', observation['meaning'])
        self.assertNotIn('decision', observation)
        self.assertEqual(path.read_bytes(), original)

    def test_five_quote_changes_do_not_change_any_numeric_plan(self):
        expected = {'AMAT': ('within', 'below'), 'TSM': ('above', 'below'),
                    'MRNA': ('within', 'below'), 'USAR': ('above', 'within'),
                    'INTC': ('above', 'above')}
        for symbol, positions in expected.items():
            with self.subTest(symbol=symbol):
                path, data = self.original(symbol)
                original = path.read_bytes()
                data['routing_revision'] = 13
                unchanged = deepcopy(data)
                view = model_context(data)
                observation = view['comparison']['plan_quote_observations']
                entry = observation['levels']['entry']
                self.assertEqual((entry['previous_quote']['reference_price_position'],
                                  entry['current_quote']['reference_price_position']), positions)
                self.assertEqual(data, unchanged)
                old = reference_document(data['reference'])
                for name, level in observation['levels'].items():
                    self.assertEqual(level['range'], old['plan'][name]['range'])
                value = sparse.candidate(view)
                value.update(decision='retain', update=None)
                value['routine_note'] = 'Observación de cotización, no cambio de decisión.'
                self.assertEqual(daily_decision(value, [], view), 'retain')
                self.assertEqual(path.read_bytes(), original)

    def test_intc_hypothetical_stop_is_not_position_execution(self):
        _, data = self.original('INTC')
        data['routing_revision'] = 13
        observation = model_context(data)['comparison']['plan_quote_observations']
        stop = observation['levels']['management_stop']
        self.assertFalse(observation['owned'])
        self.assertFalse(stop['protects_recorded_position'])
        self.assertEqual(stop['previous_quote']['reference_price_position'], 'above')
        self.assertEqual(stop['current_quote']['reference_price_position'], 'below')
        self.assertFalse(stop['current_quote']['bid_ask_overlaps_zone'])
        check = maintenance_precheck(data['reference'], data['slim'], data['sol_reference'], owned=False)
        self.assertNotIn('price_below_management_stop', check['guards'])
        owned = maintenance_precheck(data['reference'], data['slim'], data['sol_reference'], owned=True)
        self.assertIn('price_below_management_stop', owned['guards'])

    def test_price_above_target_still_allows_a_lower_entry_plan(self):
        value = context()
        value['slim']['latest_price'] = 120
        value['slim']['market_state'] = {'bid': 119, 'ask': 121}
        observations = plan_quote_observations(value)
        self.assertEqual(observations['levels']['target']['current_quote']['reference_price_position'], 'above')
        self.assertTrue(all(observations['target_above_entries'].values()))
        payload = sparse.candidate(value)
        payload.update(decision='retain', update=None)
        self.assertEqual(daily_decision(payload, [], value), 'retain')
        self.assertEqual(daily_decision(payload, ['hard_guard'], value), 'escalate')

    def test_invalid_or_missing_quote_never_manufactures_confirmation(self):
        for quote in ({}, {'bid': 2, 'ask': 1}, {'bid': True, 'ask': 100},
                      {'bid': -1, 'ask': 100}, {'bid': None, 'ask': 100}):
            with self.subTest(quote=quote):
                value = context()
                value['slim']['market_state'] = quote
                result = plan_quote_observations(value)
                self.assertFalse(result['current_quote']['valid_bid_ask'])
                for level in result['levels'].values():
                    self.assertIsNone(level['current_quote']['bid_ask_overlaps_zone'])
                    self.assertIsNone(level['current_quote']['bid_position'])
                self.assertNotIn('confirmed_breakout', result)

    def test_two_endpoint_quotes_do_not_establish_traded_path(self):
        value = context()
        value['reference']['slim_snapshot'] = {
            'latest_price': 91, 'market_state': {'bid': 90.5, 'ask': 91.5}}
        value['slim']['latest_price'] = 89
        value['slim']['market_state'] = {'bid': 88.5, 'ask': 89.5}
        observation = plan_quote_observations(value)
        entry = observation['levels']['entry']
        self.assertEqual(entry['previous_quote']['reference_price_position'], 'within')
        self.assertEqual(entry['current_quote']['reference_price_position'], 'below')
        self.assertIn('not the intraperiod traded path', observation['meaning'])
        self.assertNotIn('broken', entry)
        self.assertNotIn('filled', entry)

    def test_unknown_ownership_is_not_assumed_false(self):
        value = context()
        value.pop('owned')
        result = plan_quote_observations(value)
        self.assertIsNone(result['owned'])
        self.assertIsNone(result['levels']['management_stop']['protects_recorded_position'])

    def test_news_only_important_correction_stays_allowed(self):
        _, value = self.original('USAR')
        original = deepcopy(value)
        value['routing_revision'] = 13
        view = model_context(value)
        response = json.loads((BATCH / 'USAR/triage.json').read_text(encoding='utf-8'))
        # Human-defined counterfactual COPY: retain only the important filing
        # clarification; no claim of an actual model13 response or valid old receipt.
        response['update']['conclusion'] = None
        response['routine_note'] = (
            'El Form 4 reporta venta de 88.391 acciones para cubrir impuestos de RSU; '
            '130.939 es la tenencia posterior, no una compra discrecional.')
        self.assertEqual(daily_decision(response, [], view), 'update')
        doc = v3.document(view, response)
        before = reference_document(value['reference'])
        self.assertEqual(doc['summary'], before['summary'])
        self.assertEqual(doc['conclusion'], before['conclusion'])
        for key, level in before['plan'].items():
            for field in ('range', 'strength', 'reason'):
                self.assertEqual(doc['plan'][key][field], level[field])
        self.assertEqual(value['reference'], original['reference'])

    def test_materiality_is_not_a_keyword_or_price_gate(self):
        value = context()
        payload = sparse.candidate(value)
        payload['update']['conclusion'] = 'Decisión distinta con respaldo; esperar condición nueva.'
        self.assertEqual(daily_decision(payload, [], value), 'update')
        for flag in payload['risk']:
            risk = deepcopy(payload)
            risk['risk'][flag] = True
            self.assertEqual(daily_decision(risk, [], value), 'escalate')
        payload['evidence_gap'] = 'essential_data'
        self.assertEqual(daily_decision(payload, [], value), 'blocked')

    def test_lossless_idempotent_context_and_old_schema_unchanged(self):
        value = context()
        self.assertEqual(value, model_context(value))
        self.assertEqual(unpack_model_context(json.loads(serialize_model_input(value))), value)
        self.assertEqual(maintenance_schema(value), maintenance_schema({'routing_revision': 12}))
        self.assertEqual(report_schema(13), report_schema(12))
        for revision in (9, 10, 11, 12):
            old = prior.data()
            old['routing_revision'] = revision
            self.assertNotIn('plan_quote_observations', model_context(old)['comparison'])

    def test_original_revision12_receipts_still_reconstruct_exact_input(self):
        for symbol in ('GEV', 'AMAT', 'INTC', 'TSM', 'MRNA', 'USAR'):
            with self.subTest(symbol=symbol):
                path, value = self.original(symbol)
                work = path.parent
                review = json.loads((work / 'review.json').read_text(encoding='utf-8'))
                for key in ('guards', 'itv', 'review_flags'):
                    value[key] = review[key]
                view = model_context(value)
                view.pop('research_memory', None)
                receipt = json.loads((work / 'triage.receipt.json').read_text(encoding='utf-8'))
                self.assertEqual(hashlib.sha256(serialize_model_input(view).encode()).hexdigest(),
                                 receipt['input_sha256'])
                self.assertNotIn('plan_quote_observations', view['comparison'])

    def test_new_preparation_freezes_both_v5_prompts(self):
        sources.SourceContractTests().check_preparation(13)

    def test_first_full_report_without_reference_needs_no_invented_geometry(self):
        raw = prior.data()
        raw.update(routing_revision=13, reference={}, sol_reference={})
        view = model_context(raw)
        observation = view['comparison']['plan_quote_observations']
        self.assertEqual(observation['levels'], {})
        self.assertEqual(observation['target_above_entries'], {})
        self.assertEqual(unpack_model_context(json.loads(serialize_model_input(view))), view)

    def test_all_46_original_inputs_keep_lossless_authority_in_revision13(self):
        paths = sorted(BATCH.glob('*/input.json'))
        if not paths:
            self.skipTest('Optional original production fixture absent')
        self.assertEqual(len(paths), 46)
        for path in paths:
            with self.subTest(symbol=path.parent.name):
                original = path.read_bytes()
                raw = json.loads(original)
                old = model_context(raw)
                raw['routing_revision'] = 13
                untouched = deepcopy(raw)
                current = model_context(raw)
                self.assertEqual(raw, untouched)
                self.assertEqual(source_catalog(current), source_catalog(old))
                for key in ('reference', 'sol_reference'):
                    self.assertEqual(current[key]['semantic_data'], old[key]['semantic_data'])
                self.assertEqual(unpack_model_context(json.loads(serialize_model_input(current))), current)
                self.assertEqual(path.read_bytes(), original)

    def test_prompts_remove_conflicting_target_and_refresh_directions(self):
        daily = (ROOT / 'prompts/daily_maintenance_semantic_v5.md').read_text(encoding='utf-8')
        full = (ROOT / 'prompts/stock_analysis_semantic_v5.md').read_text(encoding='utf-8')
        self.assertIn('QUOTE OBSERVATIONS ARE NOT PLAN TRANSITIONS', daily)
        self.assertIn('FROM THE PLANNED ENTRY', daily)
        self.assertIn('if the price/position sentence', daily)
        self.assertNotIn('- Refresh reference price, all level percentages', daily)
        self.assertNotIn('a tiny move crossing an actionable entry/exit\ncan matter', daily)
        self.assertIn('Con owned=false no hay una posición registrada', full)
        self.assertIn('Separación de observación, confirmación y decisión', full)
        self.assertNotIn('Si el precio ya ha superado por completo una zona, esa zona deja de ser candidata', full)
        # The financial strength rubric is unchanged, not weakened for stability.
        old = (ROOT / 'prompts/stock_analysis_semantic_v4.md').read_text(encoding='utf-8')
        start, end = 'Fortaleza obligatoria de los soportes', 'Resistencia estructural principal'
        self.assertEqual(full[full.index(start):full.index(end)], old[old.index(start):old.index(end)])


class QuotePipelineTests(unittest.TestCase):
    def test_retain_original_snapshot_no_extra_call_or_itv_reset(self):
        review, payload, calls = prior.SemanticPipelineTests().run_case(
            revision=13, retain=True, routing_note='Cotización distinta, decisión igual.')
        self.assertEqual([kind for kind, _ in calls], ['triage'])
        self.assertEqual(review['status'], 'retained')
        self.assertEqual(payload['analysis_markdown'], prior.data()['reference']['analysis_markdown'])
        self.assertEqual(payload['generated_at'], prior.data()['reference']['generated_at'])
        self.assertEqual(review['last_full_report_at'], prior.data()['sol_reference']['generated_at'])

    def test_sparse_repair_material_escalation_itv_and_integrity_still_work(self):
        original_verdict, original_full = prior.verdict, prior.full
        def verdict(data, decision='update'):
            result = original_verdict(data, decision)
            if decision == 'update':
                key = next(k for k, row in source_catalog(data).items()
                           if row['pointer'] == '/slim/levels/supports/0')
                result['update']['plan']['entry']['evidence'] = [key]
                for name in ('ambitious_entry', 'resistance', 'target'):
                    result['update']['plan'][name] = None
            return result
        def full(data):
            result = original_full(data)
            key = next(iter(source_catalog(data)))
            for level in result['plan'].values():
                level['evidence'] = [key]
            return result
        fixture = prior.SemanticPipelineTests()
        with patch.object(prior, 'verdict', side_effect=verdict), patch.object(prior, 'full', side_effect=full):
            for options, kinds in (({}, ['triage']),
                    ({'initial_bad': True}, ['triage', 'triage_repair']),
                    ({'initial_bad': True, 'repair_bad': True}, ['triage', 'triage_repair', 'report']),
                    ({'escalate': True}, ['triage', 'report']), ({'due': True}, ['report'])):
                with self.subTest(options=options):
                    review, payload, calls = fixture.run_case(revision=13, **options)
                    self.assertEqual([kind for kind, _ in calls], kinds)
                    self.assertEqual(review['last_full_report_at'],
                        prior.base.COMPLETED.isoformat() if review['status'] == 'regenerated'
                        else prior.data()['sol_reference']['generated_at'])
            fixture.run_case(revision=13, corrupt=True)



class ConclusionProvenanceTests(unittest.TestCase):
    def news_update(self, raw):
        view = model_context(raw)
        response = sparse.candidate(view)
        response['routine_note'] = 'Aclaración importante verificada; decisión sin cambio.'
        return v3.document(view, response)

    def test_inherited_conclusion_is_dated_without_rewriting_or_prose_parsing(self):
        from src.local_runner.semantic_report import render_document
        value = prior.data()
        value['routing_revision'] = 13
        value['reference']['slim_snapshot'] = {
            'as_of': '2026-10-02T10:00:00Z', 'latest_price': 100}
        old = reference_document(value['reference'])
        doc = self.news_update(value)
        self.assertEqual(doc['conclusion'], old['conclusion'])
        provenance = doc['conclusion_provenance']
        self.assertEqual(provenance['snapshot_at'], '2026-10-02T10:00:00Z')
        self.assertEqual(provenance['reference_price'], 100)
        self.assertEqual(provenance['markdown_sha256'],
                         hashlib.sha256(value['reference']['analysis_markdown'].encode()).hexdigest())
        original = deepcopy(doc)
        rendered = render_document(doc)
        self.assertIn('Conclusión conservada · snapshot 2026-10-02T10:00:00Z', rendered)
        self.assertIn('Estado en el snapshot:', rendered)
        self.assertIn('no confirmación de ruptura ni ejecución', rendered)
        self.assertNotIn(provenance['markdown_sha256'], rendered)
        self.assertEqual(doc, original)

    def test_successive_updates_keep_original_conclusion_snapshot(self):
        from src.local_runner.semantic_report import render_document, publication_fields
        raw = prior.data()
        raw['routing_revision'] = 13
        first = self.news_update(raw)
        markdown = render_document(first)
        raw['reference'].update(publication_fields(first, markdown, raw['reference'], prior.base.COMPLETED))
        raw['reference'].update(analysis_markdown=markdown, generated_at=prior.base.COMPLETED.isoformat(),
                                slim_snapshot=deepcopy(raw['slim']))
        raw['slim']['latest_price'] = 99
        second = self.news_update(raw)
        self.assertEqual(second['conclusion_provenance'], first['conclusion_provenance'])
        self.assertEqual(second['conclusion'], first['conclusion'])
        self.assertEqual(second['metadata']['reference_price'], 99)

    def test_genuinely_revised_conclusion_gets_current_provenance(self):
        from src.local_runner.semantic_report import render_document, publication_fields
        raw = prior.data()
        raw['routing_revision'] = 13
        first = self.news_update(raw)
        markdown = render_document(first)
        raw['reference'].update(publication_fields(first, markdown, raw['reference'], prior.base.COMPLETED))
        raw['reference'].update(analysis_markdown=markdown)
        view = model_context(raw)
        response = sparse.candidate(view)
        response['update']['conclusion'] = 'Decisión revisada: esperar la condición respaldada.'
        updated = v3.document(view, response)
        self.assertNotIn('conclusion_provenance', updated)
        self.assertNotIn('Conclusión conservada · snapshot', render_document(updated))
        self.assertEqual(updated['conclusion'], response['update']['conclusion'])

    def test_revision12_render_and_contract_do_not_gain_new_labels(self):
        from src.local_runner.semantic_report import render_document
        value = prior.data()
        value['routing_revision'] = 12
        doc = self.news_update(value)
        self.assertNotIn('conclusion_provenance', doc)
        rendered = render_document(doc)
        self.assertIn('Estado actual:', rendered)
        self.assertNotIn('Estado en el snapshot:', rendered)
        self.assertNotIn('Conclusión conservada · snapshot', rendered)

if __name__ == '__main__':
    unittest.main()
