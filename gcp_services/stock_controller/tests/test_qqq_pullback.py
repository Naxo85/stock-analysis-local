from datetime import date, datetime, timedelta, timezone
import unittest

from stock_analysis.contracts.market import DailyBar
from stock_analysis.controller.qqq_pullback_panel import build_pullback_requests
from stock_analysis.market_worker.relative_pullback import current_pullback, _session


def history(prices):
    day = date(2026, 8, 3)
    rows = []
    for price in prices:
        while not _session(day):
            day += timedelta(days=1)
        rows.append(DailyBar(day, price * 1.01, price * .99, price))
        day += timedelta(days=1)
    return tuple(rows)


def calculate(prices):
    rows = history([100, 94, 100, *prices])
    return current_pullback(rows, as_of=datetime.combine(rows[-1].session_date, datetime.min.time(), tzinfo=timezone.utc).replace(hour=21))


class PullbackTests(unittest.TestCase):
    def test_lower_relative_peak_after_rebound(self):
        result = calculate([120, 108, 114, 108])
        self.assertEqual(result['peak'], 114)
        self.assertAlmostEqual(result['drawdown'], 108 / 114 - 1)
        self.assertEqual(result['phase'], 'open')

    def test_no_repeat_until_five_percent_rebound(self):
        result = calculate([120, 113, 108, 112, 109])
        self.assertEqual(result['peak'], 120)
        self.assertEqual(result['trigger_date'], history([100, 94, 100, 120, 113])[-1].session_date.isoformat())

    def test_rearm_and_follow_new_high(self):
        result = calculate([120, 108, 114, 118, 117])
        self.assertEqual(result['peak'], 118)
        self.assertIsNone(result['trigger_date'])
        self.assertEqual(result['phase'], 'tracking')

    def test_intraday_bar_is_excluded(self):
        rows = history([100, 94, 100, 120, 112, 1])
        now = datetime.combine(rows[-1].session_date, datetime.min.time(), tzinfo=timezone.utc).replace(hour=16)
        result = current_pullback(rows, as_of=now)
        self.assertEqual(result['close'], 112)
        self.assertEqual(result['close_date'], rows[-2].session_date.isoformat())

    def test_invalid_and_ambiguous_histories_are_unknown(self):
        self.assertEqual(calculate([110, float('nan')])['status'], 'unavailable')
        rows = history([100, 110, 105])
        now = datetime.combine(rows[-1].session_date, datetime.min.time(), tzinfo=timezone.utc).replace(hour=21)
        self.assertEqual(current_pullback(rows, as_of=now)['status'], 'unavailable')
        self.assertEqual(current_pullback(rows + (rows[-1],), as_of=now)['status'], 'unavailable')

    def test_gap_in_current_leg_is_unknown(self):
        rows = history([100, 94, 100, 120, 112, 108])
        now = datetime.combine(rows[-1].session_date, datetime.min.time(), tzinfo=timezone.utc).replace(hour=21)
        self.assertEqual(current_pullback(rows[:4] + rows[5:], as_of=now)['status'], 'unavailable')

    def test_missing_latest_close_is_explicit(self):
        rows = history([100, 94, 100, 120, 112, 108])
        now = datetime.combine(rows[-1].session_date, datetime.min.time(), tzinfo=timezone.utc).replace(hour=21)
        result = current_pullback(rows[:-1], as_of=now)
        self.assertEqual(result['reason'], 'Pendiente del último cierre')

    def test_writer_cannot_move_or_modify_tables(self):
        layout = {'schema_version': 5, 'sheet': {'sheet_id': 206129407}, 'general_panel': {'column': 'A'}}
        requests = build_pullback_requests(layout, calculate([120, 112]))
        for request in requests:
            kind, body = next(iter(request.items()))
            self.assertIn(kind, ('mergeCells', 'unmergeCells', 'repeatCell', 'updateCells'))
            target = body.get('range') or body['start']
            self.assertEqual(target['sheetId'], 206129407)
            self.assertGreaterEqual(target.get('startRowIndex', target.get('rowIndex')), 1)
            self.assertLessEqual(target.get('endRowIndex', target.get('rowIndex', 0) + 1), 7)
            self.assertGreaterEqual(target.get('startColumnIndex', target.get('columnIndex')), 2)
            self.assertLessEqual(target.get('endColumnIndex', target.get('columnIndex', 0) + 1), 8)
        numeric = [r['updateCells']['rows'][0]['values'][0]['userEnteredValue'] for r in requests if 'updateCells' in r]
        self.assertEqual(sum('numberValue' in v for v in numeric), 1)

    def test_unavailable_does_not_display_zero(self):
        layout = {'schema_version': 5, 'sheet': {'sheet_id': 206129407}, 'general_panel': {'column': 'A'}}
        requests = build_pullback_requests(layout, {'status': 'unavailable', 'reason': 'Pendiente del último cierre'})
        values = [r['updateCells']['rows'][0]['values'][0]['userEnteredValue'] for r in requests if 'updateCells' in r]
        self.assertFalse(any('numberValue' in v for v in values))
        self.assertIn({'stringValue': 'N/D'}, values)


if __name__ == '__main__':
    unittest.main()
