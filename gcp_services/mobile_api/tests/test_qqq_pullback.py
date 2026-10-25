import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from projection import project


class CurrentPullbackProjectionTests(unittest.TestCase):
    def project(self, drawdown=None, title='QQQ · RETROCESO ACTUAL'):
        def cell(value):
            return {'effectiveValue': {'numberValue' if isinstance(value, float) else 'stringValue': value}}
        rows = [{}, {'values': [{}, {}, cell(title)]},
                {'values': [{}, {}, cell(drawdown if drawdown is not None else 'N/D'), {}, {}, cell('Episodio abierto')]},
                {'values': [{}, {}, {}, {}, {}, cell('Umbral −5%: 721,68 $')]},
                {'values': [{}, {}, cell('Máximo: 759,66 $ · 06/10/2026')]},
                {'values': [{}, {}, cell('Cierre: 709,80 $ · 16/10/2026')]},
                {'values': [{}, {}, cell('Cierres diarios · reinicio tras rebote del 5%')]}]
        layout = {'blocks': [], 'groups': [], 'general_panel': {'start_row': 2, 'column': 'A', 'lines': []}}
        return project(layout, {}, {}, {'sheets': [{'data': [{'rowData': rows}]}]}, {}, {}, [])['market']['qqq_pullback']

    def test_same_numeric_cell_and_dated_close_reach_mobile(self):
        result = self.project(-0.065634626)
        self.assertEqual(result['drawdown'], -0.065634626)
        self.assertEqual(result['close_label'], 'Cierre: 709,80 $ · 16/10/2026')
        self.assertEqual(result['peak_label'], 'Máximo: 759,66 $ · 06/10/2026')

    def test_unavailable_is_not_zero(self):
        self.assertIsNone(self.project()['drawdown'])

    def test_old_sheet_has_no_invented_relative_metric(self):
        self.assertIsNone(self.project(-.1, title='Otro bloque'))

    def test_compact_numeric_label_and_unavailable_remain_distinct(self):
        layout = {'blocks': [], 'groups': [], 'general_panel': {'start_row': 2, 'column': 'A', 'lines': []}}
        for entered in [-.0656, 0., 'N/D']:
            with self.subTest(value=entered):
                cell = {'effectiveValue': {'numberValue' if isinstance(entered, float) else 'stringValue': entered},
                        'formattedValue': 'Caída QQQ: -6,56%' if isinstance(entered, float) else 'N/D',
                        'note': 'QQQ: distancia al máximo relativo de cierre del tramo actual.'}
                sheet = {'sheets': [{'data': [{'startRow': 1, 'startColumn': 2, 'rowData': [{'values': [cell]}]}]}]}
                actual = project(layout, {}, {}, sheet, {}, {}, [])['market']['qqq_pullback']
                self.assertEqual(actual['drawdown'], entered if isinstance(entered, float) else None)
