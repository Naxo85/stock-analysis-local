from copy import deepcopy
from datetime import datetime, timezone
from dataclasses import replace
import unittest
from stock_analysis.contracts.analysis import AnalysisSheetRecord
from stock_analysis.controller.analysis_sheet import _score_cell, _setup_cell, build_analysis_value_requests
from stock_analysis.controller.global_sheet_sort import _writable_cell
from stock_analysis.controller.sheet_layout import load_market_sheet_layout

def record():
 return AnalysisSheetRecord(ticker='AMD',score=8.5,entry=None,washout=None,entry_stop=None,washout_stop=None,resistance=None,entry_strength=None,washout_strength=None,resistance_strength=None,generated_at=datetime(2026,10,13,tzinfo=timezone.utc),report_url='https://reports.example/?symbol=AMD&format=html',score_background='#D9EAD3',score_note='Cambio de nota +0,5',thesis_score=8.5,setup_score=3.5,thesis_reason='Contrato confirmado',setup_reason='Soporte pendiente')

class ReportLinkPersistenceTest(unittest.TestCase):
 def test_value_rewrite_can_erase_runs_without_erasing_report_link(self):
  r=record(); cell=_score_cell(r,'#FFFFFF',thesis=True)
  cell.pop('textFormatRuns')
  self.assertEqual(cell['userEnteredFormat']['textFormat']['link']['uri'],r.report_url)
  self.assertEqual(cell['userEnteredFormat']['hyperlinkDisplayType'],'LINKED')
  self.assertEqual(cell['userEnteredValue'],{'stringValue':'8,5'})
  self.assertEqual(cell['note'],'Contrato confirmado\nCambio de nota +0,5')
  moved=_writable_cell(cell)
  self.assertEqual(moved['userEnteredFormat'],cell['userEnteredFormat'])
  self.assertEqual(moved['note'],cell['note'])
 def test_legacy_ver_keeps_its_report_and_setup_has_no_link(self):
  r=replace(record(),thesis_score=None,setup_score=None)
  c=_score_cell(r,'#FFFFFF',thesis=True)
  self.assertEqual(c['userEnteredValue'],{'stringValue':'Ver'})
  self.assertEqual(c['userEnteredFormat']['textFormat']['link']['uri'],r.report_url)
  self.assertNotIn('textFormat',_setup_cell(r,'#FFFFFF')['userEnteredFormat'])
 def test_request_mask_publishes_links_and_clears_them_from_other_cells(self):
  l=load_market_sheet_layout(); r=record()
  requests=build_analysis_value_requests(l,{'AMD':r},ticker_rows={t:b['header_row']+i for b in l['blocks'] for i,t in enumerate(b['tickers'])},prices={},allow_missing=True)
  for q in requests:
   fields=q['updateCells']['fields']
   self.assertIn('userEnteredFormat.textFormat.link',fields)
   self.assertIn('userEnteredFormat.hyperlinkDisplayType',fields)
   for row in q['updateCells']['rows']:
    for i,c in enumerate(row['values']):
     if i != 3:
      self.assertNotIn('link',c['userEnteredFormat'].get('textFormat',{}))

if __name__=='__main__': unittest.main()
