import copy
import json
import unittest
from unittest.mock import patch

from src.local_runner import manage_market_tracking as tracking
from src.local_runner.tracking_sheet import preserving_structure_requests
from stock_analysis.controller.sheet_structure import desired_tables, plan_structure_changes, build_structure_requests
from stock_analysis.controller.sheet_layout import column_to_index


def populated_state(layout):
    sid=layout['sheet']['sheet_id']
    rows=[[{} for _ in range(38)] for _ in range(layout['sheet']['row_count'])]
    for block in layout['blocks']:
        start=column_to_index(block['start_column'])
        for r,ticker in enumerate(block['tickers'],block['header_row']):
            rows[r][start+1]={'userEnteredValue':{'stringValue':ticker},'effectiveValue':{'stringValue':ticker},
                'note':'earnings', 'userEnteredFormat':{'borders':{'top':{'style':'SOLID_THICK'}}}}
            rows[r][start+2]={'userEnteredValue':{'numberValue':100+r},'note':'dated quote'}
            rows[r][start+12]={'userEnteredValue':{'stringValue':'8,5'},'userEnteredFormat':{
                'textFormat':{'link':{'uri':'https://example.test/report/'+ticker}}}}
    rows[1][0]={'userEnteredValue':{'stringValue':'Risk panel'}}
    rows[1][2]={'userEnteredValue':{'stringValue':'Caída QQQ'}}
    return {'sheets':[{'properties':{'sheetId':sid,'gridProperties':{'rowCount':len(rows),'columnCount':38}},
        'tables':[dict(tableId=str(i),name=name,range=copy.deepcopy(t['range']),rowsProperties=t['rowsProperties'])
                  for i,(name,t) in enumerate(desired_tables(layout).items())],
        'data':[{'rowData':[{'values':r} for r in rows]}],
        'merges':[{'sheetId':sid,'startRowIndex':1,'endRowIndex':2,'startColumnIndex':2,'endColumnIndex':5}]}]}


class TrackingSheetPreservationTests(unittest.TestCase):
    def setUp(self):
        self.layout=tracking._resolve_layout_payload(json.loads(tracking.LAYOUT_PATH.read_text(encoding='utf-8')))
        self.before=populated_state(self.layout)

    def test_reproduces_old_qqq_merge_drift_triggering_whole_sheet_clear(self):
        changes=plan_structure_changes(self.layout,self.before)
        self.assertTrue(any(c['action']=='unmerge' and c['range']['startColumnIndex']==2 for c in changes))
        old=build_structure_requests(self.layout,changes)
        self.assertTrue(any('updateCells' in r and not r['updateCells'].get('rows')
            and r['updateCells']['range']['startColumnIndex']==0 for r in old))
        self.assertEqual(preserving_structure_requests(self.layout,self.before),[])

    def test_ordinary_shots_ignore_style_and_named_range_drift(self):
        self.before['sheets'][0]['tables'][0]['rowsProperties']={}
        self.before['namedRanges']=[]
        self.assertEqual(preserving_structure_requests(self.layout,self.before),[])

    def test_add_keeps_existing_financial_cells_notes_links_and_borders(self):
        raw=json.loads(tracking.LAYOUT_PATH.read_text(encoding='utf-8'))
        raw['groups'][0]['tickers'].append('NEW')
        after=tracking._resolve_layout_payload(raw)
        requests=preserving_structure_requests(after,self.before)
        original=self.before['sheets'][0]['data'][0]['rowData']
        known={}
        for block in self.layout['blocks']:
            start=column_to_index(block['start_column'])
            for r,ticker in enumerate(block['tickers'],block['header_row']):
                known[ticker]=original[r]['values'][start:start+14]
        observed={}
        for request in requests:
            if 'updateCells' not in request:continue
            write=request['updateCells']
            self.assertIn(write['range']['startColumnIndex'],[9,24])
            self.assertGreaterEqual(write['range']['startRowIndex'],3)
            self.assertTrue(write['rows'])
            for row in write['rows']:
                cells=row['values']
                ticker=cells[1].get('userEnteredValue',{}).get('stringValue')
                if ticker:observed[ticker]=cells
        self.assertEqual(set(observed),set(known))
        for ticker,cells in observed.items():
            self.assertEqual(cells[2],known[ticker][2])
            self.assertEqual(cells[1]['note'],'earnings')
            self.assertEqual(cells[1]['userEnteredFormat']['borders'],known[ticker][1]['userEnteredFormat']['borders'])
            self.assertEqual(cells[12]['textFormatRuns'][0]['format']['link']['uri'],'https://example.test/report/'+ticker)

    def test_remove_only_clears_vacated_table_row(self):
        raw=json.loads(tracking.LAYOUT_PATH.read_text(encoding='utf-8'))
        removed=raw['groups'][0]['tickers'].pop()
        requests=preserving_structure_requests(tracking._resolve_layout_payload(raw),self.before)
        writes=[r['updateCells'] for r in requests if 'updateCells' in r]
        self.assertEqual(len(writes),2)
        values=[row['values'] for w in writes for row in w['rows']]
        names=[row[1].get('userEnteredValue',{}).get('stringValue') for row in values]
        self.assertNotIn(removed,names)
        self.assertEqual(sum(all(not c for c in row) for row in values),1)


if __name__=='__main__': unittest.main()
