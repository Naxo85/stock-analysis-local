from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import json
import logging
import os
import threading
import time
from urllib.parse import urlencode
import google.auth
from google.auth.transport.requests import AuthorizedSession
from google.cloud import storage
from google.api_core.exceptions import NotFound
from projection import project, select_report
from publication_contract import read_committed, read_attempt, with_attempt, attempt_notice

LOG = logging.getLogger(__name__)


class PublishedSources:
    def __init__(self, storage_client=None, sheets_session=None):
        self.system_bucket = os.getenv('SYSTEM_BUCKET', 'stock-analysis-system-naxo85')
        self.report_bucket = os.getenv('REPORT_BUCKET', 'stock-analysis-reports-naxo85')
        self.client = storage_client or storage.Client()
        if sheets_session is None:
            credentials, _ = google.auth.default(scopes=['https://www.googleapis.com/auth/spreadsheets.readonly'])
            sheets_session = AuthorizedSession(credentials)
        self.sheets = sheets_session
        self.lock = threading.Lock()
        self.cached = None
        self.cache_until = 0
        self.reports = {}

    def read(self, bucket, name, optional=False):
        try:
            return json.loads(self.client.bucket(bucket).blob(name).download_as_bytes(timeout=20, retry=None))
        except NotFound:
            if optional:
                return None
            raise

    def report_pair(self, symbol):
        def read(name):
            try:
                return self.client.bucket(self.report_bucket).blob(name).download_as_bytes(timeout=20, retry=None).decode('utf-8')
            except NotFound:
                return None
        body, manifest = read_committed(read, symbol)
        latest = json.loads(body) if manifest else self.read(self.report_bucket, f'{symbol}/latest.json', optional=True)
        attempt = read_attempt(read, symbol)
        if latest is None and attempt is not None:
            latest = {'symbol': symbol, 'analysis_status': 'unavailable'}
        if latest is not None:
            latest = with_attempt(latest, attempt, manifest)
        mirror = None
        if manifest is None and (not latest or latest.get('analysis_status') != 'ok'):
            mirror = self.read(self.system_bucket, f'runtime/analysis-reports/{symbol}.json', optional=True)
        try:
            history = self.read(self.report_bucket, f'{symbol}/history.json', optional=True)
        except Exception:
            LOG.warning('Could not read compact history for %s', symbol, exc_info=True)
            history = None
        return symbol, latest, mirror, history

    def snapshot(self):
        if self.cached and time.monotonic() < self.cache_until:
            return self.cached
        with self.lock:
            if self.cached and time.monotonic() < self.cache_until:
                return self.cached
            try:
                return self._load()
            except Exception:
                LOG.exception('Mobile snapshot refresh failed')
                if self.cached:
                    return {**self.cached, 'stale':True, 'warnings': [*self.cached['warnings'], 'No se pudo actualizar. Se conserva la última lectura correcta.']}
                raise

    def _load(self):
        layout = self.read(self.system_bucket, 'runtime/config/market_sheet_layout.json')
        symbols = list(dict.fromkeys(s for group in layout['groups'] for s in group['tickers']))
        warnings = []
        portfolio = self.read(self.system_bucket, 'runtime/config/portfolio.json')
        try:
            display_state = self.read(self.system_bucket, 'runtime/analysis-reports/sync-state.json', optional=True) or {}
            earnings = display_state.get('earnings', {})
        except Exception:
            LOG.warning('Could not read earnings calendar', exc_info=True)
            earnings = {}
            warnings.append('Calendario de resultados no disponible en esta lectura.')
        quotes = self.read(self.system_bucket, 'runtime/market-quotes/latest.json')
        title = layout['sheet']['title'].replace("'", "''")
        end = max(len(symbols)+35, 100)
        end_col = layout['blocks'][-1]['end_column']
        query = urlencode({'ranges': f"'{title}'!A1:{end_col}{end}", 'includeGridData':'true', 'fields':'sheets(data(startRow,startColumn,rowData(values(effectiveValue,formattedValue,note))))'})
        response = self.sheets.get(f"https://sheets.googleapis.com/v4/spreadsheets/{layout['spreadsheet']['spreadsheet_id']}?{query}", timeout=25)
        response.raise_for_status()
        sheet = response.json()
        latest, mirrors, histories, report_data = {}, {}, {}, {}
        with ThreadPoolExecutor(max_workers=8) as pool:
            jobs = {symbol:pool.submit(self.report_pair,symbol) for symbol in symbols}
            for symbol, job in jobs.items():
                try:
                    _, current, mirror, history = job.result()
                    latest[symbol], mirrors[symbol] = current, mirror
                    histories[symbol] = history
                    valid, status = select_report(current,mirror)
                    if valid or ((current or {}).get('latest_attempt')):
                        visible = valid or {'symbol': symbol, 'analysis_status': 'unavailable'}
                        report_data[symbol] = {k:visible.get(k) for k in ['symbol','generated_at','analysis_status','analysis_markdown','decision','plan','catalysts','next_event']}
                        report_data[symbol].update(last_attempt_status=status,
                            last_attempt_at=((current or {}).get('latest_attempt') or {}).get('at', (current or {}).get('generated_at')),
                            latest_attempt=(current or {}).get('latest_attempt'),
                            publication_version=(current or {}).get('publication_version'),
                            attempt_notice=attempt_notice((current or {}).get('latest_attempt'), has_report=bool(valid)))
                except Exception:
                    LOG.exception('Could not read report for %s',symbol)
                    warnings.append(f'Informe de {symbol} no disponible en esta lectura.')
        result = project(layout,portfolio,quotes,sheet,latest,mirrors,warnings,histories,earnings=earnings)
        self.reports = report_data
        self.cached = result
        self.cache_until = time.monotonic() + 60
        return result

    def report(self, symbol):
        self.snapshot()
        return self.reports.get(symbol)
