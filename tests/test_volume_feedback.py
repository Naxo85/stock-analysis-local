"""Offline replay of the 23-Oct failures; no model, acquisition or publication."""
from copy import deepcopy
import json
from pathlib import Path
import unittest

from src.local_runner.adaptive_context import model_context
from src.local_runner.adaptive_policy import validate_policy
from src.local_runner.adaptive_repair import repair_context
from src.local_runner.semantic_sources import normalize_plan, source_catalog
from src.local_runner.volume_arithmetic import validate
from src.local_runner.volume_feedback import MODE, instructions, selected_source_feedback

ROOT = Path(__file__).resolve().parents[1]
BATCH = ROOT / 'logs/batch/2026-10-23/14-18-22/adaptive'


def fixture(ticker, kind='triage'):
    context = model_context(json.loads((BATCH / ticker / 'input.json').read_text(encoding='utf-8')))
    response = json.loads((BATCH / ticker / (kind + '.json')).read_text(encoding='utf-8'))
    return context, response


class VolumeFeedbackTests(unittest.TestCase):
    def test_cls_initial_bad_reference_exposes_arithmetic_before_single_repair(self):
        context, response = fixture('CLS')
        original = deepcopy((context, response))
        result = selected_source_feedback(context, response)['entry']
        self.assertNotIn(result['declared_sources']['profile_source'], result['selected_profile_sources'])
        calculations = result['conditional_calculations']
        self.assertTrue(calculations)
        self.assertTrue(any(item['calculation']['expected'] == 10 for item in calculations))
        self.assertEqual((context, response), original)

    def test_cls_repair_eight_is_still_rejected_and_exact_ten_passes_arithmetic_only(self):
        context, response = fixture('CLS', 'triage_repair')
        plan, issues = normalize_plan({k: v for k, v in response['update']['plan'].items() if v is not None}, {}, context)
        self.assertFalse(issues)
        level = plan['entry']
        with self.assertRaisesRegex(ValueError, 'expected=10, received=8'):
            validate(level, 'entry', context, None)
        before = deepcopy(level)
        level['strength']['components']['volumen'] = 10
        validate(level, 'entry', context, None)
        self.assertEqual(level['volume_calculation_audit']['parts'],
                         dict(proximity=0, repetition=3, defense_rate=4, magnitude=3, recency=0))
        level.pop('volume_calculation_audit')
        level['strength']['components']['volumen'] = 8
        self.assertEqual(level, before)

    def test_gev_asml_general_profiles_remain_invalid_with_explicit_alternatives(self):
        for ticker in ('GEV', 'ASML'):
            with self.subTest(ticker=ticker):
                context, response = fixture(ticker, 'triage_repair')
                result = selected_source_feedback(context, response)['entry']
                self.assertTrue(result['selected_profile_sources'])
                self.assertNotIn(result['declared_sources']['profile_source'], result['selected_profile_sources'])
                plan, issues = normalize_plan({k: v for k, v in response['update']['plan'].items() if v is not None}, {}, context)
                self.assertFalse(issues)
                with self.assertRaisesRegex(ValueError, 'nonstructured_profile_source'):
                    validate(plan['entry'], 'entry', context, None)

    def test_no_selection_no_candidates_and_no_substitution(self):
        context, response = fixture('CLS')
        response['update']['plan']['entry']['evidence'] = []
        result = selected_source_feedback(context, response)['entry']
        self.assertEqual(result['selected_profile_sources'], {})
        self.assertEqual(result['conditional_calculations'], [])

    def test_unavailable_profile_is_not_a_candidate(self):
        context, response = fixture('CLS')
        for rows in context['slim']['levels'].values():
            if isinstance(rows, list):
                for row in rows:
                    if isinstance(row, dict) and (row.get('evidence') or {}).get('volume_profile'):
                        row['evidence']['volume_profile']['status'] = 'unavailable'
        # Rebind the synthetic selections to the mutated catalog explicitly.
        response['update']['plan']['entry']['evidence'] = [
            h for h, row in source_catalog(context).items() if row['pointer'].startswith('/slim/levels/')]
        self.assertEqual(selected_source_feedback(context, response)['entry']['selected_profile_sources'], {})

    def test_frozen_policy_and_full_instruction_prefixes_exact(self):
        for kind in ('triage', 'triage_repair', 'report'):
            self.assertEqual(instructions('prefix', {}, kind), 'prefix')
        self.assertEqual(instructions('prefix', {'volume_calculation_guidance': MODE}, 'report'), 'prefix')
        self.assertIn('nearest_level', instructions('prefix', {'volume_calculation_guidance': MODE}, 'triage'))

    def test_feedback_opt_in_and_mixed_error_collection(self):
        context, response = fixture('CLS')
        details = {'issues': [{'field': '/plan/entry', 'error':
                              'update_not_allowed_volume_arithmetic: entry: nonstructured_profile_source'}]}
        original = repair_context(context, response, 'update_not_allowed_other', validation_details=details)
        self.assertNotIn('volume_source_feedback', original['maintenance_repair'])
        enabled = repair_context(context, response, 'update_not_allowed_other', validation_details=details,
                                 policy={'volume_calculation_guidance': MODE})
        self.assertIn('entry', enabled['maintenance_repair']['volume_source_feedback'])
        enabled['maintenance_repair'].pop('volume_source_feedback')
        self.assertEqual(enabled, original)

    def test_invalid_direction_does_not_enter_conditional_calculations(self):
        context, response = fixture('CLS')
        # A resistance rejection cannot supply buying-support rebound arithmetic.
        handles = [h for h, row in source_catalog(context).items()
                   if row['pointer'].startswith('/slim/levels/resistances/')]
        response['update']['plan']['entry']['evidence'] = handles
        result = selected_source_feedback(context, response)['entry']
        self.assertEqual(result['selected_reaction_sources'], {})
        self.assertEqual(result['conditional_calculations'], [])

    def test_policy_mode_requires_explicit_supported_new_policy(self):
        policy = json.loads((ROOT / 'config/codex_analysis.json').read_text(encoding='utf-8'))
        policy['volume_calculation_guidance'] = MODE
        self.assertEqual(validate_policy(policy), policy)
        policy['routing_revision'] = 40
        with self.assertRaisesRegex(ValueError, 'requires41'):
            validate_policy(policy)
        policy['volume_calculation_guidance'] = 'unknown'
        with self.assertRaisesRegex(ValueError, 'unsupported_volume'):
            validate_policy(policy)


if __name__ == '__main__':
    unittest.main()
