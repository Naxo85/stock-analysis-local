"""No absent/malformed holdings may become an invented owned=False."""
import argparse,json,unittest
from unittest.mock import patch
from src.local_runner import run_batch
from src.local_runner.ownership import recorded_ownership,MARKET_OWNERSHIP_GCS_URI

def config(rows):return json.dumps({'generated_at':'2026-10-16T12:00:00Z','ticker_records':rows})
def args(**kw):
    return argparse.Namespace(**dict({'from_gcs':True,'config_gcs':None,'tickers':None,'generation_provider':'codex','legacy_codex':False},**kw))

class OwnershipInputs(unittest.TestCase):
    def test_individual_and_manual_use_current_market_authority(self):
        rows=[{'ticker':'TLN','owned':False},{'ticker':'CAT','owned':True}]
        with patch.object(run_batch,'_read_gcs_text',return_value=config(rows)) as read:
            owned,proof=recorded_ownership('TLN')
            self.assertIs(owned,False);self.assertEqual(proof['source'],MARKET_OWNERSHIP_GCS_URI)
            read.assert_called_once_with(MARKET_OWNERSHIP_GCS_URI)
        with patch.object(run_batch,'_read_gcs_text',return_value=config(rows)) as read:
            records,_=run_batch._load_ticker_records(args(from_gcs=False,tickers='CAT,TLN'))
            self.assertEqual([(r.ticker,r.owned) for r in records],[('CAT',True),('TLN',False)])
            read.assert_called_once_with(MARKET_OWNERSHIP_GCS_URI)

    def test_explicit_boolean_records_and_sources_preserved_without_extra_fetch(self):
        rows=[{'ticker':'CAT','owned':False,'ownership_source':'explicit:list'}, {'ticker':'TLN','owned':True}]
        for source in (run_batch.TICKERS_GCS_URI,run_batch.CORE_TICKERS_GCS_URI,MARKET_OWNERSHIP_GCS_URI):
            with self.subTest(source=source),patch.object(run_batch,'_read_gcs_text',return_value=config(rows)) as read:
                records,actual=run_batch._load_ticker_records(args(config_gcs=source))
                self.assertEqual([(r.ticker,r.owned,r.ownership_source) for r in records],[('CAT',False,'explicit:list'),('TLN',True,None)])
                self.assertEqual(actual,source);read.assert_called_once_with(source)

    def test_missing_and_nonboolean_values_resolve_strict_market_not_truthiness(self):
        unknown=[{}, {'owned':None}, {'owned':'false'}, {'owned':0}, {'owned':1}, {'owned':[]}]
        for value in unknown:
            with self.subTest(value=value):
                requested=config([dict(ticker='CAT',ownership_source='unverified_old_source',**value),{'ticker':'TLN'}])
                authoritative=config([{'ticker':'CAT','owned':True},{'ticker':'TLN','owned':False}])
                with patch.object(run_batch,'_read_gcs_text',side_effect=[requested,authoritative]) as read:
                    records,_=run_batch._load_ticker_records(args())
                self.assertEqual([(r.ticker,r.owned) for r in records],[('CAT',True),('TLN',False)])
                self.assertTrue(all(r.ownership_source==MARKET_OWNERSHIP_GCS_URI for r in records))
                self.assertEqual(read.call_count,2)

    def test_list_only_selects_same_order_and_looks_up_owned_explicitly(self):
        requested=json.dumps({'tickers':['CAT','TLN']})
        with patch.object(run_batch,'_read_gcs_text',side_effect=[requested,config([{'ticker':'TLN','owned':True},{'ticker':'CAT','owned':False}])]):
            records,_=run_batch._load_ticker_records(args())
        self.assertEqual([(r.ticker,r.owned) for r in records],[('CAT',False),('TLN',True)])

    def test_market_unknown_ambiguous_or_nonboolean_is_visible_failure(self):
        for rows in ([],[{'ticker':'CAT'}],[{'ticker':'CAT','owned':'false'}],[{'ticker':'CAT','owned':0}],[{'ticker':'CAT','owned':True},{'ticker':'CAT','owned':False}]):
            with self.subTest(rows=rows),patch.object(run_batch,'_read_gcs_text',side_effect=[json.dumps({'tickers':['CAT']}),config(rows)]):
                with self.assertRaisesRegex(RuntimeError,'ownership_unavailable'):
                    run_batch._load_ticker_records(args())

    def test_market_source_does_not_re_fetch_or_fall_back_to_old_trading(self):
        with patch.object(run_batch,'_read_gcs_text',return_value=config([{'ticker':'CAT'}])) as read:
            with self.assertRaisesRegex(RuntimeError,'ownership_unavailable'):
                run_batch._load_ticker_records(args(config_gcs=MARKET_OWNERSHIP_GCS_URI))
            read.assert_called_once_with(MARKET_OWNERSHIP_GCS_URI)

    def test_malformed_selected_records_never_drop_or_default(self):
        for rows in ([{'ticker':'CAT','owned':False},{'ticker':'CAT','owned':False}], [None], [{'ticker':'','owned':False}]):
            with self.subTest(rows=rows):
                with self.assertRaisesRegex(RuntimeError,'ownership_unavailable'):
                    run_batch._clean_ticker_records(rows)
        with self.assertRaisesRegex(RuntimeError,'ownership_unavailable'):
            run_batch._clean_ticker_records([{'ticker':'CAT'}])
        with patch.object(run_batch,'_read_gcs_text',return_value=json.dumps({'tickers':['CAT'],'ticker_records':'bad'})):
            with self.assertRaisesRegex(RuntimeError,'ticker_records must be a list'):
                run_batch._load_ticker_records(args())

    def test_authority_read_error_reaches_caller_before_model_or_gateway(self):
        with patch.object(run_batch,'_read_gcs_text',side_effect=[json.dumps({'tickers':['CAT']}),RuntimeError('market_read_error')]),patch.object(run_batch,'ensure_gateway') as gateway,patch('src.local_runner.adaptive_preflight.check') as preflight,patch.object(run_batch,'_run_batch') as pipeline:
            with self.assertRaisesRegex(RuntimeError,'market_read_error'):
                run_batch.main(['--from-gcs','--upload-real'])
            gateway.assert_not_called();preflight.assert_not_called();pipeline.assert_not_called()

if __name__=='__main__':unittest.main()
