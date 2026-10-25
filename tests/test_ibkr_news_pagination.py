"""Offline coverage for observed IBKR backward-cursor compatibility."""
import asyncio
import json
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace as N
from unittest.mock import Mock, patch
from ib_insync import IB, util
from src.local_runner.ibkr_news_pagination import collect_cached_headlines
from src.local_runner.ibkr_analyst_probe import (
    _request_complete_historical_news, _collect_complete_historical_news,
    fetch_ibkr_analyst_headlines, build_probe_payload, require_complete_news_payload,
)

END = datetime(2026,10,18,7,35,13,123456,tzinfo=timezone.utc)
START = datetime(2026,10,13,16,17,46,tzinfo=timezone.utc)
def row(id, days=0, *, seconds=0, headline='headline'):
    return N(time=(END-timedelta(days=days,seconds=seconds)).replace(microsecond=0),
             providerCode='DJ-N',articleId=id,headline=headline)
def terminal(more):
    return {'terminal_received':True,'has_more':more,'request_id':17}

class PaginationTests(unittest.TestCase):
    def collect(self,pages,**kwargs):
        requests=[]
        def fetch(cursor,limit,timeout):
            requests.append((cursor,limit,timeout))
            value=pages[len(requests)-1]
            if isinstance(value,Exception):raise value
            return value
        result=collect_cached_headlines(fetch,start=START,end=END,limit=kwargs.pop('limit',3),**kwargs)
        return result,requests
    def test_default_capacity_accepts_fourteen_pages_only_with_actual_eof(self):
        pages=[]
        for index in range(14):
            items=[row(str(index),index+1)]
            if index:items.insert(0,row(str(index-1),index))
            pages.append((items,terminal(index<13)))
        (items,coverage),requests=self.collect(pages)
        self.assertEqual(len(items),14)
        self.assertEqual(len(requests),14)
        self.assertEqual(coverage['max_pages'],16)
        self.assertEqual(coverage['total_timeout_seconds'],180)
        self.assertIs(coverage['has_more'],False)
    def test_default_capacity_still_rejects_sixteen_more_pages(self):
        pages=[]
        for index in range(16):
            items=[row(str(index),index+1)]
            if index:items.insert(0,row(str(index-1),index))
            pages.append((items,terminal(True)))
        with self.assertRaisesRegex(RuntimeError,'page_limit'):self.collect(pages)
    def test_overlap_preserves_new_identity_at_same_second(self):
        a,b,c,d=row('a'),row('b',1),row('c',1),row('d',2)
        (values,cov),requests=self.collect([([a,b],terminal(True)),([b,c,d],terminal(False))])
        self.assertEqual({v.articleId for v in values},{'a','b','c','d'})
        self.assertEqual(cov['duplicate_count'],1)
        self.assertEqual(cov['page_count'],2)
        self.assertEqual(requests[1][0],b.time+timedelta(seconds=1))
        self.assertEqual(requests[0][0],END.replace(microsecond=0)+timedelta(seconds=1))
        self.assertEqual(cov['has_more'],False)
        self.assertEqual(cov['total_timeout_seconds'],180)
        require_complete_news_payload({'coverage':cov})
    def test_lower_bound_crossing_is_never_completion(self):
        with self.assertRaisesRegex(RuntimeError,'page_limit'):
            self.collect([([row('old',20)],terminal(True))],max_pages=1)
    def test_empty_initial_terminal_false_is_complete(self):
        (values,cov),_=self.collect([([],terminal(False))])
        self.assertEqual(values,[]);self.assertEqual(cov['status'],'complete')
    def test_exact_limit_false_is_complete_without_guessing(self):
        (values,cov),_=self.collect([([row('a'),row('b',1),row('c',2)],terminal(False))])
        self.assertEqual(len(values),3);self.assertFalse(cov['has_more'])
    def test_empty_true_fails(self):
        with self.assertRaisesRegex(RuntimeError,'empty_with_more'):self.collect([([],terminal(True))])
    def test_missing_overlap_fails_even_when_terminal_false(self):
        with self.assertRaisesRegex(RuntimeError,'boundary_missing'):
            self.collect([([row('a'),row('b',1)],terminal(True)),([row('c',2)],terminal(False))])
    def test_saturated_second_fails_without_decrementing_cursor(self):
        a,b,c=row('a',1),row('b',1),row('c',1)
        with self.assertRaisesRegex(RuntimeError,'no_progress_or_saturated_second'):
            self.collect([([a,b,c],terminal(True)),([a,b,c],terminal(True))])
    def test_identity_conflict_fails(self):
        with self.assertRaisesRegex(RuntimeError,'identity_conflict'):
            self.collect([([row('a',1)],terminal(True)),([row('a',1,headline='changed')],terminal(False))])
    def test_all_boundary_second_identities_must_return(self):
        a,b=row('a',1),row('b',1)
        with self.assertRaisesRegex(RuntimeError,'boundary_missing'):
            self.collect([([a,b],terminal(True)),([a,row('c',2)],terminal(False))])
    def test_unsorted_rejected(self):
        with self.assertRaisesRegex(RuntimeError,'not_descending'):
            self.collect([([row('old',2),row('new',1)],terminal(False))])
    def test_cursor_violation_rejected(self):
        with self.assertRaisesRegex(RuntimeError,'cursor_not_respected'):
            self.collect([([row('future',-1)],terminal(False))])
    def test_missing_identity_timestamp_and_headline_rejected(self):
        for field,value,error in [('articleId',None,'missing_identity'),('time','unknown','invalid_timestamp'),('headline',None,'invalid_headline')]:
            with self.subTest(field=field):
                item=row('a');setattr(item,field,value)
                with self.assertRaisesRegex(RuntimeError,error):self.collect([([item],terminal(False))])
    def test_unknown_terminal_rejected(self):
        for coverage in ({},{'terminal_received':True,'has_more':0},{'has_more':False}):
            with self.subTest(coverage=coverage):
                with self.assertRaisesRegex(RuntimeError,'terminal_unknown'):self.collect([([],coverage)])
    def test_page_over_limit_rejected(self):
        with self.assertRaisesRegex(RuntimeError,'page_exceeds_limit'):
            self.collect([([row('a'),row('b',1)],terminal(False))],limit=1)
    def test_request_error_never_returns_accumulated_partial(self):
        with self.assertRaisesRegex(RuntimeError,'provider failure'):
            self.collect([([row('a',1)],terminal(True)),RuntimeError('provider failure')])
    def test_total_budget_rejected_even_on_late_terminal_false(self):
        clock=iter([0,0,0,181])
        with self.assertRaisesRegex(RuntimeError,'total_timeout'):
            self.collect([([],terminal(False))],clock=lambda:next(clock))
    def test_remaining_time_bounds_page_clock(self):
        clock=iter([0,165,165,166,166,166])
        (_,cov),requests=self.collect([([],terminal(False))],clock=lambda:next(clock))
        self.assertEqual(requests[0][2],15)
    def test_explicit_smaller_collector_budgets_remain_effective(self):
        (_,coverage),requests=self.collect([([],terminal(False))],page_timeout=10,max_pages=8,total_timeout=75)
        self.assertEqual(requests[0][2],10)
        self.assertEqual(coverage['max_pages'],8)
        self.assertEqual(coverage['total_timeout_seconds'],75)
        clock=iter([0,0,0,76])
        with self.assertRaisesRegex(RuntimeError,'total_timeout'):
            self.collect([([],terminal(False))],total_timeout=75,clock=lambda:next(clock))
    def test_invalid_limits_do_not_request(self):
        for limit in (0,301,True):
            with self.subTest(limit=limit):
                with self.assertRaises(ValueError):self.collect([],limit=limit)
        for field,value in [('page_timeout',0),('total_timeout',float('nan')),('max_pages',0)]:
            with self.subTest(field=field):
                with self.assertRaises(ValueError):self.collect([],**{field:value})
    def test_naive_window_rejected(self):
        fetch=Mock()
        with self.assertRaises(ValueError):
            collect_cached_headlines(fetch,start=START.replace(tzinfo=None),end=END,limit=300)
        fetch.assert_not_called()
    def test_payload_preserves_raw_before_and_after_exact_window(self):
        items=[row('old',10),row('within',1),N(time=END+timedelta(microseconds=1),providerCode='DJ-N',articleId='later',headline='later')]
        payload=build_probe_payload(symbol='X',contract=N(conId=1),provider='DJ-N',providers=[],
            headlines=items,start=START,generated_at=END,host='127.0.0.1',port=7497)
        self.assertEqual(payload['raw_headline_count'],3)
        self.assertEqual(len(payload['raw_headlines']),3)
        self.assertEqual([r['articleId'] for r in payload['headlines']],['within'])
        self.assertEqual(payload['filtered_before_start_count'],1)
        self.assertEqual(payload['filtered_after_end_count'],1)
    def test_complete_cache_can_yield_empty_window(self):
        (items,coverage),_=self.collect([([row('old',20)],terminal(False))])
        payload=build_probe_payload(symbol='X',contract=N(conId=1),provider='DJ-N',providers=[],
            headlines=items,start=START,generated_at=END,host='127.0.0.1',port=7497,coverage=coverage)
        self.assertEqual(payload['headline_count'],0)
        self.assertEqual(payload['raw_headline_count'],1)
        require_complete_news_payload(payload)
    def test_collector_uses_iso_backward_cursor_empty_end_and_thirty_seconds(self):
        with patch('src.local_runner.ibkr_analyst_probe._request_complete_historical_news',return_value=([],terminal(False))) as request:
            _collect_complete_historical_news(Mock(),1,'DJ-N',START,END,300)
        self.assertEqual(request.call_args.args[3:6],('2026-10-18 07:35:14.0','',300))
        self.assertEqual(request.call_args.kwargs,{'timeout':30.0,'allow_more':True})
    def test_connection_clock_separate_private_disconnect_on_failure(self):
        ib=Mock();ib.qualifyContracts.return_value=[N(conId=1)];ib.isConnected.return_value=True
        with patch('ib_insync.IB',return_value=ib),patch('src.local_runner.ibkr_analyst_probe._collect_complete_historical_news',side_effect=RuntimeError('page_limit')) as request:
            with self.assertRaisesRegex(RuntimeError,'page_limit'):
                fetch_ibkr_analyst_headlines(symbol='X',host='127.0.0.1',port=7497,client_id=71,
                    provider='DJ-N',start=START,total_results=300,readonly=True,timeout=10,generated_at=END)
        self.assertEqual(ib.connect.call_args.kwargs['timeout'],10)
        self.assertEqual(request.call_args.kwargs['historical_timeout'],30)
        ib.disconnect.assert_called_once_with()

