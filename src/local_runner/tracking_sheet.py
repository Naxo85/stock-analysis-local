"""Change ticker membership without initializing or clearing the market sheet."""
from copy import deepcopy

from stock_analysis.controller.global_sheet_sort import _writable_cell
from stock_analysis.controller.sheet_layout import column_to_index
from stock_analysis.controller.sheet_structure import desired_tables, _ticker_formula


def _preserved_cell(cell):
    result = _writable_cell(deepcopy(cell))
    borders = cell.get('userEnteredFormat', {}).get('borders')
    if borders is not None:
        result.setdefault('userEnteredFormat', {})['borders'] = deepcopy(borders)
    return result


def preserving_structure_requests(layout, spreadsheet):
    sheet_id = layout['sheet']['sheet_id']
    sheet = next(x for x in spreadsheet['sheets'] if x['properties']['sheetId'] == sheet_id)
    cells = {}
    for grid in sheet.get('data', []):
        for r, row in enumerate(grid.get('rowData', []), grid.get('startRow', 0)):
            for c, cell in enumerate(row.get('values', []), grid.get('startColumn', 0)):
                cells[r, c] = cell
    target = {ticker for block in layout['blocks'] for ticker in block['tickers']}
    live = {}
    order = []
    old_ends = {}
    tables = {table['name']: table for table in sheet.get('tables', [])}
    for block in layout['blocks']:
        table = tables.get(block['table_name'])
        if table is None:
            raise ValueError('tracking_native_table_missing:' + block['table_name'])
        start = column_to_index(block['start_column'])
        width = column_to_index(block['end_column']) + 1 - start
        if (table['range']['startColumnIndex'] != start or
                table['range']['endColumnIndex'] != start + width or
                table['range']['startRowIndex'] != block['header_row'] - 1):
            raise ValueError('tracking_unexpected_table_geometry')
        old_ends[block['id']] = table['range']['endRowIndex']
        # Include a row inserted immediately by Apps Script outside the table.
        for r in range(block['header_row'], sheet['properties']['gridProperties']['rowCount']):
            ticker_cell = cells.get((r, start + layout['table_template']['ticker_column_offset']), {})
            value = ticker_cell.get('effectiveValue', ticker_cell.get('userEnteredValue', {}))
            ticker = value.get('stringValue', '')
            if not ticker:
                if r < table['range']['endRowIndex']:
                    raise ValueError('tracking_missing_live_ticker')
                continue
            if ticker in live:
                raise ValueError('tracking_duplicate_live_ticker:' + ticker)
            live[ticker] = [_preserved_cell(cells.get((r, start + c), {})) for c in range(width)]
            order.append(ticker)
    physical = [ticker for ticker in order if ticker in target]
    physical += [ticker for block in layout['blocks'] for ticker in block['tickers'] if ticker not in live]
    expected = desired_tables(layout)
    geometry_same = all(tables[name]['range'] == item['range'] for name, item in expected.items())
    if set(live) == target and geometry_same:
        # Styling, panel merges and named ranges are outside a shot operation.
        return []
    requests = []
    current_rows = sheet['properties']['gridProperties']['rowCount']
    if layout['sheet']['row_count'] > current_rows:
        requests.append({'updateSheetProperties': {'properties': {
            'sheetId': sheet_id, 'gridProperties': {'rowCount': layout['sheet']['row_count']}},
            'fields': 'gridProperties.rowCount'}})
    offset = 0
    for block in layout['blocks']:
        table = tables[block['table_name']]
        target_range = expected[block['table_name']]['range']
        if table['range'] != target_range:
            requests.append({'updateTable': {'table': {'tableId': table['tableId'], 'range': target_range}, 'fields': 'range'}})
        width = target_range['endColumnIndex'] - target_range['startColumnIndex']
        tickers = physical[offset:offset + len(block['tickers'])]
        offset += len(tickers)
        rows = []
        for ticker in tickers:
            if ticker in live:
                row = live[ticker]
            else:
                # New tickers have no quote/report yet. Existing rows retain
                # every value, note, formula, link and cell format by identity.
                row = [{}, _ticker_formula(layout, ticker), *({} for _ in range(width - 2))]
            rows.append({'values': row})
        end = max(old_ends[block['id']], target_range['endRowIndex'])
        rows.extend({'values': [{} for _ in range(width)]} for _ in range(end - block['header_row'] - len(rows)))
        requests.append({'updateCells': {'range': {
            'sheetId': sheet_id, 'startRowIndex': block['header_row'], 'endRowIndex': end,
            'startColumnIndex': target_range['startColumnIndex'], 'endColumnIndex': target_range['endColumnIndex']},
            'rows': rows, 'fields': 'userEnteredValue,note,textFormatRuns,dataValidation,userEnteredFormat'}})
    return requests
