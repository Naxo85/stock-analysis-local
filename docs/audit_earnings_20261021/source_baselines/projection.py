"""Read-only mobile projection of published data. Never generates investment rules."""
from __future__ import annotations
from publication_contract import attempt_notice

from datetime import datetime, timezone
import hashlib
import math
import re
from changes import material_changes
from market_session import mobile_schedule


def number(value):
    if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value):
        return value
    return None


def text(value):
    return re.sub(r'\[([^\]]+)\]\([^)]*\)', r'\1', str(value or '')).replace('**', '').strip()


def sheet_cells(payload):
    cells = {}
    for sheet in payload.get('sheets', []):
        for grid in sheet.get('data', []):
            for r, row in enumerate(grid.get('rowData', []), grid.get('startRow', 0)):
                for c, value in enumerate(row.get('values', []), grid.get('startColumn', 0)):
                    cells[(r, c)] = value
    return cells


def value(cell):
    data = cell.get('effectiveValue', {})
    return data.get('numberValue', data.get('stringValue', cell.get('formattedValue')))


def column_index(label):
    result = 0
    for char in label:
        result = result * 26 + ord(char.upper()) - 64
    return result - 1


def percent_label(label):
    found = re.search(r'([-+]?\d+(?:[.,]\d+)?)\s*%', str(label or ''))
    return float(found[1].replace(',', '.')) / 100 if found else None


def select_report(latest, mirror):
    valid = latest if latest and latest.get('analysis_status') == 'ok' else mirror
    if not valid or valid.get('analysis_status') != 'ok':
        valid = None
    return valid, ((latest or {}).get('latest_attempt') or {}).get('status', (latest or {}).get('analysis_status', 'unavailable'))


