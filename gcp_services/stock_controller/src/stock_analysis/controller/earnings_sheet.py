"""Earnings borders and notes, applied after sorting and base table borders."""
import re

from stock_analysis.earnings_calendar import earnings_alert
from stock_analysis.controller.sheet_layout import column_to_index, _rgb
from stock_analysis.controller.sheet_tickers import configured_ticker_rows, ordered_block_tickers


def ticker_notes(layout, spreadsheet):
    notes = {}
    offset = layout['table_template'].get('ticker_column_offset', 0)
    columns = {column_to_index(block['start_column']) for block in layout['blocks']}
    for sheet in spreadsheet.get('sheets', []):
        if sheet.get('properties', {}).get('sheetId') != layout['sheet']['sheet_id']:
            continue
        for grid in sheet.get('data', []):
            if grid.get('startColumn', 0) not in columns:
                continue
            for row in grid.get('rowData', []):
                cells = row.get('values', [])
                if len(cells) > offset:
                    cell = cells[offset]
                    symbol = cell.get('effectiveValue', {}).get('stringValue')
                    if symbol:
                        notes[symbol] = cell.get('note', '')
    return notes


def _note(previous, alert):
    # Remove only this renderer's three-line calendar block, preserving other notes.
    remaining = previous or ''
    match = re.search(r'(?m)^Resultados: [^\n]*\nFuente del calendario: [^\n]*\nFecha del resumen: [^\n]*', remaining)
    if match:
        before, after = remaining[:match.start()], remaining[match.end():]
        if before.endswith('\n\n'):
            before = before[:-2]
        remaining = before + after
    if not alert:
        return remaining
    date_label = '/'.join(reversed(alert['date'].split('-')))
    hour = ' · ' + alert['hour_label'] if alert['hour_label'] else ''
    block = (f"Resultados: {date_label} · {alert['label']}{hour}\n"
             f"Fuente del calendario: {alert.get('source') or 'N/D'}\n"
             f"Fecha del resumen: {alert.get('as_of') or 'N/D'}")
    return '\n\n'.join(part for part in (remaining, block) if part)


def build_earnings_requests(layout, events, *, ticker_rows=None, notes=None, now=None):
    rows = ticker_rows if ticker_rows is not None else configured_ticker_rows(layout)
    notes = notes or {}
    clear, active = [], []
    offset = layout['table_template'].get('ticker_column_offset', 0)
    base_line = {'style': 'SOLID_MEDIUM', 'colorStyle': {'rgbColor': _rgb('#5F6B73')}}
    for block in layout['blocks']:
        col = column_to_index(block['start_column']) + offset
        physical = ordered_block_tickers(block, rows)
        for symbol in physical:
            row = rows[symbol]
            target = {'sheetId': layout['sheet']['sheet_id'], 'startRowIndex': row, 'endRowIndex': row + 1,
                      'startColumnIndex': col, 'endColumnIndex': col + 1}
            # Clear all previous earnings edges first; never touch fills, links or values.
            borders = {side: {'style': 'NONE'} for side in ('top', 'bottom', 'left', 'right')}
            if symbol == physical[-1]:
                borders['bottom'] = base_line
            if offset == 0:
                borders['left'] = base_line
            if offset in layout['table_template'].get('divider_after_offsets', []):
                borders['right'] = base_line
            clear.append({'updateBorders': {'range': target, **borders}})
            alert = earnings_alert(events.get(symbol), now=now)
            note = _note(notes.get(symbol, ''), alert)
            if note != notes.get(symbol, ''):
                clear.append({'repeatCell': {'range': target, 'cell': {'note': note}, 'fields': 'note'}})
            if alert:
                line = {'style': 'SOLID_THICK',
                        'colorStyle': {'rgbColor': _rgb('#D93025' if alert['severity'] == 'red' else '#F29900')}}
                active.append((alert['severity'] == 'red', {'updateBorders': {'range': target,
                               **{side: line for side in ('top', 'bottom', 'left', 'right')}}}))
    # Red wins when adjacent orange/red tickers share an edge.
    return clear + [request for _, request in sorted(active, key=lambda item: item[0])]
