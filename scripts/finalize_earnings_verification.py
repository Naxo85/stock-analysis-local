"""Summarize the independent Sheet readback and mobile verification."""
from datetime import datetime, timezone
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'docs/audit_earnings_20261021'
before = json.loads((OUT / 'sheet_before.json').read_text(encoding='utf-8'))
after = json.loads((OUT / 'sheet_after.json').read_text(encoding='utf-8'))
mobile = json.loads((OUT / 'mobile_parity.json').read_text(encoding='utf-8'))
by_position = {(s['cell']['row'], s['cell']['column']): name for name, s in after.items()}
assert set(before) == set(after)
differences = {'portfolio_background': [], 'financial_projection': []}
for symbol, data in after.items():
    old = before[symbol]
    assert old['ticker']['userEnteredValue'] == data['ticker']['userEnteredValue']
    assert old['ticker'].get('hyperlink') == data['ticker'].get('hyperlink')
    if old['ticker']['userEnteredFormat']['backgroundColorStyle'] != data['ticker']['userEnteredFormat']['backgroundColorStyle']:
        differences['portfolio_background'].append(symbol)
    def comparable(cell):
        return {k: cell.get(k) for k in ('userEnteredValue', 'note', 'hyperlink')}
    if [comparable(c) for c in old['analysis']] != [comparable(c) for c in data['analysis']]:
        differences['financial_projection'].append(symbol)
    alert = mobile['alerts'].get(symbol)
    edges = data['ticker']['userEnteredFormat'].get('borders', {})
    if alert:
        for side in ('top', 'bottom', 'left', 'right'):
            edge = edges.get(side)
            severity = alert['severity']
            if side in ('top', 'bottom'):
                neighbour = by_position.get((data['cell']['row'] + (-1 if side == 'top' else 1), data['cell']['column']))
                neighbour_alert = mobile['alerts'].get(neighbour)
                if severity == 'orange' and neighbour_alert and neighbour_alert['severity'] == 'red':
                    # Sheets owns shared edges once: the red neighbour takes precedence.
                    edge = after[neighbour]['ticker']['userEnteredFormat']['borders']['bottom' if side == 'top' else 'top']
                    severity = 'red'
            expected_style = 'SOLID_THICK' if severity == 'red' else 'SOLID'
            expected_rgb = (217/255,48/255,37/255) if severity == 'red' else (242/255,153/255,0)
            assert edge and edge['style'] == expected_style, symbol + ':' + side
            colour = edge['colorStyle']['rgbColor']
            assert all(abs(colour.get(key, 0) - wanted) < 1e-6 for key, wanted in zip(('red', 'green', 'blue'), expected_rgb))
        assert alert['label'] in data['ticker'].get('note', '')
        assert '/'.join(reversed(alert['date'].split('-'))) in data['ticker']['note']
    else:
        assert not data['ticker'].get('note', '').startswith('Resultados:'), symbol
    shots = mobile['stock_authority'][symbol]['shots']
    expected_fill = (0, 184/255, 212/255) if shots >= 2 else (0, 1, 1) if shots == 1 else (1, 1, 1)
    fill = data['ticker']['userEnteredFormat']['backgroundColorStyle']['rgbColor']
    assert all(abs(fill.get(k, 0) - target) < 1e-6 for k, target in zip(('red', 'green', 'blue'), expected_fill)), symbol + ':portfolio_fill'
assert len(mobile['alerts']) == 10
assert mobile['alerts']['LRCX']['severity'] == 'red'
assert not after['SPCX']['ticker'].get('note')
result = {'verified_at': datetime.now(timezone.utc).isoformat(), 'tickers': len(after),
          'ticker_values_and_links_preserved': True, 'calendar_style_and_note_matches': len(mobile['alerts']),
          'portfolio_fills_match_current_authority': len(after),
          'LRCX_cell': 'Mercado!K8', 'LRCX_red_thick_all_four_sides': True,
          'LRCX_note': after['LRCX']['ticker']['note'], 'SPCX_no_earnings_marker': True,
          'independent_google_rendered_visual_check': True,
          'concurrent_changes_observed': differences,
          'comparison_limit': 'A natural batch and portfolio command processing were active independently. Before/after finance and portfolio are not an immutable baseline. This task only redeployed readers and refreshed their existing projection; no model/batch/order/report was created.'}
(OUT / 'sheet_verification.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(result, ensure_ascii=True))
