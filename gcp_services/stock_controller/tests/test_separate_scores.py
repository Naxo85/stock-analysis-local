from dataclasses import replace
import unittest

from test_analysis_score_persistence import payload
from test_global_sheet_sort import spreadsheet
from stock_analysis.analysis_worker.reports import parse_analysis_report
from stock_analysis.controller.analysis_sheet import _score_cell, _setup_cell
from stock_analysis.controller.sheet_layout import load_market_sheet_layout
from stock_analysis.controller.global_sheet_sort import build_global_sort_plan


class SeparateScoresTest(unittest.TestCase):
    def parse(self, data):
        return parse_analysis_report('AMD', data, report_url_template='https://reports.example/{ticker}')

    def test_old_score_is_never_displayed_as_thesis_or_setup(self):
        record = self.parse(payload('AMD', 4, 6))
        thesis = _score_cell(record, '#FFFFFF', thesis=True)
        self.assertEqual(thesis['userEnteredValue'], {'stringValue': 'Ver'})
        self.assertIn('histórico', thesis['note'])
        self.assertTrue(thesis['textFormatRuns'])
        self.assertEqual(_setup_cell(record, '#FFFFFF')['userEnteredValue'], {'stringValue': ''})

    def test_new_scores_and_reasons_remain_independent_without_migration_color(self):
        data = payload('AMD', 8.5, 4)
        data['decision'].update(score_basis='thesis', thesis_score=8.5, setup_score=3.5, thesis_reason='Contrato confirmado', setup_reason='Soporte sin confirmar')
        data['changes']['score_basis_changed'] = True
        record = self.parse(data)
        self.assertIsNone(record.score_background)
        self.assertEqual(_score_cell(record, '#FFFFFF', thesis=True)['userEnteredValue'], {'stringValue': '8,5'})
        self.assertEqual(_setup_cell(record, '#FFFFFF')['userEnteredValue'], {'stringValue': '3,5'})
        self.assertEqual(_setup_cell(record, '#FFFFFF')['note'], 'Soporte sin confirmar')
        data['decision']['setup_score'] = None
        with self.assertRaises(ValueError):
            self.parse(data)

    def test_setup_sort_keeps_thesis_notes_and_ticker_together(self):
        layout = load_market_sheet_layout()
        plan = build_global_sort_plan(layout, spreadsheet(layout, 'Setup'), sort_values={'setup_score': {'RKLB': 10}})
        self.assertEqual(plan.ticker_rows['RKLB'], 3)
        row = plan.requests[0]['updateCells']['rows'][0]['values']
        self.assertEqual(row[12]['note'], 'report:RKLB')
        self.assertEqual(len(row), 14)