def project(layout, portfolio, quotes, sheet, latest_reports, mirrors, warnings, histories=None):
    histories = histories or {}
    cells = sheet_cells(sheet)
    metrics = {}
    fields = ['price', 'day_change', 'strength', 'return_5d', 'return_20d', 'volatility', 'drawdown']
    for block in layout['blocks']:
        col = column_index(block['start_column'])
        for row in range(block['header_row'], max([r for r, _ in cells], default=0) + 1):
            symbol = value(cells.get((row, col + 1), {}))
            if isinstance(symbol, str):
                metrics[symbol] = {name: number(value(cells.get((row, col + 2 + index), {}))) for index, name in enumerate(fields)}
    stocks, changes, news = [], [], []
    news_by_article = {}
    quote_map = quotes.get('quotes', {})
    for group in layout['groups']:
        for symbol in group['tickers']:
            latest = latest_reports.get(symbol)
            report, attempt_status = select_report(latest, mirrors.get(symbol))
            quote = quote_map.get(symbol, {})
            plan = (report or {}).get('plan') or {}
            decision = (report or {}).get('decision') or {}
            stock = {
                'symbol': symbol, 'group': group.get('label', group['id']), 'group_id':group['id'],
                'benchmark': group.get('benchmark'), 'shots': portfolio.get('positions', {}).get(symbol, 0),
                **metrics.get(symbol, {}),
                'quote_at': quote.get('observed_at'), 'quote_source': quote.get('source'),
                'analysis_at': (report or {}).get('generated_at'), 'analysis_status':'ok' if report else 'unavailable',
                'last_attempt_at': ((latest or {}).get('latest_attempt') or {}).get('at', (latest or {}).get('generated_at')), 'last_attempt_status': attempt_status,
                'latest_attempt': (latest or {}).get('latest_attempt'),
                'publication_version': (latest or {}).get('publication_version'),
                'attempt_notice': attempt_notice((latest or {}).get('latest_attempt'), has_report=bool(report)),
                'decision': {k: decision.get(k) for k in ['thesis_score','setup_score','score','score_basis','narrative']},
                'plan': {k:v for k,v in plan.items() if k.endswith('_score') or k.endswith('_category') or k in ['entry','ambitious_entry','resistance','management_stop','structural_stop','target']},
                'next_event': (report or {}).get('next_event'),
            }
            # The persistent quote cache supplies a verifiable observation time.
            stock['price'] = number(quote.get('price'))
            stock['day_change'] = number(quote.get('day_change'))
            stocks.append(stock)
            if not report:
                continue
            at = report.get('generated_at')
            for index, item in enumerate(material_changes(report, histories.get(symbol))):
                changes.append({**item, 'id': f"{symbol}:{at}:{item['kind']}:{index}", 'symbol':symbol,
                                'title':text(item['title']), 'detail':text(item['detail']),
                                'last_attempt_status':attempt_status})
            source = report.get('ibkr_recent_news') or {}
            for item in source.get('items', []):
                title = text(item.get('headline') or item.get('title'))
                if not title:
                    continue
                provider = item.get('providerCode') or source.get('providerCode') or 'IBKR'
                key = f"{provider}:{item.get('articleId') or title}"
                if key in news_by_article:
                    if symbol not in news_by_article[key]['symbols']:
                        news_by_article[key]['symbols'].append(symbol)
                    continue
                entry = {'id': hashlib.sha256(key.encode()).hexdigest()[:20], 'symbol':symbol, 'symbols':[symbol], 'title':title, 'at':item.get('time') or item.get('published_at') or item.get('timestamp') or source.get('generated_at'), 'provider':provider, 'analysis_at':at}
                news_by_article[key] = entry
                news.append(entry)
    panel = layout['general_panel']
    panel_row = panel['start_row'] - 1
    panel_col = column_index(panel['column'])
    lines = {name: cells.get((panel_row+i, panel_col), {}) for i,name in enumerate(panel['lines'])}
    risk = text(value(lines.get('risk_regime', {})))
    risk_match = re.search(r'(\d+)\s*/\s*100',risk)
    vxn_match = re.search(r'VXN:\s*([0-9]+(?:[.,][0-9]+)?)',lines.get('vxn_regime', {}).get('note',''))
    groups = []
    # Identify summary by ETF, independent of its physical daily order.
    group_config = {g['benchmark']:g for g in layout['groups'] if g.get('benchmark')}
    for row in range(max([r for r,_ in cells], default=0)+1):
        benchmark = value(cells.get((row,2),{}))
        if benchmark in group_config:
            group = group_config[benchmark]
            groups.append({'label':group['label'], 'benchmark':benchmark, 'day_change':number(value(cells.get((row,3),{}))), 'return_20d':number(value(cells.get((row,4),{}))), 'drawdown':number(value(cells.get((row,5),{})))})
    groups.sort(key=lambda g: (g['day_change'] is not None, g['day_change'] or 0), reverse=True)
    qqq = quote_map.get('QQQ', {})
    # The controller owns this calculation; the app reads the same typed cells.
    qqq_pullback = None
    pullback_cell = cells.get((1, 2), {})
    compact_pullback = str(pullback_cell.get('formattedValue', '')).startswith('Caída QQQ:') or (
        value(pullback_cell) == 'N/D' and 'QQQ: distancia al máximo relativo' in pullback_cell.get('note', '')
    )
    if value(pullback_cell) == 'QQQ · RETROCESO ACTUAL' or compact_pullback:
        drawdown_cell = pullback_cell if compact_pullback else cells.get((2, 2), {})
        qqq_pullback = {
            'drawdown': number(value(drawdown_cell)),
            'state': text(value(cells.get((2, 5), {}))) or ('Actual' if number(value(drawdown_cell)) is not None else 'Sin dato'),
            'threshold_label': text(value(cells.get((3, 5), {}))),
            'peak_label': text(value(cells.get((4, 2), {}))),
            'close_label': text(value(cells.get((5, 2), {}))),
            'basis': text(value(cells.get((6, 2), {}))),
            'note': drawdown_cell.get('note', ''),
        }
    schedule = mobile_schedule(layout)
    return {
        'schema_version':1, 'generated_at':datetime.now(timezone.utc).isoformat(), 'stale':False,
        'warnings': warnings,
        'market': {**schedule, 'risk_label':risk or 'Riesgo no disponible', 'risk_score':int(risk_match[1]) if risk_match else None,
            'vxn':float(vxn_match[1].replace(',','.')) if vxn_match else None,
            'vxn_label':text(value(lines.get('vxn_regime',{}))),
            'qqq_day':number(qqq.get('day_change')), 'qqq_20d':percent_label(value(lines.get('qqq_20d',{}))),
            'qqq_drawdown':percent_label(value(lines.get('nasdaq_dd6m',{}))), 'quote_at':qqq.get('observed_at'),
            'risk_note':lines.get('risk_regime',{}).get('note',''), 'vxn_note':lines.get('vxn_regime',{}).get('note',''), 'groups':groups,
            'qqq_pullback': qqq_pullback},
        'stocks':stocks, 'changes':sorted(changes,key=lambda c:c['at'] or '',reverse=True),
        'news':sorted(news,key=lambda n:str(n['at'] or ''),reverse=True)[:80],
    }