class DuplicateTerminalTests(unittest.TestCase):
    def test_duplicate_terminals_are_not_silently_accepted(self):
        for second in (False,True):
            with self.subTest(second=second):
                ib=IB();ib.client.getReqId=lambda:17
                def request(req_id,*args):
                    def complete():
                        ib.wrapper.historicalNewsEnd(req_id,False)
                        ib.wrapper.historicalNewsEnd(req_id,second)
                    util.getLoop().call_soon(complete)
                ib.client.reqHistoricalNews=request
                try:
                    with self.assertRaisesRegex(RuntimeError,'terminal coverage unknown'):
                        _request_complete_historical_news(ib,1,'DJ-N','','',300)
                    self.assertFalse(ib.wrapper._futures);self.assertFalse(ib.wrapper._results)
                    self.assertFalse(ib.RaiseRequestErrors)
                finally:ib.disconnect()
    def test_allow_more_is_only_incomplete_page_not_payload_coverage(self):
        ib=IB();ib.client.getReqId=lambda:17
        ib.client.reqHistoricalNews=lambda req_id,*args:util.getLoop().call_soon(ib.wrapper.historicalNewsEnd,req_id,True)
        try:
            rows,coverage=_request_complete_historical_news(ib,1,'DJ-N','','',300,allow_more=True)
            self.assertEqual(coverage['status'],'incomplete')
            with self.assertRaisesRegex(RuntimeError,'coverage_not_verified'):require_complete_news_payload({'coverage':coverage})
        finally:ib.disconnect()

if __name__=='__main__':unittest.main()
