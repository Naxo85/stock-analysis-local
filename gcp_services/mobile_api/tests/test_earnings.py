from datetime import datetime, timezone
from pathlib import Path
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from projection import project


class EarningsProjectionTests(unittest.TestCase):
    def test_mobile_uses_same_calendar_and_rolls_day_without_report_update(self):
        layout = {'blocks': [], 'groups': [{'id': 'g', 'tickers': ['LRCX', 'SPCX']}],
                  'general_panel': {'start_row': 2, 'column': 'A', 'lines': []}}
        earnings = {'LRCX': {'date': '2026-10-21', 'as_of': '2026-10-20'},
                    'SPCX': {'date': '2026-10-20', 'as_of': '2026-10-20'}}
        for day, labels in ((20, ['mañana', 'hoy']), (21, ['hoy', None]), (22, [None, None])):
            result = project(layout, {'positions': {'LRCX': 2}}, {}, {}, {}, {}, [], earnings=earnings,
                             now=datetime(2026, 10, day, 12, tzinfo=timezone.utc))
            self.assertEqual([(s['earnings_alert'] or {}).get('label') for s in result['stocks']], labels)
            self.assertEqual(result['stocks'][0]['shots'], 2)
            self.assertEqual(result['stocks'][0]['earnings']['as_of'], '2026-10-20')

    def test_calendar_logic_is_identical_to_controller(self):
        root = next((p for p in Path(__file__).resolve().parents if (p / 'gcp_services').exists()), None)
        if root is None:
            self.skipTest('source parity is checked in local workspace')
        self.assertEqual((root / 'gcp_services/mobile_api/earnings_calendar.py').read_bytes(),
                         (root / 'gcp_services/stock_controller/src/stock_analysis/earnings_calendar.py').read_bytes())
