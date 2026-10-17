"""No models/network: typed finance -> Markdown/JSON, no prose validation."""
from contextlib import ExitStack
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import test_adaptive_maintenance_stage as base
from src.local_runner import adaptive_stage as stage
from src.local_runner.adaptive_budget import read_json, write_json
from src.local_runner.adaptive_context import model_context, serialize_model_input
from src.local_runner.adaptive_maintenance import maintenance_schema, maintenance_decision, apply_update
from src.local_runner.adaptive_repair import repair_context
from src.local_runner.semantic_report import (
    EDITABLE, LABELS, MAXIMA, check_schema, update_schema, report_schema, reference_document,
    maintenance_document, full_document, render_document, publication_fields, validation_result,
)


def data():
    value = base.context()
    value['routing_revision'] = 9
    value['slim']['levels'].update(supports=[{'level': 90}, {'level': 80}], resistances=[{'level': 110}])
    return value


def level(zone, *, scored=True):
    return {'range': zone, 'transition': 'keep', 'reason': 'Fundamento vigente, sin frase prefijada',
            'strength': {'components': {'estructura': 18, 'volumen': 12, 'opciones': 16, 'confluencia': 10, 'durabilidad': 10},
                         'factors': 'Estructura independiente. Riesgos conocidos, evidencia limitada'} if scored and zone else None,
            'evidence': ['/slim'], 'facts': []}


def verdict(context, decision='update'):
    old = reference_document(context['reference'])
    result = base.update_payload(context)
    del result['edits']
    result['evidence_gap'] = 'none'
    result['decision'] = decision
    result['update'] = {'setup_score': 6.5, 'setup_reason': 'Apoyo actual sin cambio de tesis',
                       'plan': {key: level(old['plan'][key]['range'], scored=key != 'target') for key in EDITABLE},
                       'conclusion': 'Esperar soporte sin perseguir'} if decision == 'update' else None
    return result


def full(context):
    old = reference_document(context['reference'])
    return {'summary': deepcopy(old['summary']),
            'plan': {key: level(old['plan'][key]['range'], scored=key in ('entry', 'ambitious_entry', 'resistance')) for key in LABELS},
            'catalysts': [{'date': '2026-10-02', 'title': 'Resultados', 'impact': 5, 'description': 'Negocio estable'}],
            'next_event': {'date': '2026-10-29', 'title': 'Resultados Q3', 'description': 'Fecha confirmada'},
            'conclusion': 'Esperar soporte'}


