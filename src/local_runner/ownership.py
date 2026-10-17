"""Use the same recorded holdings for individual and market entry points."""
import json


def recorded_ownership(symbol, read_text=None):
    from src.local_runner.run_batch import TICKERS_GCS_URI, _read_gcs_text
    payload = json.loads((read_text or _read_gcs_text)(TICKERS_GCS_URI))
    records = payload.get('ticker_records')
    if not isinstance(records, list):
        raise RuntimeError('ownership_unavailable: ticker_records missing; absence is not owned=false')
    matches = [row for row in records if isinstance(row, dict)
               and str(row.get('ticker', '')).strip().upper() == symbol.upper()]
    if len(matches) != 1 or type(matches[0].get('owned')) is not bool:
        raise RuntimeError('ownership_unavailable: explicit unique record required for ' + symbol)
    row = matches[0]
    return row['owned'], {'source': TICKERS_GCS_URI, 'ownership_source': row.get('ownership_source'),
                         'config_at': payload.get('generated_at') or payload.get('updated_at')}
