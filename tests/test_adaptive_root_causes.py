"""Offline root-cause regressions; original production receipts remain read-only."""
from copy import deepcopy
from datetime import date
import hashlib
import importlib.util
import json
from pathlib import Path
import unittest

from src.common.analysis_validator import validate_markdown
from src.local_runner.adaptive_budget import read_json, write_json
from src.local_runner.adaptive_context import model_context, validation_context
from src.local_runner.adaptive_maintenance import (
    _claim_expiry, _locate_emphasis_equivalent_edit, _refresh_wall_facts,
    apply_update, maintenance_decision, maintenance_schema,
)
from src.local_runner.adaptive_repair import repair_context

ROOT = Path(__file__).resolve().parents[1]
BATCH = ROOT / 'logs/batch/2026-10-05/12-38-33/adaptive'
spec = importlib.util.spec_from_file_location('root_fixture', ROOT / 'tests/test_adaptive_maintenance_stage.py')
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)


class RootCauseTests(unittest.TestCase):
    def sources(self):
        wall = {'type': 'put_wall', 'level': 91, 'expiration': '2026-10-16',
                'oi': 16099, 'oi_share_pct': 3.5, 'gamma_share_pct': 21.6}
        slim = {'as_of': '2026-10-05T12:00:00Z', 'levels': {'put_walls_top': [wall]}}
        return {'slim': slim, 'reference': {'slim_snapshot': deepcopy(slim)}}

    def candidate(self, prose):
        return 'Entrada: $90-92\nFactores de Entrada: ' + prose + '\n'

    def test_option_quantities_are_not_strikes_but_remain_validated(self):
        for prose in ('put $91 del 16-Oct, gamma put 21.6%, OI 16,099 (3.5%)',
                      'put wall $91 del 16-10, 21.6% del gamma put y 16,099 contratos',
                      'put wall 16,099 contratos, 21.6% del gamma put al 16-10',
                      'put $91 del 16-Oct; gamma put 21.6%; OI 16,099 (3.5%); durabilidad 1/10',
                      'wall $91, gamma put 21.6% y OI 16,099 (3.5%), vencimiento 16-Oct'):
            text = self.candidate(prose)
            with self.subTest(prose=prose):
                self.assertEqual(_refresh_wall_facts('', text, self.sources()), (text, []))
                for old, wrong in (('21.6', '25.6'), ('16,099', '16,098')):
                    with self.assertRaisesRegex(ValueError, 'stale_or_unproven_wall_metric'):
                        _refresh_wall_facts('', text.replace(old, wrong), self.sources())
        with self.assertRaisesRegex(ValueError, 'stale_or_unproven_wall_metric'):
            _refresh_wall_facts('', self.candidate('put $91 del 16-Oct, OI 16,099 (9.5%)'), self.sources())

    def test_unpriced_wall_needs_unique_plan_zone_identity(self):
        data = self.sources()
        data['slim']['levels']['put_walls_top'].append({**deepcopy(data['slim']['levels']['put_walls_top'][0]), 'level': 92})
        for prose in ('put wall 16,099 contratos, gamma put 21.6%', 'put $999, OI 16,099'):
            with self.assertRaisesRegex(ValueError, 'ambiguous_current_wall_fact'):
                _refresh_wall_facts('', self.candidate(prose), data)

    def test_expiry_is_proven_not_ignored(self):
        records = [{'expiry': date(2026, 10, 16)}]
        for text in ('16-Oct', '16-10', '16/10/2026', '2026-10-16'):
            self.assertEqual(_claim_expiry(text, records), date(2026, 10, 16))
        for text in ('09-Oct', '09-10', '16/10/2027'):
            with self.assertRaisesRegex(ValueError, 'unproven_wall_expiry'):
                _claim_expiry(text, records)
        self.assertIsNone(_claim_expiry('durabilidad 1/10', records))
        with self.assertRaises(ValueError):
            _claim_expiry('16-Oct', records + [{'expiry': date(2027, 10, 16)}])

    def test_no_option_metrics_do_not_require_an_option_identity(self):
        text = self.candidate('wall $30 a 3.5 ATR; sin estructura independiente')
        self.assertEqual(_refresh_wall_facts('', text, self.sources()), (text, []))

    def test_elided_wall_side_keeps_separate_source_identities(self):
        data = self.sources()
        data['slim']['levels']['put_walls_top'].append({
            **deepcopy(data['slim']['levels']['put_walls_top'][0]), 'level': 92, 'oi': 500, 'gamma_share_pct': 8.1})
        text = self.candidate('put wall $91, 16,099 contratos, 21.6% del gamma; wall de $92 con 500 contratos y 8.1% del gamma')
        self.assertEqual(_refresh_wall_facts('', text, data), (text, []))
        with self.assertRaisesRegex(ValueError, 'stale_or_unproven_wall_metric'):
            _refresh_wall_facts('', text.replace('500 contratos', '600 contratos'), data)

    def test_history_does_not_exempt_false_current_metrics(self):
        text = self.candidate('put $91 del 16-Oct, OI 16,099 y gamma put 21.6% (el informe anterior registraba OI 200)')
        self.assertEqual(_refresh_wall_facts('', text, self.sources()), (text, []))
        with self.assertRaisesRegex(ValueError, 'stale_or_unproven_wall_metric'):
            _refresh_wall_facts('', text.replace('16,099', '1'), self.sources())

    def test_bold_identity_is_not_fuzzy_application(self):
        text = 'Factores de Entrada: dato **1+2=3**.\n'
        self.assertEqual(_locate_emphasis_equivalent_edit(text, '**Factores de Entrada: dato 1+2=3.**'), (0, len(text)-1))
        for before in ('Factores de Entrada: dato 1+2=4.', 'Factores de Entrada: dato 1+2=3;',
                       'Factores de Entrada: otro 1+2=3.', 'dato 1+2=3.', '## Plan:',
                       'Factores de Entrada: dato 1+2=3.\nOtra línea'):
            self.assertIsNone(_locate_emphasis_equivalent_edit(text, before))
        self.assertIsNone(_locate_emphasis_equivalent_edit(text+text, '**Factores de Entrada: dato 1+2=3.**'))

    def test_bold_matching_keeps_protected_fields_and_hash_checks(self):
        data = base.context()
        data['routing_revision'] = 4
        value = base.update_payload(data)
        value['edits'].append(base.FIXTURE.edit('**Tesis: 8 / 10**', 'Tesis: 7 / 10'))
        with self.assertRaisesRegex(ValueError, 'protected'):
            apply_update(value, data)
        value['base_markdown_sha256'] = 'bad'
        with self.assertRaisesRegex(ValueError, 'base_hash'):
            apply_update(value, data)

    def test_bad_before_feedback_identifies_the_edit_but_does_not_apply_it(self):
        data = base.context()
        data['routing_revision'] = 4
        value = base.update_payload(data)
        value['edits'].append(base.FIXTURE.edit('Setup: 6 / 11', 'Setup: 7 / 10'))
        with self.assertRaises(ValueError) as caught:
            apply_update(value, data)
        details = caught.exception.maintenance_details
        self.assertEqual(details['edit_index'], 1)
        self.assertIn('Setup: 6 / 10', details['nearest_source_lines'])
        self.assertEqual(repair_context(data, value, str(caught.exception), validation_details=details)['maintenance_repair']['validation_details'], details)

    def test_original_luna_outputs_pass_full_validation_without_source_mutation(self):
        for symbol in ('NBIS', 'GOOG', 'MRNA', 'CLS', 'INOD'):
            work = BATCH / symbol
            if not work.exists():
                self.skipTest('Production artifacts unavailable')
            for name in ('triage.response', 'triage_repair.response'):
                path = work / name
                if not path.exists():
                    continue
                protected = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in (path, work/'input.json')}
                data = model_context(read_json(work/'input.json'))
                value = json.loads(path.read_text(encoding='utf-8'))
                if value['decision'] != 'update':
                    continue
                checked = validate_markdown(apply_update(value, data), authoritative_context=validation_context(data),
                    require_support_strengths=True, require_resistance=True, require_separate_scores=True)
                self.assertTrue(checked.ok, (symbol, name, checked.errors))
                self.assertEqual(protected, {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in protected})

    def test_tsla_old_wall_remains_rejected_with_actionable_source_feedback(self):
        work = BATCH / 'TSLA'
        if not work.exists():
            self.skipTest('Production artifacts unavailable')
        data = model_context(read_json(work/'input.json'))
        with self.assertRaises(ValueError) as caught:
            apply_update(read_json(work/'triage.response'), data)
        details = caught.exception.maintenance_details
        self.assertIn(350, details['strikes'])
        self.assertTrue(details['current_sources'])
        self.assertTrue(details['historical_sources'])
        self.assertTrue(all(x['strike'] != 350 for x in details['current_sources']))

    def verdict(self, gap, decision='blocked'):
        data = base.context()
        data['routing_revision'] = 5
        value = base.update_payload(data)
        value.update(decision=decision, edits=[], routine_note='', evidence_gap=gap)
        return data, value

    def test_research_routes_to_sol_essential_data_blocks(self):
        for decision in ('blocked', 'retain', 'escalate'):
            data, value = self.verdict('research', decision)
            self.assertEqual(maintenance_decision(value, [], data), 'escalate')
            value['evidence_gap'] = 'essential_data'
            self.assertEqual(maintenance_decision(value, [], data), 'blocked')
        data, value = self.verdict('none', 'retain')
        self.assertEqual(maintenance_decision(value, [], data), 'retain')
        value['decision'] = 'blocked'
        with self.assertRaisesRegex(ValueError, 'blocked_without_data_gap'):
            maintenance_decision(value, [], data)

    def test_shared_schema_and_legacy_blocked_contract(self):
        data, value = self.verdict('research')
        self.assertEqual(maintenance_schema(data), maintenance_schema({'routing_revision': 5}))
        self.assertIn('evidence_gap', maintenance_schema(data)['required'])
        for invalid in (None, True, [], 'unknown'):
            value['evidence_gap'] = invalid
            with self.assertRaises(ValueError):
                maintenance_decision(value, [], data)
        data['routing_revision'] = 4
        value.pop('evidence_gap')
        value['risk']['requires_research'] = True
        self.assertEqual(maintenance_decision(value, [], data), 'blocked')
        self.assertNotIn('evidence_gap', maintenance_schema(data)['properties'])

    def test_rddt_reason_needs_typed_research_classification_not_a_ticker_exception(self):
        work = BATCH / 'RDDT'
        if not work.exists():
            self.skipTest('Production artifacts unavailable')
        data = model_context(read_json(work/'input.json'))
        value = read_json(work/'triage.response')
        self.assertEqual(maintenance_decision(value, [], data), 'blocked')
        self.assertEqual(data['news']['status'], 'ok')
        self.assertFalse(data['news']['truncated'])
        data['routing_revision'] = 5
        value['evidence_gap'] = 'research'  # Offline fixture only; original receipt untouched.
        self.assertEqual(maintenance_decision(value, [], data), 'escalate')


