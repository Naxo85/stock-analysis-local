"""Both initial projection and live quotes obey the same assessed extent."""
from copy import deepcopy
from dataclasses import replace
import unittest
from unittest.mock import patch,Mock
from stock_analysis.contracts.analysis import PriceRange,support_validity_floor
from stock_analysis.controller.analysis_sheet import build_analysis_value_requests,build_live_proximity_background_requests,_proximity_background
from stock_analysis.analysis_worker.reports import parse_analysis_report,load_support_validity
from test_analysis_sheet import LAYOUT,record
from test_analysis_reports import report_payload

def extent(lower=98.8,zone=None):
 return {'lower_bound':lower,'range':zone or {'lower':100,'upper':102},
         'reason':'Observed buying structure; estimate.', 'assessed_at':'2026-10-14T12:00:00+00:00'}

class SupportValidityTest(unittest.TestCase):
 def test_threshold_boundaries_and_unknown_without_past_percent_fallback(self):
  z=PriceRange(100,102);v=extent();rules=LAYOUT['format_rules']['entry_proximity']
  for price,green in [(102.1,False),(102,True),(100,True),(99,True),(98.8,True),(98.79,False),(80,False)]:
   self.assertEqual(_proximity_background(z,price,'#FFFFFF',rules,support_validity=v),'#00FF00' if green else '#FFFFFF')
  for price in [99,98.5,98.4,80]:
   self.assertEqual(_proximity_background(z,price,'#FFFFFF',rules),'#FFFFFF')
  for missing in [None,False,float('nan'),float('inf')]:
   self.assertEqual(_proximity_background(z,missing,'#FFFFFF',rules,support_validity=v),'#FFFFFF')
 def test_bad_or_different_zone_and_nonfinite_floor_are_unknown(self):
  z=PriceRange(100,102)
  for bad in [extent(105),extent(False),extent(float('nan')),extent(float('inf')),extent(98.8,{'lower':99,'upper':102}),{'lower_bound':98.8}]:
   self.assertIsNone(support_validity_floor(z,bad))
 def test_live_quotes_extend_green_and_remove_it_two_hours_later(self):
  levels={'AAA':('100,0-102,0','',''),'BBB':('100,0-102,0','','')}
  v={t:{'entry':extent()} for t in levels}
  q=build_live_proximity_background_requests(LAYOUT,levels,ticker_rows={'AAA':3,'BBB':4},prices={'AAA':99,'BBB':98},support_validity=v)
  colors=[x['values'][0]['userEnteredFormat']['backgroundColorStyle']['rgbColor'] for x in q[0]['updateCells']['rows']]
  self.assertEqual(colors,[{'red':0,'green':1,'blue':0},{'red':1,'green':1,'blue':1}])
  self.assertEqual(q[0]['updateCells']['fields'],'userEnteredFormat.backgroundColorStyle')
 def test_one_decimal_sheet_display_keeps_exact_extent_binding(self):
  levels={'AAA':('34,9-35,1','',''),'BBB':('35,0-35,2','','')}
  v={t:{'entry':extent(34.4,{'lower':34.85,'upper':35.15})} for t in levels}
  q=build_live_proximity_background_requests(LAYOUT,levels,ticker_rows={'AAA':3,'BBB':4},prices={'AAA':34.5,'BBB':34.5},support_validity=v)
  colors=[x['values'][0]['userEnteredFormat']['backgroundColorStyle']['rgbColor'] for x in q[0]['updateCells']['rows']]
  self.assertEqual(colors,[{'red':0,'green':1,'blue':0},{'red':1,'green':1,'blue':1}])
 def test_initial_projection_keeps_ranges_notes_scores_links_and_visibility(self):
  r=record('AAA',90,90);z={'lower':r.entry.lower,'upper':r.entry.upper}
  v=extent(r.entry.lower-2,z);new=replace(r,entry_support_validity=v)
  kw=dict(ticker_rows={'AAA':3,'BBB':4},prices={'AAA':r.entry.lower-1,'BBB':100})
  a=build_analysis_value_requests(LAYOUT,{'AAA':r,'BBB':record('BBB',60,60)},**kw)
  b=build_analysis_value_requests(LAYOUT,{'AAA':new,'BBB':record('BBB',60,60)},**kw)
  old=a[0]['updateCells']['rows'][0]['values'];after=b[0]['updateCells']['rows'][0]['values']
  self.assertEqual(old[0]['userEnteredValue'],after[0]['userEnteredValue'])
  for i in (1,2,3):self.assertEqual(old[i],after[i])
  self.assertIn('2026-10-14',after[0]['note'])
 def test_parser_uses_exact_typed_mirror_and_does_not_parse_a_reason(self):
  p=report_payload();p['semantic_report']={'data':{'plan':{'entry':{'range':p['plan']['entry']}}}}
  z=p['plan']['entry'];v=extent(z['lower']-1,z)
  p['plan']['entry_support_validity']=deepcopy(v)
  p['semantic_report']['data']['plan']['entry']['support_validity']=deepcopy(v)
  r=parse_analysis_report('RKLB',p,report_url_template='{ticker}')
  self.assertIsNotNone(r.entry_support_validity)
  p['plan']['entry_support_validity']['lower_bound']-=1
  r=parse_analysis_report('RKLB',p,report_url_template='{ticker}')
  self.assertIsNone(r.entry_support_validity)
 def test_projection_read_is_one_small_bounded_gcs_read(self):
  blob=Mock();blob.download_as_bytes.return_value=b'{"support_validity":{"AAA":{"entry":null}}}'
  with patch('stock_analysis.analysis_worker.reports.storage.Client') as client:
   client.return_value.bucket.return_value.blob.return_value=blob
   self.assertEqual(load_support_validity('bucket','runtime/reports'),{'AAA':{'entry':None}})
  blob.download_as_bytes.assert_called_once_with(timeout=10,retry=None)
