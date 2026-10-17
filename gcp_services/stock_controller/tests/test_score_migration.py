from copy import deepcopy
import unittest
from stock_analysis.controller.sheet_layout import load_market_sheet_layout
from stock_analysis.controller.migrate_scores import upgrade_layout, migration_requests


class ScoreMigrationTest(unittest.TestCase):
    def setUp(self):
        self.new = load_market_sheet_layout()
        self.old = deepcopy(self.new)
        self.old['schema_version'] = 4
        self.old['sheet']['column_count'] = 36
        self.old['table_template']['headers'][-2:] = ['Nota']
        self.old['table_template']['column_widths_px'].pop()
        self.old['blocks'][0]['end_column'] = 'V'
        self.old['blocks'][1].update(start_column='X', end_column='AJ')
        self.old['spacer_columns'][-1]['column'] = 'W'
        self.old['global_sort']['default'] = 'Nota'
        self.old['global_sort']['options'][0]['label'] = 'Nota'
        self.old['global_sort']['options'].pop(1)
        self.old['data_refresh']['deferred_columns'][-2:] = ['Nota']
        self.old['analysis_sync']['automatic_columns'][-2:] = ['Nota']

    def test_upgrade_preserves_live_groups_and_is_idempotent(self):
        result = upgrade_layout(self.old)
        self.assertEqual(result, self.new)
        self.assertEqual(result['groups'], self.old['groups'])
        self.assertEqual(upgrade_layout(result), result)
        self.assertEqual(self.old['sheet']['column_count'], 36)

    def test_migration_only_inserts_columns_and_updates_headers_not_body_values(self):
        sheet = {'properties': {'gridProperties': {'columnCount': 36}}, 'tables': []}
        for index, block in enumerate(self.old['blocks']):
            start = 9 if index == 0 else 23
            sheet['tables'].append({'name': block['table_name'], 'tableId': str(index), 'range': {'sheetId': self.new['sheet']['sheet_id'], 'startRowIndex': 2, 'endRowIndex': 26, 'startColumnIndex': start, 'endColumnIndex': start + 13}, 'columnProperties': [{'columnIndex': i, 'columnName': name} for i, name in enumerate(self.old['table_template']['headers'])]})
        requests = migration_requests(self.old, self.new, sheet, 'Fuerza')
        self.assertEqual(requests[0]['insertDimension']['range']['startIndex'], 22)
        self.assertEqual(requests[1]['appendDimension']['length'], 1)
        for req in requests:
            if 'updateCells' in req:
                self.assertIn(req['updateCells']['start']['rowIndex'], (2, 8, 9))
        tables = [r['updateTable']['table'] for r in requests if 'updateTable' in r]
        self.assertEqual([t['range']['endColumnIndex'] for t in tables], [23, 38])
        self.assertEqual(tables[1]['columnProperties'][-1]['columnName'], 'Setup')
        sheet['properties']['gridProperties']['columnCount'] = 38
        with self.assertRaises(ValueError):
            migration_requests(self.old, self.new, sheet, 'Tesis')
