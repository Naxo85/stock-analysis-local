"""Sheets normalizes a uniform linked run into textFormat.link on readback.

An updateCells mask that clears absent textFormatRuns also clears that link,
even when the same request contains textFormat.link. This boundary behavior was
reproduced on the live sheet; the captured before/write/after is kept in the audit.
"""
from copy import deepcopy
import unittest

from stock_analysis.controller.global_sheet_sort import _writable_cell


class NormalizedReportLinkSortTest(unittest.TestCase):
    def setUp(self):
        self.url = 'https://reports.example/?symbol=SNDK&format=html&version='+'a'*64
        self.cell = {
            'userEnteredValue': {'stringValue': '9,2'},
            'formattedValue': '9,2',
            'note': 'Tesis fechada; puntuación sin cambios.',
            'hyperlink': self.url,
            'userEnteredFormat': {
                'numberFormat': {'type': 'TEXT'},
                'textFormat': {'fontFamily': 'Arial', 'fontSize': 10, 'link': {'uri': self.url}},
                'hyperlinkDisplayType': 'LINKED',
                'backgroundColorStyle': {'rgbColor': {'red': 1, 'green': 1, 'blue': 1}},
            },
        }

    def test_normalized_whole_cell_link_is_reconstituted_for_sort_write(self):
        original = deepcopy(self.cell)
        writable = _writable_cell(self.cell)
        self.assertEqual(writable['textFormatRuns'][0]['startIndex'], 0)
        self.assertEqual(writable['textFormatRuns'][0]['format']['link']['uri'], self.url)
        for field in ('userEnteredValue', 'note', 'userEnteredFormat'):
            self.assertEqual(writable[field], original[field])
        self.assertEqual(self.cell, original)

    def test_repeated_sheets_normalization_does_not_lose_versioned_target(self):
        current = deepcopy(self.cell)
        for _ in range(3):
            outgoing = _writable_cell(current)
            self.assertEqual(outgoing['textFormatRuns'][0]['format']['link']['uri'], self.url)
            # Sheets returns only a whole-cell link for a single uniform run.
            current = deepcopy(outgoing)
            current.pop('textFormatRuns')

    def test_existing_partial_rich_text_is_preserved_exactly(self):
        cell = deepcopy(self.cell)
        cell['textFormatRuns'] = [{'startIndex': 0, 'format': {'bold': True}},
                                  {'startIndex': 2, 'format': {'link': {'uri': self.url}}}]
        self.assertEqual(_writable_cell(cell)['textFormatRuns'], cell['textFormatRuns'])

    def test_plain_number_formula_and_blank_do_not_get_rich_runs(self):
        for entered in ({'numberValue': 9.2}, {'formulaValue': '=HYPERLINK("https://example.com";"9,2")'},
                        {'stringValue': ''}):
            with self.subTest(entered=entered):
                cell = deepcopy(self.cell)
                cell['userEnteredValue'] = entered
                self.assertNotIn('textFormatRuns', _writable_cell(cell))
        cell = deepcopy(self.cell)
        cell['userEnteredFormat']['textFormat'].pop('link')
        self.assertNotIn('textFormatRuns', _writable_cell(cell))


if __name__ == '__main__': unittest.main()
