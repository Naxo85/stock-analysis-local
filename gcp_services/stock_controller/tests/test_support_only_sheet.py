from copy import deepcopy
import unittest
from test_analysis_sheet import LAYOUT, record
from test_analysis_reports import report_payload
from stock_analysis.analysis_worker.reports import parse_analysis_report
from stock_analysis.analysis_worker.run_sync import effective_sync_version
from stock_analysis.controller.analysis_sheet import build_analysis_value_requests, build_strength_border_requests, build_live_proximity_background_requests
from stock_analysis.controller.sheet_layout import load_market_sheet_layout, build_column_width_apply_requests

class SupportOnlyTest(unittest.TestCase):
 def test_blank_resistance_preserves_supports_score_positions_and_links(self):
  old=deepcopy(LAYOUT);old['table_template']['headers']=['Tesis','Setup']
  new=deepcopy(old);new['table_template']['show_resistance']=False
  rows={'AAA':3,'BBB':4};records={t:record(t,90,95) for t in rows}
  kw=dict(ticker_rows=rows,prices={'AAA':120.5,'BBB':120.5})
  a=build_analysis_value_requests(old,records,**kw);b=build_analysis_value_requests(new,records,**kw)
  self.assertEqual(a[0]['updateCells']['range'],b[0]['updateCells']['range'])
  for before,after in zip(a[0]['updateCells']['rows'],b[0]['updateCells']['rows']):
   for i in (0,1,3,4):self.assertEqual(before['values'][i],after['values'][i])
   self.assertEqual(after['values'][2]['userEnteredValue'],{'stringValue':''})
   self.assertFalse(after['values'][2].get('note'))
  borders=build_strength_border_requests(new,records,ticker_rows=rows)
  self.assertEqual(len(borders),2)
  for request in borders:self.assertNotEqual(request['updateBorders']['range']['startColumnIndex'],14)
 def test_hidden_columns_are_derived_not_shifted(self):
  layout=load_market_sheet_layout();layout['table_template']['show_resistance']=False
  requests=build_column_width_apply_requests(layout['sheet']['sheet_id'],layout)
  hidden={q['updateDimensionProperties']['range']['startIndex'] for q in requests
          if q['updateDimensionProperties']['properties'].get('hiddenByUser')}
  self.assertTrue({20,35}<=hidden)
  old=deepcopy(layout);old['table_template']['show_resistance']=True
  self.assertNotEqual(effective_sync_version('same',old),effective_sync_version('same',layout))
 def test_new_contract_accepts_absent_resistance_but_keeps_support_checks(self):
  p=report_payload();p['report_schema_version']=7
  p['semantic_report']={'data':{'metadata':{'source_contract_revision':35}}}
  for key in ('entry','washout'):
   p['plan'].update({key+'_strength_score':50,key+'_strength_category':'moderado',key+'_strength_factors':'observations',
    key+'_strength_breakdown':dict(estructura=10,volumen=10,opciones=10,confluencia=10,durabilidad=10)})
  r=parse_analysis_report('RKLB',p,report_url_template='{ticker}')
  self.assertIsNone(r.resistance)
  old=deepcopy(p);old['semantic_report']['data']['metadata']['source_contract_revision']=34
  with self.assertRaises(ValueError):parse_analysis_report('RKLB',old,report_url_template='{ticker}')
  p['plan']['entry_strength_breakdown']['volumen']=0
  with self.assertRaises(ValueError):parse_analysis_report('RKLB',p,report_url_template='{ticker}')