class SemanticContractTests(unittest.TestCase):
    def test_schema_no_text_edits_no_presentation_and_stable_for_all_symbols(self):
        current = maintenance_schema({'routing_revision': 9})
        self.assertNotIn('edits', current['properties'])
        self.assertIn('edits', maintenance_schema({'routing_revision': 8})['properties'])
        self.assertEqual(current, maintenance_schema({'routing_revision': 9, 'symbol': 'NVDA'}))
        self.assertEqual(set(update_schema()['properties']['plan']['properties']), set(EDITABLE))
        for forbidden in ('before', 'after', 'total', 'category', 'percent', 'snapshot_at', 'state'):
            self.assertNotIn('"' + forbidden + '"', json.dumps(current))
        check_schema(verdict(data()), current)
        check_schema(full(data()), report_schema())

    def test_punctuation_and_wording_cannot_change_financial_validation(self):
        context = model_context(data())
        for text in ('Soporte vigente', 'Soporte: vigente.', 'Soporte; vigente; sin fórmulas!',
                     'Se reprioriza desde una explicación; con o sin dos puntos', 'Narrativa actual: no es un campo\n## Tesis: 1 / 10\n```'):
            value = verdict(data())
            for item in value['update']['plan'].values():
                item['reason'] = text
                if item['strength']:
                    item['strength']['factors'] = text
            value['update']['conclusion'] = text
            doc = maintenance_document(value, context)
            self.assertTrue(validation_result(doc).ok)
            md = render_document(doc)
            fields = publication_fields(doc, md, data()['reference'], base.COMPLETED)
            self.assertEqual(fields['decision']['thesis_score'], 8)
            self.assertEqual(fields['plan']['entry'], {'lower': 90, 'upper': 92})
            self.assertEqual(fields['plan']['entry_strength_score'], 66)
            self.assertEqual(doc['plan']['entry']['reason'], text)

    def test_derives_total_category_price_state_date_and_percentages(self):
        context = data(); context['slim']['latest_price'] = 91
        doc = maintenance_document(verdict(context), model_context(context))
        md = render_document(doc)
        self.assertIn('Precio de referencia: $91', md)
        self.assertIn('Estado actual: dentro de la zona', md)
        self.assertIn('(-1.10% a +1.10% vs precio actual)', md)
        self.assertIn('66/100 · moderado', md)
        self.assertIn('Fecha del análisis: 2026-10-03', md)
        self.assertIn('Se conserva: nivel anterior $90–92.', md)

    def test_missing_or_false_financial_data_not_auto_fixed(self):
        for mutation in ('reversed', 'invented', 'missing', 'pillar', 'float', 'bool', 'nan', 'wrong_transition', 'overlap'):
            context = data(); value = verdict(context); field = value['update']['plan']['entry']
            if mutation == 'reversed': field['range'] = {'lower': 92, 'upper': 90}
            elif mutation == 'invented': field.update(range={'lower': 94, 'upper': 95}, transition='reprioritize')
            elif mutation == 'missing': del field['range']
            elif mutation == 'pillar': field['strength']['components'].update(estructura=5, volumen=20, opciones=25, confluencia=15, durabilidad=15)
            elif mutation == 'float': field['strength']['components']['volumen'] = 12.5
            elif mutation == 'bool': field['range']['lower'] = True
            elif mutation == 'nan': field['range']['lower'] = float('nan')
            elif mutation == 'wrong_transition': field['transition'] = 'new'
            elif mutation == 'overlap': field.update(range={'lower': 91, 'upper': 93}, transition='reprioritize')
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                maintenance_document(value, model_context(context))

    def test_correct_same_numbers_allowed_without_required_phrase(self):
        value = verdict(data()); value['update']['plan']['entry']['transition'] = 'correct'
        doc = maintenance_document(value, model_context(data()))
        self.assertEqual(doc['plan']['entry']['range'], {'lower': 90, 'upper': 92})
        self.assertIn('Se corrige: nivel anterior $90–92', render_document(doc))

    def test_sources_are_exact_scalar_data_not_regex_wall_prose(self):
        context = data()
        context['slim']['levels']['put_walls_top'] = [{'type': 'put_wall', 'level': 90,
            'expiration': '2026-10-16', 'oi': 12345, 'oi_share_pct': 11, 'gamma_share_pct': 19}]
        value = verdict(context)
        value['update']['plan']['entry']['facts'] = ['/slim/levels/put_walls_top/0/oi_share_pct']
        doc = maintenance_document(value, model_context(context))
        fact = doc['plan']['entry']['resolved_facts'][0]
        self.assertEqual(fact['value'], 11)
        self.assertEqual(fact['options_record']['oi'], 12345)
        self.assertEqual(fact['options_record']['expiration'], '2026-10-16')
        self.assertFalse(fact['historical'])
        context['slim']['levels']['put_walls_top'][0]['evidence'] = {'volume_profile': {'level': 90.1234}}
        nested = deepcopy(value)
        nested['update']['plan']['entry']['facts'] = ['/slim/levels/put_walls_top/0/evidence/volume_profile/level']
        nested_fact = maintenance_document(nested, model_context(context))['plan']['entry']['resolved_facts'][0]
        self.assertEqual(nested_fact['value'], 90.1234)
        self.assertEqual(nested_fact['options_record']['level'], 90)
        for source in ('/slim/levels/put_walls_top/0/imaginary', '/slim/levels/put_walls_top/0',
                       '/news/items/0/headline', '/slim/levels/put_walls_top/20/oi'):
            bad = deepcopy(value); bad['update']['plan']['entry']['facts'] = [source]
            with self.subTest(source=source), self.assertRaises(ValueError):
                maintenance_document(bad, model_context(context))
        context['slim']['levels']['put_walls_top'][0]['expiration'] = '2026-10-01'
        with self.assertRaisesRegex(ValueError, 'expired_or_inactive'):
            maintenance_document(value, model_context(context))

    def test_historical_option_facts_stay_dated_in_audit_not_public_plan(self):
        context = data(); context['reference']['slim_snapshot'] = {'as_of': '2026-10-02T10:00:00Z',
            'levels': {'put_walls_top': [{'type': 'put_wall', 'level': 90, 'expiration': '2026-10-01', 'oi': 10}]}}
        value = verdict(context)
        value['update']['plan']['entry']['facts'] = ['/reference/slim_snapshot/levels/put_walls_top/0/oi']
        doc = maintenance_document(value, model_context(context))
        self.assertTrue(doc['plan']['entry']['resolved_facts'][0]['historical'])
        self.assertEqual(doc['plan']['entry']['resolved_facts'][0]['as_of'], '2026-10-02T10:00:00Z')
        self.assertNotIn('/reference/slim_snapshot/', render_document(doc))

    def test_duplicate_wall_metrics_cannot_hide_source_conflict(self):
        context = data()
        row = {'type': 'put_wall', 'level': 90, 'expiration': '2026-10-16', 'oi': 120, 'oi_share_pct': 11}
        context['slim']['levels']['put_walls_top'] = [row]
        context['slim']['levels']['supports'].append({**row, 'oi': 121})
        value = verdict(context); value['update']['plan']['entry']['facts'] = ['/slim/levels/put_walls_top/0/oi']
        with self.assertRaisesRegex(ValueError, 'conflicting_wall_sources'):
            maintenance_document(value, model_context(context))

    def test_sources_and_legacy_46_ticker_baselines_are_readonly(self):
        root = Path(__file__).resolve().parents[1]
        paths = sorted((root / 'logs/batch/2026-10-06/09-24-30/adaptive').glob('*/input.json'))
        if not paths: self.skipTest('Optional real incident archive unavailable')
        self.assertEqual(len(paths), 46)
        for path in paths:
            original = path.read_bytes(); raw = json.loads(original)
            for key in ('reference', 'sol_reference'):
                doc = reference_document(raw[key])
                self.assertIsNotNone(doc['summary']['thesis_score'])
                for name in ('entry', 'management_stop', 'structural_stop', 'resistance', 'target'):
                    self.assertIsNotNone(doc['plan'][name]['range'])
            self.assertEqual(path.read_bytes(), original)

    def test_semantic_news_citations_still_require_completed_tool_result(self):
        from src.local_runner.adaptive_news_research import collect_news_research
        url = 'https://example.test/company/news'
        events = json.dumps({'type': 'item.completed', 'item': {'id': 'web-1', 'type': 'web_search',
            'results': [{'url': url, 'title': 'Company source', 'snippet': 'Discovery only'}]}}) + '\n'
        receipt = {'luna_news_events_sha256': hashlib.sha256(events.encode()).hexdigest(),
                   'web_search_count': 1, 'completed_at': base.COMPLETED.isoformat(), 'model': 'gpt-6-luna'}
        value = verdict(data()); value['update']['conclusion'] = 'Observación [' + url + '](' + url + ')'
        collected = collect_news_research(events, receipt, value)
        self.assertEqual([row['url'] for row in collected['sources']], [url])
        value['update']['conclusion'] += ' https://invented.test/article'
        self.assertEqual(collect_news_research(events, receipt, value)['sources'], collected['sources'])

    def test_readonly_audit_uses_financial_contract_not_prose_validator(self):
        from scripts.audit_adaptive_rejections import replay
        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory) / 'CAT'; work.mkdir()
            write_json(work / 'input.json', data())
            write_json(work / 'triage.response', verdict(data()))
            original = (work / 'triage.response').read_bytes()
            with patch('scripts.audit_adaptive_rejections.validate_markdown', side_effect=AssertionError('NO PROSE VALIDATOR')):
                result = replay(work, 'triage.response')
            self.assertTrue(result['ok'], result)
            self.assertEqual((work / 'triage.response').read_bytes(), original)

    def test_luna_cannot_edit_protected_fields_or_invent_urls(self):
        for key in ('thesis_score', 'narrative', 'management_stop', 'structural_stop', 'catalysts', 'next_event'):
            value = verdict(data()); value['update'][key] = 'override'
            with self.subTest(key=key), self.assertRaises(ValueError):
                maintenance_document(value, model_context(data()))
        bad = verdict(data()); bad['update']['conclusion'] += ' https://invented.test/news'
        with self.assertRaisesRegex(ValueError, 'unsupported_url'):
            maintenance_document(bad, model_context(data()))
        doc = maintenance_document(verdict(data()), model_context(data()))
        old = reference_document(data()['reference'])
        for key in ('management_stop', 'structural_stop'):
            self.assertEqual(doc['plan'][key], old['plan'][key])
        self.assertEqual(doc['fundamental_markdown'], old['fundamental_markdown'])
        self.assertEqual(doc['summary']['narrative'], old['summary']['narrative'])

    def test_hash_and_binding_failures_are_integrity_not_paid_repair(self):
        value = verdict(data()); value['base_markdown_sha256'] = 'wrong'
        with self.assertRaisesRegex(ValueError, 'base_hash'):
            maintenance_document(value, model_context(data()))
        doc = maintenance_document(verdict(data()), model_context(data()))
        md = render_document(doc)
        reference = {**data()['reference'], 'analysis_markdown': md,
                     **publication_fields(doc, md, data()['reference'], base.COMPLETED)}
        for mutation in ('markdown', 'data'):
            bad = deepcopy(reference)
            if mutation == 'markdown': bad['analysis_markdown'] += '.'
            else: bad['semantic_report']['data']['plan']['entry']['range']['lower'] += 1
            with self.subTest(mutation=mutation), self.assertRaisesRegex(ValueError, 'semantic_base_integrity'):
                reference_document(bad)

    def test_new_baseline_never_imports_prose_and_retains_precision(self):
        context = data(); value = verdict(context)
        value['update']['plan']['resistance'].update(range={'lower': 110, 'upper': 110.0032}, transition='correct')
        doc = maintenance_document(value, model_context(context)); md = render_document(doc)
        reference = {**context['reference'], 'analysis_markdown': md,
            **publication_fields(doc, md, context['reference'], base.COMPLETED)}
        context['reference'] = reference
        context['sol_reference'] = deepcopy(reference)
        with patch('src.local_runner.adaptive_maintenance._layout', side_effect=AssertionError('NO TEXT IMPORT')):
            projected = model_context(context)
            self.assertEqual(reference_document(reference)['plan']['resistance']['range']['upper'], 110.0032)
            self.assertEqual(projected['reference']['semantic_data']['plan']['resistance']['range']['upper'], 110.0032)
            self.assertIn('semantic_data', json.loads(serialize_model_input(projected))['reference'])

    def test_full_sol_uses_same_data_contract_and_derives_sorted_dates(self):
        value = full(data())
        value['catalysts'].append({'date': '2026-10-03', 'title': 'Otro evento', 'impact': -6, 'description': 'Riesgo verificado'})
        doc = full_document(value, model_context(data()))
        self.assertEqual(doc['catalysts'][0]['date'], '2026-10-03')
        fields = publication_fields(doc, render_document(doc), data()['reference'], base.COMPLETED)
        self.assertEqual(fields['catalysts'][0]['explanation'], 'Riesgo verificado')
        self.assertEqual(fields['next_event']['explanation'], 'Fecha confirmada')
        bad = deepcopy(value); bad['catalysts'][0]['date'] = 'tomorrow'
        with self.assertRaises(ValueError): full_document(bad, model_context(data()))

    def test_risk_itv_blocking_and_repair_instruction_not_cosmetic(self):
        context = model_context(data()); value = verdict(data())
        for flag in value['risk']:
            bad = deepcopy(value); bad['risk'][flag] = True
            self.assertEqual(maintenance_decision(bad, [], context), 'escalate')
        self.assertEqual(maintenance_decision(value, ['hard_guard'], context), 'escalate')
        value['evidence_gap'] = 'essential_data'
        self.assertEqual(maintenance_decision(value, [], context), 'blocked')
        feedback = repair_context(context, verdict(data()), 'update_not_allowed_unproven_current_level_origin')
        self.assertNotIn('patch_source_check', feedback['maintenance_repair'])
        self.assertIn('no hay comprobación de frases', feedback['maintenance_repair']['instruction'].lower())

    def test_routing_notes_are_not_report_edits_for_all_decisions(self):
        context = model_context(data())
        for decision in ('retain', 'escalate', 'blocked', 'update'):
            value = verdict(data(), decision)
            value['routine_note'] = 'Comentario informativo; no autoriza cambios al informe.'
            if decision == 'blocked':
                value['evidence_gap'] = 'essential_data'
            original = deepcopy(value)
            with self.subTest(decision=decision):
                self.assertEqual(maintenance_decision(value, [], context), decision)
                self.assertEqual(value, original)

    def test_routing_notes_never_bypass_financial_authority_or_evidence(self):
        context = model_context(data())
        value = verdict(data(), 'retain')
        value['routine_note'] = 'Se puede explicar una decisión sin modificar el informe.'
        for flag in value['risk']:
            bad = deepcopy(value); bad['risk'][flag] = True
            self.assertEqual(maintenance_decision(bad, [], context), 'escalate')
        self.assertEqual(maintenance_decision(value, ['hard_guard'], context), 'escalate')
        for gap, expected in (('research', 'escalate'), ('essential_data', 'blocked')):
            bad = deepcopy(value); bad['evidence_gap'] = gap
            self.assertEqual(maintenance_decision(bad, [], context), expected)
        bad = deepcopy(value); bad['uncertainty'] = True
        self.assertEqual(maintenance_decision(bad, [], context), 'escalate')
        for mutation in ('unexpected_update', 'missing_update', 'unknown_edits', 'blank_reason',
                         'blank_assessment', 'empty_evidence', 'invented_evidence', 'blocked_without_gap'):
            bad = deepcopy(value)
            if mutation == 'unexpected_update': bad['update'] = verdict(data())['update']
            elif mutation == 'missing_update': bad['decision'] = 'update'
            elif mutation == 'unknown_edits': bad['edits'] = []
            elif mutation == 'blank_reason': bad['reason'] = '  '
            elif mutation == 'blank_assessment': bad['thesis']['assessment'] = '  '
            elif mutation == 'empty_evidence': bad['thesis']['evidence'] = []
            elif mutation == 'invented_evidence': bad['thesis']['evidence'] = ['/invented']
            elif mutation == 'blocked_without_gap': bad['decision'] = 'blocked'
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                maintenance_decision(bad, [], context)

    def test_legacy_note_contract_is_not_reinterpreted(self):
        for revision in (3, 8):
            context = data(); context['routing_revision'] = revision
            value = base.update_payload(context)
            value.update(decision='retain', edits=[], routine_note='Nota del contrato antiguo')
            if revision >= 5: value['evidence_gap'] = 'none'
            with self.subTest(revision=revision), self.assertRaisesRegex(ValueError, 'edits_without_update'):
                maintenance_decision(value, [], context)

    def test_oct7_original_routing_receipts_accept_notes_without_any_artifact_edit(self):
        root = Path(__file__).resolve().parents[1]
        batch = root / 'logs/batch/2026-10-07/07-50-26/adaptive'
        if not batch.exists(): self.skipTest('Original production receipts not present in this checkout')
        for symbol, expected in (('MRVL', 'escalate'), ('NVDA', 'escalate'), ('MU', 'escalate'),
                                 ('QCOM', 'retain'), ('GOOG', 'escalate')):
            work = batch / symbol
            paths = [work / name for name in ('triage.response', 'input.json', 'policy.json', 'triage.receipt.json')]
            original = {path: path.read_bytes() for path in paths}
            value = json.loads(original[paths[0]])
            context = json.loads(original[paths[1]])
            context['routing_revision'] = json.loads(original[paths[2]])['routing_revision']
            with self.subTest(symbol=symbol):
                self.assertTrue(value['routine_note'].strip())
                self.assertIsNone(value['update'])
                self.assertEqual(maintenance_decision(value, [], model_context(context)), expected)
                self.assertEqual({path: path.read_bytes() for path in paths}, original)


