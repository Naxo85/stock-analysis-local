"""Add Tesis/Setup to Mercado without rebuilding or clearing its body."""
from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path

from stock_analysis.controller.market_sheet import GoogleSheetsRestClient, _google_access_token
from stock_analysis.controller.sheet_layout import (
    load_market_sheet_layout, resolve_balanced_table_geometry,
    validate_market_sheet_layout, build_column_width_apply_requests,
    build_table_border_apply_requests,
)
from stock_analysis.controller.global_sheet_sort import build_global_sort_control_requests


def upgrade_layout(old: dict) -> dict:
    layout = deepcopy(old)
    if layout['table_template']['headers'][-2:] == ['Tesis', 'Setup']:
        return layout
    if layout['sheet']['column_count'] != 36 or layout['table_template']['headers'][-1] != 'Nota':
        raise ValueError('Expected the 36-column Nota layout')
    layout['schema_version'] = 5
    layout['sheet']['column_count'] = 38
    layout['table_template']['headers'][-1:] = ['Tesis', 'Setup']
    layout['table_template']['column_widths_px'].append(64)
    layout['blocks'][0]['end_column'] = 'W'
    layout['blocks'][1].update(start_column='Y', end_column='AL')
    for spacer in layout['spacer_columns']:
        if spacer['column'] == 'W':
            spacer['column'] = 'X'
    for section, key in [('data_refresh', 'deferred_columns'), ('analysis_sync', 'automatic_columns')]:
        columns = layout[section][key]
        columns[columns.index('Nota'):] = ['Tesis', 'Setup']
    layout['global_sort']['default'] = 'Tesis'
    layout['global_sort']['options'][0]['label'] = 'Tesis'
    layout['global_sort']['options'].insert(1, {'label': 'Setup', 'field': 'setup_score', 'direction': 'desc'})
    resolve_balanced_table_geometry(layout)
    validate_market_sheet_layout(layout)
    return layout


def migration_requests(old: dict, new: dict, sheet: dict, selection: str) -> list[dict]:
    sid = new['sheet']['sheet_id']
    if sheet['properties']['gridProperties']['columnCount'] != 36:
        raise ValueError('Live grid must still have 36 columns; inspect before retrying')
    tables = {table['name']: table for table in sheet.get('tables', [])}
    requests = [
        {'insertDimension': {'range': {'sheetId': sid, 'dimension': 'COLUMNS', 'startIndex': 22, 'endIndex': 23}, 'inheritFromBefore': True}},
        {'appendDimension': {'sheetId': sid, 'dimension': 'COLUMNS', 'length': 1}},
    ]
    for index, block in enumerate(new['blocks']):
        table = tables[block['table_name']]
        expected_start = 9 if index == 0 else 23
        if table['range']['startColumnIndex'] != expected_start or table['range']['endColumnIndex'] != expected_start + 13:
            raise ValueError('Unexpected live table geometry')
        start = 9 if index == 0 else 24
        table_range = dict(table['range'], startColumnIndex=start, endColumnIndex=start + 14)
        columns = deepcopy(table.get('columnProperties', []))
        if len(columns) != 13:
            raise ValueError('Expected 13 native table columns')
        columns[-1]['columnName'] = 'Tesis'
        columns.append({'columnIndex': 13, 'columnName': 'Setup'})
        requests.append({'updateTable': {'table': {'tableId': table['tableId'], 'range': table_range, 'columnProperties': columns}, 'fields': 'range,columnProperties'}})
        score_col = start + 12
        body_end = block['header_row'] + len(block['tickers'])
        requests.append({'copyPaste': {'source': {'sheetId': sid, 'startRowIndex': 2, 'endRowIndex': body_end, 'startColumnIndex': score_col, 'endColumnIndex': score_col + 1}, 'destination': {'sheetId': sid, 'startRowIndex': 2, 'endRowIndex': body_end, 'startColumnIndex': score_col + 1, 'endColumnIndex': score_col + 2}, 'pasteType': 'PASTE_FORMAT'}})
        requests.append({'updateCells': {'start': {'sheetId': sid, 'rowIndex': 2, 'columnIndex': score_col}, 'rows': [{'values': [{'userEnteredValue': {'stringValue': 'Tesis'}, 'note': 'Tesis /10: narrativa, catalizadores, evidencia y riesgos específicos.'}, {'userEnteredValue': {'stringValue': 'Setup'}, 'note': 'Setup /10: entrada propuesta, asimetría y situación técnica actual.'}]}], 'fields': 'userEnteredValue,note'}})
    requests.extend(build_column_width_apply_requests(sid, new))
    requests.extend(build_table_border_apply_requests(sid, new))
    requests.extend(build_global_sort_control_requests(new, 'Tesis' if selection == 'Nota' else selection))
    return requests