class RoutingIntegrationTests(unittest.TestCase):
    def fixture(self, gap):
        case = base.MaintenanceStageTests(methodName='test_update_builds_full_bundle_luna_provenance_and_original_completion_time')
        case.setUp()
        self.addCleanup(case.doCleanups)
        case.data['routing_revision'] = 5
        case.write_input()
        write_json(case.work/'policy.json', {**base.POLICY, 'routing_revision': 5})
        value = base.update_payload(case.data)
        value.update(decision='blocked', evidence_gap=gap, edits=[], routine_note='')
        return case, value

    def test_research_creates_sol_bundle_essential_data_calls_no_report(self):
        case, value = self.fixture('research')
        result = case.run_analyze(value)
        self.assertEqual(result['status'], 'regenerated')
        self.assertEqual([kind for kind, _ in case.seen], ['triage', 'report'])
        case, value = self.fixture('essential_data')
        with self.assertRaisesRegex(RuntimeError, 'blocked_insufficient_evidence'):
            case.run_analyze(value)
        self.assertEqual([kind for kind, _ in case.seen], ['triage'])

    def test_preflight_source_failure_blocks_before_any_model(self):
        case, value = self.fixture('research')
        case.data['news']['truncated'] = True
        case.write_input()
        with self.assertRaises(RuntimeError):
            case.run_analyze(value)
        self.assertEqual(case.seen, [])


if __name__ == '__main__':
    unittest.main()
