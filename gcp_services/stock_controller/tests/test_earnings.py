from copy import deepcopy
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch
import unittest

from stock_analysis.earnings_calendar import calendar_from_reports, earnings_alert
from stock_analysis.controller.earnings_sheet import build_earnings_requests, ticker_notes, _note
from stock_analysis.controller.sheet_tickers import TickerRows

NOW = datetime(2026, 10, 21, 12, tzinfo=timezone.utc)


def event(days=0):
    return {'date': (NOW.date() + timedelta(days=days)).isoformat(),
            'source': 'Finnhub · calendario publicado', 'as_of': '2026-10-20T21:10:36Z'}


def layout():
    return {'sheet': {'sheet_id': 123}, 'table_template': {'ticker_column_offset': 1},
            'blocks': [{'table_name': 'Left', 'start_column': 'J', 'header_row': 3, 'tickers': ['A', 'B']},
                       {'table_name': 'Right', 'start_column': 'Y', 'header_row': 3, 'tickers': ['C', 'D']}]}


class EarningsTests(unittest.TestCase):
    def test_window_includes_today_tomorrow_and_seven_but_not_yesterday_or_eight(self):
        for days in (-1, 0, 1, 2, 7, 8):
            with self.subTest(days=days):
                alert = earnings_alert(event(days), now=NOW)
                if days in (-1, 8):
                    self.assertIsNone(alert)
                else:
                    self.assertEqual(alert['severity'], 'red' if days < 2 else 'orange')
                    self.assertEqual(alert['days'], days)

    def test_madrid_midnight_changes_label_and_expires_with_no_new_report(self):
        before = datetime(2026, 10, 21, 21, 59, tzinfo=timezone.utc)
        after = before + timedelta(minutes=1)
        self.assertEqual(earnings_alert(event(1), now=before)['label'], 'mañana')
        self.assertEqual(earnings_alert(event(1), now=after)['label'], 'hoy')
        self.assertIsNone(earnings_alert(event(), now=after))

    def test_invalid_unknown_and_ambiguous_dates_never_mark(self):
        for value in (None, '', '?', '2026-02-30', '20261021', '2026-10-21T00:00:00Z', 20261021, True):
            with self.subTest(value=value):
                self.assertIsNone(earnings_alert({'date': value}, now=NOW))
        self.assertIsNone(earnings_alert(None, now=NOW))

    def test_only_exact_structured_summary_is_a_calendar(self):
        p = {'symbol': 'A', 'analysis_status': 'ok', 'analyst_ratings_summary':
             {'status': 'ok', 'next_earnings_date': '2026-10-22', 'as_of': '2026-10-20', 'next_earnings_hour': 'amc'}}
        original = deepcopy(p)
        result = calendar_from_reports({'A': p})
        self.assertEqual(result['A']['date'], '2026-10-22')
        self.assertEqual(result['A']['as_of'], '2026-10-20')
        self.assertEqual(earnings_alert(result['A'], now=NOW)['hour_label'], 'después del cierre')
        self.assertEqual(p, original)
        for update in ({'symbol': 'OTHER'}, {'analysis_status': 'failed'}, {'analyst_ratings_summary': None}):
            self.assertEqual(calendar_from_reports({'A': {**p, **update}}), {})
        self.assertEqual(calendar_from_reports({'A': {'symbol': 'A', 'analysis_status': 'ok',
            'next_event': {'title': 'Resultados', 'date': '2026-10-22'}}}), {})

    def test_note_preserves_original_text_and_clears_only_calendar_block(self):
        original = 'Mi nota manual\nCon espacio final  '
        alert = earnings_alert(event(), now=NOW)
        marked = _note(original, alert)
        self.assertEqual(_note(marked, alert), marked)
        self.assertEqual(_note(marked, None), original)
        self.assertNotIn('apertura', marked)
        self.assertIn('21/10/2026 · hoy', marked)
        self.assertIn('2026-10-20T21:10:36Z', marked)
        self.assertEqual(_note(marked + '\nOtra nota posterior', None), original + '\nOtra nota posterior')

    def test_renderer_only_writes_ticker_edges_and_notes(self):
        requests = build_earnings_requests(layout(), {'A': event(), 'B': event(3)}, now=NOW)
        for request in requests:
            kind, body = next(iter(request.items()))
            self.assertIn(kind, ('updateBorders', 'repeatCell'))
            if kind == 'repeatCell':
                self.assertEqual(body['fields'], 'note')
                self.assertEqual(set(body['cell']), {'note'})
            target = body['range']
            self.assertIn(target['startColumnIndex'], (10, 25))
            self.assertEqual(target['endColumnIndex'], target['startColumnIndex'] + 1)
        self.assertEqual(requests[-1]['updateBorders']['top']['style'], 'SOLID_THICK')
        self.assertEqual(requests[-2]['updateBorders']['top']['style'], 'SOLID_THICK')

    def test_cross_table_move_follows_ticker_and_reapplies_after_clear(self):
        rows = TickerRows({'C': 3, 'D': 4, 'A': 3, 'B': 4},
                          table_by_ticker={'C': 'Left', 'D': 'Left', 'A': 'Right', 'B': 'Right'})
        requests = build_earnings_requests(layout(), {'A': event()}, ticker_rows=rows, now=NOW)
        border = requests[-1]['updateBorders']
        self.assertEqual(border['range']['startColumnIndex'], 25)
        self.assertEqual(border['range']['startRowIndex'], 3)
        self.assertEqual(border['top']['colorStyle']['rgbColor']['red'], 217/255)

    def test_expired_mark_clears_note_and_keeps_bottom_table_outline(self):
        previous = _note('Mi nota', earnings_alert(event(), now=NOW))
        requests = build_earnings_requests(layout(), {'B': event(-1)}, notes={'B': previous}, now=NOW)
        note = [r['repeatCell'] for r in requests if 'repeatCell' in r][0]
        self.assertEqual(note['cell']['note'], 'Mi nota')
        bottom = [r['updateBorders'] for r in requests if 'updateBorders' in r and r['updateBorders']['range']['startRowIndex'] == 4]
        self.assertTrue(all(r['bottom']['style'] == 'SOLID_MEDIUM' for r in bottom))
        self.assertFalse(any(r['top']['style'] != 'NONE' for r in bottom))

    def test_notes_are_resolved_by_symbol_before_sort(self):
        sheet = {'sheets': [{'properties': {'sheetId': 123}, 'data': [{'startRow': 3, 'startColumn': 9,
            'rowData': [{'values': [{}, {'effectiveValue': {'stringValue': 'B'}, 'note': 'Nota B'}]}]}]}]}
        self.assertEqual(ticker_notes(layout(), sheet), {'B': 'Nota B'})

    def test_sync_persists_calendar_without_changing_financial_payload(self):
        from stock_analysis.analysis_worker.run_sync import run
        from stock_analysis.controller.sheet_layout import load_market_sheet_layout
        from test_global_sheet_sort import spreadsheet
        full = load_market_sheet_layout()
        universe = [t for b in full['blocks'] for t in b['tickers']]
        payloads = {t: {'symbol': t, 'analysis_status': 'ok', 'generated_at': '2026-10-20T12:00:00Z',
            'decision': {'score': 7}, 'plan': {'entry': None, 'ambitious_entry': None},
            'analyst_ratings_summary': {'status': 'ok', 'next_earnings_date': '2026-10-21', 'as_of': '2026-10-20'}} for t in universe}
        original = deepcopy(payloads)
        store, client = Mock(), Mock()
        store.index.return_value = Mock(version='v1', publications={}, blobs={t: Mock(generation='1') for t in universe})
        store.sync_state.return_value = {}
        store.load.return_value = payloads
        client.get_spreadsheet.return_value = spreadsheet(full, 'Tesis')
        with patch('stock_analysis.analysis_worker.run_sync.resolve_ticker_rows_and_prices', return_value=({}, {})), \
             patch('stock_analysis.analysis_worker.run_sync.resolve_visible_scores', return_value={}):
            result = run(publish=True, force=True, store=store, sheets_client=client, layout=full)
        self.assertEqual(result['tickers'], len(universe))
        self.assertEqual(store.mark_synced.call_args.kwargs['earnings']['LRCX']['date'], '2026-10-21')
        self.assertEqual(payloads, original)

    def test_scheduled_refresh_rolls_colour_using_saved_calendar_after_reordering(self):
        from contextlib import ExitStack
        from stock_analysis.market_worker import run_refresh as refresh
        from stock_analysis.controller.sheet_layout import load_market_sheet_layout
        from test_global_sheet_sort import spreadsheet
        from test_market_sheet import metric
        full = load_market_sheet_layout()
        universe = [t for b in full['blocks'] for t in b['tickers']]
        client = Mock()
        client.get_spreadsheet.return_value = spreadsheet(full, 'Tesis')
        client.batch_get_values.return_value = [{'values': [[t] for t in b['tickers']]} for b in full['blocks']]
        with ExitStack() as stack:
            def replace(name, **kw):
                return stack.enter_context(patch(name, **kw))
            replace('stock_analysis.market_worker.run_refresh.tradier_token_from_environment', return_value='fixture')
            provider = replace('stock_analysis.market_worker.run_refresh.TradierMarketDataProvider')
            provider.return_value.fetch_universe.return_value = ({}, {})
            replace('stock_analysis.market_worker.run_refresh.calculate_universe_metrics', return_value=tuple(metric(t) for t in universe))
            replace('stock_analysis.market_worker.run_refresh.calculate_benchmark_metrics', return_value=())
            replace('stock_analysis.market_worker.run_refresh.fetch_general_market_inputs', return_value={})
            replace('stock_analysis.market_worker.run_refresh.build_general_market_overview', return_value=None)
            replace('stock_analysis.market_worker.run_refresh.build_sorted_group_summary_requests', return_value=[])
            replace('stock_analysis.market_worker.run_refresh.GoogleSheetsRestClient', return_value=client)
            replace('stock_analysis.analysis_worker.reports.load_display_state', return_value={'earnings': {'LRCX': event()}})
            refresh.run(publish=True, force=True, now=NOW - timedelta(days=2))
            orange = client.batch_update.call_args.args[1][-1]['updateBorders']
            self.assertEqual(orange['top']['style'], 'SOLID_THICK')
            refresh.run(publish=True, force=True, now=NOW - timedelta(days=1))
            red = client.batch_update.call_args.args[1][-1]['updateBorders']
            self.assertEqual(red['range'], orange['range'])
            self.assertEqual(red['top']['style'], 'SOLID_THICK')


if __name__ == '__main__':
    unittest.main()
