from datetime import datetime, timezone, date
import unittest

from test_report_schema import _report
from src.common.analysis_validator import validate_markdown, extract_score
from src.local_runner.report_schema import build_structured_report
from src.local_runner.analysis_policy import parse_reference_summary, route_ticker, TickerRecord
from src.local_runner.run_one import _replace_report_score


def report(thesis=8.5, setup=3.5):
    return _report().replace('Valoración: 7.0 / 10', f'Tesis: {thesis} / 10\nMotivo de Tesis: Contrato confirmado; ejecución sólida.\nSetup: {setup} / 10\nMotivo de Setup: Sector débil; falta confirmar soporte.')


class SeparateScoreTests(unittest.TestCase):
    def test_high_thesis_low_setup_validate_and_parse_independently(self):
        md = report()
        self.assertTrue(validate_markdown(md, require_separate_scores=True).ok)
        parsed = build_structured_report(markdown=md, generated_at=datetime.now(timezone.utc), latest_price=76)
        self.assertEqual(parsed['decision']['thesis_score'], 8.5)
        self.assertEqual(parsed['decision']['setup_score'], 3.5)
        self.assertEqual(parsed['decision']['score_basis'], 'thesis')

    def test_legacy_remains_readable_but_cannot_be_new_output(self):
        self.assertTrue(validate_markdown(_report()).ok)
        self.assertFalse(validate_markdown(_report(), require_separate_scores=True).ok)
        self.assertEqual(extract_score(_report()), 7.0)

    def test_missing_out_of_range_or_unexplained_dimension_fails(self):
        for md in [report(setup=11), report().replace('Setup: 3.5 / 10', ''), report().replace('Motivo de Tesis: Contrato confirmado; ejecución sólida.', '')]:
            with self.subTest(md=md[:100]):
                self.assertFalse(validate_markdown(md, require_separate_scores=True).ok)

    def test_migration_does_not_raise_false_thesis_change(self):
        parsed = build_structured_report(markdown=report(), previous_markdown=_report(score=4), generated_at=datetime.now(timezone.utc), latest_price=76)
        self.assertTrue(parsed['changes']['score_basis_changed'])
        self.assertIsNone(parsed['changes']['score_delta'])
        self.assertFalse(any(a['type'] == 'score_change' for a in parsed['alerts']))

    def test_setup_change_does_not_change_thesis_and_score_lock_leaves_setup(self):
        parsed = build_structured_report(markdown=report(setup=8), previous_markdown=report(), generated_at=datetime.now(timezone.utc), latest_price=76)
        self.assertEqual(parsed['changes']['score_delta'], 0)
        self.assertEqual(parsed['changes']['setup_delta'], 4.5)
        locked = _replace_report_score(report(), 8.0)
        self.assertIn('Tesis: 8.0 / 10', locked)
        self.assertIn('Setup: 3.5 / 10', locked)

    def test_legacy_reference_forces_new_reference_even_in_daily_mode(self):
        reference = parse_reference_summary({'analysis_status': 'ok', 'generated_at': '2026-09-27T12:00:00Z', 'decision': {'score': 7}})
        route = route_ticker(TickerRecord('AMD'), reference, on_date=date(2026, 9, 28), requested_mode='daily')
        self.assertEqual(route.analysis_kind, 'reference')


if __name__ == '__main__':
    unittest.main()
