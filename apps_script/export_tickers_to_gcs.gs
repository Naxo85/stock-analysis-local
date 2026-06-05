const TICKER_EXPORT_BUCKET = 'stock-analysis-reports-naxo85';

const TICKER_EXPORT_PROFILES = {
  trading: {
    label: 'trading',
    sheetName: 'Bolsa_2026',
    tickerColumnLabel: 'D',
    tickerColumn: 4,
    firstDataRow: 2,
    objectName: 'config/tickers.json',
  },
  core: {
    label: 'core',
    sheetName: 'Bolsa_2026',
    tickerColumnLabel: 'AG',
    tickerColumn: 33,
    firstDataRow: 2,
    objectName: 'config/tickers_core.json',
  },
};

function onOpen() {
  SpreadsheetApp.getUi()
    .createMenu('Análisis IA')
    .addItem('Exportar tickers trading a GCS', 'exportTradingTickersToGcs')
    .addItem('Exportar tickers core a GCS', 'exportCoreTickersToGcs')
    .addSeparator()
    .addItem('Actualizar target y nota trading', 'updateTradingTargetsAndNotes')
    .addItem('Actualizar target y nota core', 'updateCoreTargetsAndNotes')
    .addToUi();
}

function exportTickersToGcs() {
  exportTradingTickersToGcs();
}

function exportTradingTickersToGcs() {
  exportTickerProfileToGcs_('trading');
}

function exportCoreTickersToGcs() {
  exportTickerProfileToGcs_('core');
}

function exportTickerProfileToGcs_(profileName) {
  const profile = tickerExportProfile_(profileName);
  const spreadsheet = SpreadsheetApp.getActiveSpreadsheet();
  const sheet = spreadsheet.getSheetByName(profile.sheetName);

  if (!sheet) {
    throw new Error(`Sheet not found: ${profile.sheetName}`);
  }

  const tickers = readTickerValues_(
    sheet,
    profile.firstDataRow,
    profile.tickerColumn
  );
  const payload = {
    generated_at: new Date().toISOString(),
    source_sheet: profile.sheetName,
    profile: profile.label,
    ticker_column: profile.tickerColumnLabel,
    count: tickers.length,
    tickers,
  };

  uploadJsonToGcs_(TICKER_EXPORT_BUCKET, profile.objectName, payload);

  SpreadsheetApp.getActiveSpreadsheet().toast(
    `Exportados ${tickers.length} tickers ${profile.label} a GCS`,
    'Análisis IA'
  );
}

function readTickerValues_(sheet, firstDataRow, tickerColumn) {
  const lastRow = sheet.getLastRow();

  if (lastRow < firstDataRow) {
    return [];
  }

  const values = sheet
    .getRange(firstDataRow, tickerColumn, lastRow - firstDataRow + 1, 1)
    .getValues();
  const seen = new Set();
  const tickers = [];

  values.forEach((row) => {
    const ticker = String(row[0]).trim().toUpperCase();

    if (!ticker || seen.has(ticker)) {
      return;
    }

    seen.add(ticker);
    tickers.push(ticker);
  });

  return tickers;
}

function tickerExportProfile_(profileName) {
  const profile = TICKER_EXPORT_PROFILES[profileName];

  if (!profile) {
    throw new Error(`Unknown ticker export profile: ${profileName}`);
  }

  return profile;
}

function uploadJsonToGcs_(bucket, objectName, payload) {
  const objectPath = encodeURIComponent(objectName).replace(/%2F/g, '/');
  const url =
    `https://storage.googleapis.com/upload/storage/v1/b/${bucket}/o` +
    `?uploadType=media&name=${objectPath}`;
  const body = JSON.stringify(payload, null, 2);
  const response = UrlFetchApp.fetch(url, {
    method: 'post',
    contentType: 'application/json; charset=utf-8',
    payload: body,
    headers: {
      Authorization: `Bearer ${ScriptApp.getOAuthToken()}`,
    },
    muteHttpExceptions: true,
  });
  const status = response.getResponseCode();

  if (status < 200 || status >= 300) {
    throw new Error(
      `GCS upload failed (${status}): ${response.getContentText()}`
    );
  }
}