class SemanticPipelineTests(unittest.TestCase):
    def test_transport_schema_prefix_models_and_legacy_are_versioned(self):
        root = Path(__file__).resolve().parents[1]
        prefixes = []
        with tempfile.TemporaryDirectory() as directory:
            for revision in (8, 9, 10, 11):
                for kind in ('triage', 'triage_repair', 'report'):
                    work = Path(directory) / (str(revision) + '-' + kind); work.mkdir()
                    (work / 'triage_instructions.md').write_text('stable daily prefix', encoding='utf-8')
                    (work / 'instructions.md').write_text('stable full prefix', encoding='utf-8')
                    context = data(); context['routing_revision'] = revision
                    policy = {**base.POLICY, 'routing_revision': revision}
                    with patch.object(stage, 'reserve', return_value='CAT:' + kind), patch.object(stage, 'finish'), \
                         patch.object(stage, 'load_triage', return_value=None), \
                         patch.object(stage, 'call_codex', side_effect=RuntimeError('OFFLINE TRANSPORT MOCK')) as call:
                        with self.assertRaisesRegex(RuntimeError, 'OFFLINE TRANSPORT MOCK'):
                            stage.model_call(root, work, 'CAT', Path(directory) / 'budget.json', policy, kind, context)
                    actual = call.call_args.kwargs
                    role = 'report' if kind == 'report' else 'triage'
                    self.assertEqual(actual['model'], policy[role + '_model'])
                    self.assertEqual(actual['effort'], policy[role + '_effort'])
                    if kind == 'report':
                        self.assertEqual(actual['schema'], report_schema(revision) if revision >= 9 else None)
                        self.assertIn('semantic report JSON' if revision >= 9 else 'Spanish markdown', actual['instructions'])
                    else:
                        self.assertIn('update' if revision >= 9 else 'edits', actual['schema']['required'])
                        if revision == 9: prefixes.append(actual['instructions'])
            self.assertEqual(prefixes[0], prefixes[1])

    def test_prepare_freezes_semantic_policies_without_legacy_format_contract(self):
        root = Path(__file__).resolve().parents[1]
        context = data()
        with tempfile.TemporaryDirectory() as directory, ExitStack() as stack:
            work = Path(directory) / 'CAT'; work.mkdir()
            stack.enter_context(patch.object(stage, 'datetime', base.FrozenClock))
            stack.enter_context(patch.object(stage, 'load_policy', return_value={**base.POLICY, 'routing_revision': 9}))
            stack.enter_context(patch.object(stage, 'load_reference_payload', return_value=context['sol_reference']))
            stack.enter_context(patch.object(stage, 'load_current_report', return_value=context['reference']))
            stack.enter_context(patch.object(stage, 'load_research', return_value=None))
            stack.enter_context(patch.object(stage.one, '_fetch_slim', return_value=context['slim']))
            stack.enter_context(patch.object(stage.one, '_load_analyst_quality', return_value={}))
            stack.enter_context(patch.object(stage.one, 'load_compact_analyst_summary', return_value={}))
            stack.enter_context(patch.object(stage.one, 'load_recent_analyst_actions', return_value=context['analyst_actions']))
            stack.enter_context(patch.object(stage.one, 'load_recent_news', return_value=context['news']))
            stack.enter_context(patch.object(stage.one, '_load_system_prompt', return_value='OBSOLETE MARKDOWN CONTRACT'))
            stack.enter_context(patch.object(stage, 'call_codex', side_effect=AssertionError('NO MODEL DURING PREPARE')))
            stage.prepare(root, work, 'CAT', False, 'tracking')
            daily = (work / 'triage_instructions.md').read_text(encoding='utf-8')
            full_prefix = (work / 'instructions.md').read_text(encoding='utf-8')
            self.assertIn('SEMANTIC OUTPUT CONTRACT', daily)
            self.assertNotIn('Patches: before', daily)
            self.assertNotIn('Usa estas fórmulas', daily)
            self.assertNotIn('OBSOLETE MARKDOWN CONTRACT', full_prefix)
            self.assertEqual(read_json(work / 'policy.json')['routing_revision'], 9)

    def run_case(self, *, initial_bad=False, repair_bad=False, due=False, retain=False, corrupt=False,
                 escalate=False, routing_note='', revision=9, expected_entry=(90, 92)):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); work = root / 'batch/adaptive/CAT'; work.mkdir(parents=True)
            context = data(); context['routing_revision'] = revision
            policy = {**base.POLICY, 'routing_revision': revision, 'luna_repair_version': 1}
            write_json(work / 'input.json', context); write_json(work / 'policy.json', policy)
            original = (work / 'input.json').read_bytes(); calls = []
            def call(root, work, symbol, budget, policy, kind, supplied, **kwargs):
                calls.append((kind, deepcopy(supplied)))
                result = full(context) if kind == 'report' else verdict(context, 'retain' if retain else 'escalate' if escalate else 'update')
                if kind != 'report' and routing_note: result['routine_note'] = routing_note
                if kind == 'triage' and corrupt: result['base_markdown_sha256'] = 'wrong'
                if (kind == 'triage' and initial_bad) or (kind == 'triage_repair' and repair_bad):
                    result['update']['plan']['entry'].update(range={'lower': 94, 'upper': 95}, transition='reprioritize')
                if revision >= 10:
                    plan = result.get('plan') if kind == 'report' else (result.get('update') or {}).get('plan', {})
                    for item in plan.values():
                        if item is not None: item.pop('transition', None)
                if revision >= 11: result.pop('base_markdown_sha256', None)
                text = json.dumps(result)
                (work / (kind + '.response')).write_text(text, encoding='utf-8')
                supplied_view = model_context(supplied)
                if kind != 'report': supplied_view.pop('research_memory', None)
                receipt_hash = hashlib.sha256(serialize_model_input(supplied_view).encode()).hexdigest()
                if revision >= 11 and corrupt: receipt_hash = 'wrong'
                return {'text': text, 'exit_code': 0, 'completed_at': base.COMPLETED.isoformat(),
                        'input_sha256': receipt_hash,
                        'model': policy['report_model' if kind == 'report' else 'triage_model'],
                        'usage': {'input_tokens': 100, 'output_tokens': 20}}
            with ExitStack() as stack:
                stack.enter_context(patch.object(stage, 'datetime', base.FrozenClock))
                stack.enter_context(patch.object(stage, 'maintenance_precheck', return_value={'guards': [], 'review_flags': []}))
                stack.enter_context(patch.object(stage, 'itv_state', return_value={'due': due, 'age_sessions': 1}))
                stack.enter_context(patch.object(stage, 'model_call', side_effect=call))
                stack.enter_context(patch.object(stage.one, 'validate_markdown', side_effect=AssertionError('NO PROSE VALIDATOR')))
                stack.enter_context(patch.object(stage.one, 'build_structured_report', side_effect=AssertionError('NO PROSE MIRROR')))
                stack.enter_context(patch.object(stage, 'save_research'))
                stack.enter_context(patch.object(stage, 'call_codex', side_effect=AssertionError('NO REAL MODEL')))
                if corrupt:
                    with self.assertRaisesRegex(ValueError, 'response_binding' if revision >= 11 else 'base_hash'):
                        stage.analyze(root, work, 'CAT', root / 'budget.json', False)
                    self.assertEqual([k for k, _ in calls], ['triage'])
                    return
                review = stage.analyze(root, work, 'CAT', root / 'budget.json', False)
                payload = read_json(work / 'publish/output/CAT/latest.json')
                self.assertEqual((work / 'input.json').read_bytes(), original)
                self.assertEqual(payload['analysis_status'], 'ok')
                if review['status'] != 'retained':
                    expected = None if expected_entry is None else dict(zip(('lower', 'upper'), expected_entry))
                    self.assertEqual(reference_document(payload)['plan']['entry']['range'], expected)
                with patch.object(stage, 'model_call', side_effect=AssertionError('NO RECOVERY CALL')):
                    self.assertEqual(stage.analyze(root, work, 'CAT', root / 'budget.json', False), review)
                return review, payload, calls

    def test_one_luna_no_cosmetic_validator_immutable_anchor(self):
        review, payload, calls = self.run_case()
        self.assertEqual([kind for kind, _ in calls], ['triage'])
        self.assertEqual(review['status'], 'updated')
        self.assertEqual(payload['last_full_report_at'], data()['sol_reference']['generated_at'])
        self.assertEqual(payload['plan']['entry_strength_score'], 66)
        self.assertEqual(payload['decision']['score'], 8)

    def test_one_directed_financial_repair_before_sol(self):
        review, payload, calls = self.run_case(initial_bad=True)
        self.assertEqual([kind for kind, _ in calls], ['triage', 'triage_repair'])
        self.assertEqual(review['status'], 'updated')
        self.assertIn('unproven_current_level_origin', calls[1][1]['maintenance_repair']['rejection'])

    def test_failed_financial_repair_requires_full_sol_not_hidden_failure(self):
        review, payload, calls = self.run_case(initial_bad=True, repair_bad=True)
        self.assertEqual([kind for kind, _ in calls], ['triage', 'triage_repair', 'report'])
        self.assertEqual(review['status'], 'regenerated')
        self.assertFalse(review['fallback_used'])

    def test_due_itv_no_luna_and_full_sol_same_contract(self):
        review, payload, calls = self.run_case(due=True)
        self.assertEqual([kind for kind, _ in calls], ['report'])
        self.assertEqual(review['status'], 'regenerated')

    def test_retain_no_refresh_and_no_full_model(self):
        review, payload, calls = self.run_case(retain=True, routing_note='Nota informativa, no edición')
        self.assertEqual(review['status'], 'retained')
        self.assertEqual(payload['analysis_markdown'], data()['reference']['analysis_markdown'])
        self.assertEqual(payload['generated_at'], data()['reference']['generated_at'])
        self.assertEqual([kind for kind, _ in calls], ['triage'])

    def test_escalation_note_reaches_sol_without_paid_luna_repair(self):
        review, payload, calls = self.run_case(escalate=True, routing_note='Motivo informativo para la revisión Sol')
        self.assertEqual(review['status'], 'regenerated')
        self.assertEqual([kind for kind, _ in calls], ['triage', 'report'])
        self.assertEqual(calls[-1][1]['triage']['routine_note'], 'Motivo informativo para la revisión Sol')
        self.assertFalse(review['fallback_used'])

    def test_integrity_failure_no_repair_or_sol(self):
        self.run_case(corrupt=True)


if __name__ == '__main__':
    unittest.main()
