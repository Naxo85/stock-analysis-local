const TICKER_EXPORT_SHEET_NAME = 'Bolsa_2026';
const TICKER_EXPORT_HEADER = 'Ticker';
const TICKER_EXPORT_BUCKET = 'stock-analysis-reports-naxo85';
const TICKER_EXPORT_OBJECT = 'config/tickers.json';

function onOpen() {
  SpreadsheetApp.getUi()
    .createMenu('Análisis IA')
    .addItem('Exportar tickers a GCS', 'exportTickersToGcs')
    .addSeparator()
    .addItem('Actualizar target y nota', 'updateAnalysisTargetsAndNotes')
    .addToUi();
}

function exportTickersToGcs() {
  const spreadsheet = SpreadsheetApp.getActiveSpreadsheet();
  const sheet = spreadsheet.getSheetByName(TICKER_EXPORT_SHEET_NAME);

  if (!sheet) {
    throw new Error(`Sheet not found: ${TICKER_EXPORT_SHEET_NAME}`);
  }

  const lastRow = sheet.getLastRow();
  const lastColumn = sheet.getLastColumn();

  if (lastRow < 1 || lastColumn < 1) {
    throw new Error(`Sheet is empty: ${TICKER_EXPORT_SHEET_NAME}`);
  }

  const headers = sheet.getRange(1, 1, 1, lastColumn).getValues()[0];
  const tickerColumnIndex = headers.findIndex(
    (header) => String(header).trim() === TICKER_EXPORT_HEADER
  );

  if (tickerColumnIndex === -1) {
    throw new Error(`Header not found: ${TICKER_EXPORT_HEADER}`);
  }

  const tickers = readTickerValues_(sheet, lastRow, tickerColumnIndex + 1);
  const payload = {
    generated_at: new Date().toISOString(),
    source_sheet: TICKER_EXPORT_SHEET_NAME,
    ticker_column: TICKER_EXPORT_HEADER,
    count: tickers.length,
    tickers,
  };

  uploadJsonToGcs_(TICKER_EXPORT_BUCKET, TICKER_EXPORT_OBJECT, payload);

  SpreadsheetApp.getActiveSpreadsheet().toast(
    `Exportados ${tickers.length} tickers a GCS`,
    'Análisis IA'
  );
}

function readTickerValues_(sheet, lastRow, tickerColumn) {
  if (lastRow < 2) {
    return [];
  }

  const values = sheet.getRange(2, tickerColumn, lastRow - 1, 1).getValues();
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
