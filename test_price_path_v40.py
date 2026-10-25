import copy
import unittest
from datetime import date, timedelta
from gcp_functions.support_resistances_raw.market_sessions import market_session
from gcp_functions.support_resistances_raw.price_path import horizontal_path_evidence


def bars(values, start="2026-10-01"):
    result = []
    day = date.fromisoformat(start)
    for lo, hi, cl in values:
        while not market_session(day):
            day += timedelta(days=1)
        result.append(dict(date=day.isoformat(), low=lo, high=hi, close=cl))
        day += timedelta(days=1)
    return result


class PricePathEvidenceTests(unittest.TestCase):
    def test_adversity_precedes_rebound_without_claiming_trade(self):
        rows = bars([(115,120,118), (99,101,100), (80,102,85),
                     (84,110,108), (106,108,107), (107,109,108), (107,108,107)])
        original = copy.deepcopy(rows)
        result = horizontal_path_evidence(100, rows, .5)
        event = result['events'][0]
        self.assertEqual(event['adverse_excursion_pct'], 20)
        self.assertEqual(event['favorable_excursion_pct'], 10)
        self.assertEqual(event['terminal_close_return_pct'], 7)
        self.assertEqual(event['extreme_order'], 'adverse_extreme_first')
        self.assertEqual(event['approach'], 'from_above')
        self.assertFalse(result['independent_trials_assumed'])
        self.assertEqual(rows, original)
        self.assertNotIn('defended', event)

    def test_same_bar_extremes_preserve_unknown_order(self):
        rows = bars([(99,101,100), (90,110,100)])
        event = horizontal_path_evidence(100, rows, 0, forward_sessions=1)['events'][0]
        self.assertEqual(event['extreme_order'], 'same_session_unknown')
        self.assertEqual(event['favorable_excursion_pct'], 10)
        self.assertEqual(event['adverse_excursion_pct'], 10)

    def test_touch_day_extremes_are_not_post_close_returns(self):
        rows = bars([(50,200,100), (101,102,101)])
        result = horizontal_path_evidence(100, rows, 0, forward_sessions=1)
        self.assertEqual(result['events'][0]['favorable_excursion_pct'], 2)
        self.assertEqual(result['events'][0]['adverse_excursion_pct'], 0)

    def test_partial_window_is_pending_not_failure(self):
        result = horizontal_path_evidence(100, bars([(99,101,100), (101,102,101)]), 0)
        self.assertEqual(result['status'], 'unavailable')
        self.assertEqual(result['completed_count'], 0)
        self.assertEqual(result['pending_count'], 1)
        self.assertNotIn('median_adverse_excursion_pct', result)

    def test_missing_or_invalid_future_data_excluded(self):
        rows = bars([(99,101,100), (101,102,110)])
        result = horizontal_path_evidence(100, rows, 0, forward_sessions=1)
        self.assertEqual(result['incomplete_data_count'], 1)
        self.assertEqual(result['completed_count'], 0)

    def test_overlapping_windows_not_independent(self):
        rows = bars([(95,97,96), (99,101,100), (102,104,103),
                     (99,101,100), (102,104,103), (103,105,104),
                     (104,106,105), (105,107,106), (106,108,107)])
        result = horizontal_path_evidence(100, rows, .5, max_events=1)
        self.assertEqual(result['completed_count'], 2)
        self.assertEqual(result['overlapping_window_count'], 1)
        self.assertEqual(result['events_omitted'], 1)
        self.assertEqual(result['events'][0]['approach'], 'from_above')

    def test_contact_close_must_be_a_valid_observed_price(self):
        for close in (110, 90, 0, None, float('nan'), True):
            with self.subTest(close=close):
                rows = bars([(99, 101, close), (101, 102, 101)])
                result = horizontal_path_evidence(100, rows, 0, forward_sessions=1)
                self.assertEqual(result['incomplete_data_count'], 1)
                self.assertEqual(result['completed_count'], 0)
                self.assertEqual(result['events'], [])
        rows = bars([(-1, 101, 100), (101, 102, 101)])
        self.assertEqual(horizontal_path_evidence(100, rows, 0, forward_sessions=1)
                         ['incomplete_data_count'], 1)

    def test_invalid_contact_is_not_a_pending_valid_observation(self):
        result = horizontal_path_evidence(100, bars([(99, 101, 110)]), 0)
        self.assertEqual(result['incomplete_data_count'], 1)
        self.assertEqual(result['pending_count'], 0)

    def test_detail_budget_preserves_omitted_unfavorable_observations(self):
        values = [(99, 101, 100), (80, 90, 85)]
        for _ in range(7):
            values.extend([(99, 101, 100), (101, 102, 101)])
        rows = bars(values)
        complete = horizontal_path_evidence(100, rows, 0, forward_sessions=1, max_events=8)
        bounded = horizontal_path_evidence(100, rows, 0, forward_sessions=1)
        no_detail = horizontal_path_evidence(100, rows, 0, forward_sessions=1, max_events=0)
        self.assertEqual(len(bounded['events']), 3)
        self.assertEqual(bounded['events'], complete['events'][-3:])
        self.assertEqual(bounded['events_omitted'], 5)
        self.assertEqual(bounded['completed_count'], 8)
        self.assertEqual(bounded['negative_terminal_count'], 1)
        self.assertEqual(bounded['max_adverse_excursion_pct'], 20)
        self.assertEqual(bounded['min_terminal_close_return_pct'], -15)
        self.assertEqual(bounded['same_session_extremes_count'], 8)
        self.assertTrue(all(e['terminal_close_return_pct'] > 0 for e in bounded['events']))
        summaries = lambda result: {k: v for k, v in result.items()
                                    if k not in ('events', 'events_omitted')}
        self.assertEqual(summaries(complete), summaries(bounded))
        self.assertEqual(summaries(complete), summaries(no_detail))
        self.assertEqual(no_detail['events'], [])

    def test_missing_session_cannot_be_replaced_with_a_later_row(self):
        rows = bars([(99, 101, 100)] + [(102, 104, 103)] * 6)
        del rows[2]
        result = horizontal_path_evidence(100, rows, 0)
        self.assertEqual(len(rows), 6)
        self.assertEqual(result['contact_count'], 1)
        self.assertEqual(result['completed_count'], 0)
        self.assertEqual(result['incomplete_data_count'], 1)
        self.assertEqual(result['pending_count'], 0)
        self.assertEqual(result['negative_terminal_count'], 0)
        self.assertEqual(result['events'], [])

    def test_gap_in_partial_window_is_incomplete_not_pending(self):
        rows = bars([(99, 101, 100)] + [(102, 104, 103)] * 2)
        del rows[1]
        result = horizontal_path_evidence(100, rows, 0)
        self.assertEqual(result['incomplete_data_count'], 1)
        self.assertEqual(result['pending_count'], 0)

    def test_weekend_and_holiday_are_not_missing_sessions(self):
        rows = bars([(99, 101, 100)] + [(102, 104, 103)] * 5,
                    start='2026-11-25')
        self.assertEqual([row['date'] for row in rows],
                         ['2026-11-25', '2026-11-27', '2026-11-30',
                          '2026-12-01', '2026-12-02', '2026-12-03'])
        result = horizontal_path_evidence(100, rows, 0)
        self.assertEqual(result['completed_count'], 1)
        self.assertEqual(result['incomplete_data_count'], 0)
        self.assertEqual(result['events'][0]['window_end'], '2026-12-03')

    def test_exceptional_closure_requires_explicit_calendar_input(self):
        rows = bars([(99, 101, 100)] + [(102, 104, 103)] * 6)
        missing_day = rows[2]['date']
        del rows[2]
        unknown = horizontal_path_evidence(100, rows, 0)
        known = horizontal_path_evidence(100, rows, 0, extra_closures=[missing_day])
        self.assertEqual(unknown['incomplete_data_count'], 1)
        self.assertEqual(known['completed_count'], 1)
        self.assertEqual(known['incomplete_data_count'], 0)
        self.assertEqual(known['events'][0]['window_end'], rows[-1]['date'])

    def test_nonmarket_row_cannot_count_as_a_session(self):
        rows = bars([(99, 101, 100), (102, 104, 103)])
        rows[1]['date'] = '2026-10-03'
        result = horizontal_path_evidence(100, rows, 0, forward_sessions=1)
        self.assertEqual(result['incomplete_data_count'], 1)
        self.assertEqual(result['completed_count'], 0)
        rows[0]['date'] = '2026-09-31'
        self.assertEqual(horizontal_path_evidence(100, rows, 0)['reason'],
                         'invalid_session_date')

    def test_no_future_curve_or_inventory_inference(self):
        result = horizontal_path_evidence(100, bars([(99,101,100),(98,101,99)]), 0,
                                          forward_sessions=1)
        self.assertIn('not a historical AVWAP curve', result['scope'])
        self.assertIn('not ex-ante validation', result['scope'])

    def test_invalid_coordinate_and_session_order(self):
        rows = bars([(99,101,100), (98,101,99)])
        self.assertEqual(horizontal_path_evidence(float('nan'), rows, 0)['status'], 'unavailable')
        self.assertEqual(horizontal_path_evidence(100, rows[::-1], 0)['reason'], 'invalid_session_order')
        self.assertEqual(horizontal_path_evidence(100, rows + rows, 0)['reason'], 'invalid_session_order')
        with self.assertRaises(ValueError):
            horizontal_path_evidence(100, rows, 0, forward_sessions=0)


if __name__ == '__main__':
    unittest.main()