def repair_table_ranges(layout: dict, client: GoogleSheetsRestClient) -> None:
    from stock_analysis.controller.sheet_structure import desired_tables
    sid = layout['sheet']['sheet_id']
    spreadsheet_id = layout['spreadsheet']['spreadsheet_id']
    state = client.get_spreadsheet(spreadsheet_id)
    sheet = next(s for s in state['sheets'] if s['properties']['sheetId'] == sid)
    desired = desired_tables(layout)
    active_ranges = [f"'Mercado'!{b['start_column']}{b['header_row'] + 1}:{b['end_column']}{b['header_row'] + len(b['tickers'])}" for b in layout['blocks']]
    active = client.batch_get_values(spreadsheet_id, active_ranges, value_render_option='UNFORMATTED_VALUE')
    tickers = [str(row[1]) for block in active for row in block.get('values', []) if len(row) > 1]
    if len(tickers) != len(set(tickers)):
        raise ValueError('Active body has duplicate tickers')
    requests = []
    for table in sheet.get('tables', []):
        expected = desired.get(table['name'], {}).get('range')
        if not expected or table['range'] == expected:
            continue
        actual = table['range']
        if any(actual.get(key) != expected.get(key) for key in ('sheetId', 'startRowIndex', 'startColumnIndex', 'endColumnIndex')) or actual['endRowIndex'] != expected['endRowIndex'] + 1:
            raise ValueError('Unexpected table drift; refusing automatic repair')
        from stock_analysis.controller.sheet_layout import index_to_column
        tail = dict(expected, startRowIndex=expected['endRowIndex'], endRowIndex=actual['endRowIndex'])
        a1 = f"'Mercado'!{index_to_column(tail['startColumnIndex'])}{tail['startRowIndex'] + 1}:{index_to_column(tail['endColumnIndex'] - 1)}{tail['endRowIndex']}"
        values = client.batch_get_values(spreadsheet_id, [a1], value_render_option='UNFORMATTED_VALUE')[0].get('values', [])
        if values and (len(values[0]) < 2 or str(values[0][1]) not in tickers):
            raise ValueError('Tail is not a duplicate of an active ticker')
        requests.append({'updateCells': {'range': tail, 'fields': 'userEnteredValue,note,textFormatRuns,userEnteredFormat'}})
        requests.append({'updateTable': {'table': {'tableId': table['tableId'], 'range': expected}, 'fields': 'range'}})
    if requests:
        client.batch_update(spreadsheet_id, requests)
    print(f'REPAIRED requests={len(requests)}')


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--repair-ranges', action='store_true')
    parser.add_argument('--bucket', default='stock-analysis-system-naxo85')
    args = parser.parse_args()
    if args.repair_ranges:
        layout = load_market_sheet_layout()
        repair_table_ranges(layout, GoogleSheetsRestClient(service_account=layout['spreadsheet'].get('service_account')))
        return
    from google.cloud import storage
    from google.oauth2.credentials import Credentials
    storage_client = storage.Client(project='recipe-generator-429817', credentials=Credentials(_google_access_token(None)))
    bucket = storage_client.bucket(args.bucket)
    blob = bucket.blob('runtime/config/market_sheet_layout.json')
    blob.reload()
    generation = blob.generation
    old = json.loads(blob.download_as_bytes(if_generation_match=generation))
    if old['table_template']['headers'][-2:] == ['Tesis', 'Setup']:
        print('ALREADY_MIGRATED')
        return
    new = upgrade_layout(old)
    client = GoogleSheetsRestClient(service_account=new['spreadsheet'].get('service_account'))
    spreadsheet_id = new['spreadsheet']['spreadsheet_id']
    metadata = client.get_spreadsheet(spreadsheet_id)
    sheet_meta = next(s for s in metadata['sheets'] if s['properties']['sheetId'] == new['sheet']['sheet_id'])
    title = sheet_meta['properties']['title']
    state = client.get_spreadsheet(spreadsheet_id, include_grid_data=True, ranges=[f"'{title}'!A1:AJ{new['sheet']['row_count']}"])
    sheet = next(s for s in state['sheets'] if s['properties']['sheetId'] == new['sheet']['sheet_id'])
    # Native table metadata can be absent from a range-limited grid response.
    sheet['tables'] = sheet_meta.get('tables', [])
    selection = client.batch_get_values(spreadsheet_id, [f"'{title}'!C10"], value_render_option='UNFORMATTED_VALUE')[0].get('values', [['Nota']])[0][0]
    requests = migration_requests(old, new, sheet, str(selection))
    backup = Path('artifacts') / ('score-migration-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
    backup.mkdir(parents=True, exist_ok=False)
    for name, value in [('layout-before', old), ('layout-after', new), ('sheet-before', state), ('requests', requests)]:
        (backup / f'{name}.json').write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'PLAN requests={len(requests)} tickers={sum(len(g["tickers"]) for g in old["groups"])} backup={backup}', flush=True)
    if not args.apply:
        return
    # Caller pauses the two scheduler jobs for this short, backed-up migration.
    client.batch_update(spreadsheet_id, requests)
    blob.upload_from_string(json.dumps(new, ensure_ascii=False, indent=2), content_type='application/json', if_generation_match=generation)
    from stock_analysis.analysis_worker.run_sync import run
    from stock_analysis.analysis_worker.reports import GcsAnalysisReportStore
    result = run(publish=True, force=True, bucket_name=args.bucket, sheets_client=client, layout=new, store=GcsAnalysisReportStore(args.bucket, storage_client=storage_client))
    print('APPLIED ' + json.dumps(result), flush=True)


if __name__ == '__main__':
    main()
