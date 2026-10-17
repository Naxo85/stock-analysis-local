const TICKER_EXPORT_BUCKET = 'stock-analysis-reports-naxo85';

const MARKET_TICKER_EXPORT = {
  sheetName: 'Mercado',
  headerLabel: 'Ticker',
  objectName: 'config/tickers_market.json',
  ownedBackgrounds: ['#00ffff', '#00b8d4'],
};

const TICKER_EXPORT_PROFILES = {
  trading: {
    label: 'trading',
    sheetName: 'Bolsa_2026',
    tickerColumnLabel: 'D',
    tickerColumn: 4,
    ownershipColumnLabel: 'C',
    ownershipColumn: 3,
    firstDataRow: 2,
    objectName: 'config/tickers.json',
  },
  core: {
    label: 'core',
    sheetName: 'Bolsa_2026',
    tickerColumnLabel: 'AG',
    tickerColumn: 33,
    ownershipColumnLabel: 'AF',
    ownershipColumn: 32,
    firstDataRow: 2,
    objectName: 'config/tickers_core.json',
  },
};

function onOpen() {
  const spreadsheet = SpreadsheetApp.getActiveSpreadsheet();
  const analysisMenu = SpreadsheetApp.getUi().createMenu('Análisis IA');
  const hasMarketSheet = Boolean(
    spreadsheet.getSheetByName(MARKET_TICKER_EXPORT.sheetName)
  );

  if (hasMarketSheet) {
    analysisMenu
      .addItem('Analizar mercado en local', 'enqueueMarketAnalysis')
      .addItem('Analizar ticker en local...', 'promptAndEnqueueTickerAnalysis')
      .addSeparator()
      .addItem('He comprado 1 shot...', 'promptMarketShotPurchase')
      .addItem('He vendido 1 shot...', 'promptMarketShotSale')
      .addItem('Quitar ticker del seguimiento...', 'promptRemoveMarketTicker');
  } else if (spreadsheet.getSheetByName('Bolsa_2026')) {
    analysisMenu
      .addItem('Analizar trading en local', 'enqueueTradingAnalysis')
      .addItem('Analizar core en local', 'enqueueCoreAnalysis')
      .addItem('Analizar ticker en local...', 'promptAndEnqueueTickerAnalysis')
      .addSeparator()
      .addItem('Actualizar target y nota trading', 'updateTradingTargetsAndNotes')
      .addItem('Actualizar target y nota core', 'updateCoreTargetsAndNotes')
      .addItem('Actualizar colores dip Core', 'refreshCoreDrawdownColorsNow')
      .addSeparator()
      .addItem('Reinstalar actualización Nasdaq 5 min', 'MKT_INSTALL_NASDAQ_RISK_REGIME_TRIGGER');
  }

  analysisMenu.addSeparator().addItem('Ver última ejecución', 'showLatestAnalysisStatus').addToUi();

  try {
    refreshTradingDrawdownNotesNow();
    refreshCoreDrawdownColorsNow();
  } catch (e) {
    console.log('[onOpen] No se pudieron actualizar las leyendas de dip:', e);
  }
}

function enqueueMarketAnalysis() {
  const exported = exportMarketTickersToGcs_(false);
  enqueueAnalysisCommand_({
    action: 'analyze_market',
    max_parallel: ANALYSIS_COMMAND_DEFAULT_PARALLEL,
    ticker_count: exported.count,
    config_generated_at: exported.generated_at,
  });
}

function exportMarketTickersToGcs() {
  return exportMarketTickersToGcs_(true);
}

function exportMarketTickersToGcs_(showToast) {
  const spreadsheet = SpreadsheetApp.getActiveSpreadsheet();
  const sheet = spreadsheet.getSheetByName(MARKET_TICKER_EXPORT.sheetName);

  if (!sheet) {
    throw new Error(`Sheet not found: ${MARKET_TICKER_EXPORT.sheetName}`);
  }

  const records = [];
  const seen = new Set();
  const tickerColumns = findMarketTickerColumns_(sheet);

  tickerColumns.forEach((column) => {
    readContiguousMarketTickerRecords_(sheet, column).forEach((record) => {
      if (seen.has(record.ticker)) {
        throw new Error(`Ticker duplicado en Mercado: ${record.ticker}`);
      }
      seen.add(record.ticker);
      records.push(record);
    });
  });

  if (records.length === 0) {
    throw new Error('Mercado no contiene tickers para analizar.');
  }

  const payload = {
    generated_at: new Date().toISOString(),
    source_sheet: MARKET_TICKER_EXPORT.sheetName,
    profile: 'market',
    ticker_columns: tickerColumns.map(
      (column) => column.label
    ),
    count: records.length,
    tickers: records.map((record) => record.ticker),
    ticker_records: records,
  };

  uploadJsonToGcs_(
    TICKER_EXPORT_BUCKET,
    MARKET_TICKER_EXPORT.objectName,
    payload
  );

  if (showToast) {
    spreadsheet.toast(
      `Exportados ${records.length} tickers de Mercado a GCS`,
      'Mercado IA'
    );
  }

  return payload;
}

function findMarketTickerColumns_(sheet) {
  const lastRow = sheet.getLastRow();
  const lastColumn = sheet.getLastColumn();
  if (lastRow < 1 || lastColumn < 1) {
    throw new Error('Mercado está vacío.');
  }

  const values = sheet.getRange(1, 1, lastRow, lastColumn).getDisplayValues();
  const columns = [];
  values.forEach((row, rowIndex) => {
    row.forEach((value, columnIndex) => {
      if (String(value || '').trim().toLowerCase() !== 'ticker') {
        return;
      }
      const column = columnIndex + 1;
      columns.push({
        label: sheet.getRange(1, column).getA1Notation().replace(/\d/g, ''),
        column,
        firstDataRow: rowIndex + 2,
      });
    });
  });

  if (columns.length !== 2) {
    throw new Error(
      `Se esperaban 2 cabeceras Ticker en Mercado y se encontraron ${columns.length}.`
    );
  }
  return columns;
}

function readContiguousMarketTickerRecords_(sheet, column) {
  const rowCount = sheet.getLastRow() - column.firstDataRow + 1;

  if (rowCount < 1) {
    return [];
  }

  const range = sheet.getRange(
    column.firstDataRow,
    column.column,
    rowCount,
    1
  );
  const values = range.getValues();
  const backgrounds = range.getBackgrounds();
  const records = [];

  for (let index = 0; index < values.length; index += 1) {
    const ticker = String(values[index][0] || '').trim().toUpperCase();

    if (!ticker) {
      if (records.length > 0) {
        break;
      }
      continue;
    }

    if (!/^[A-Z][A-Z0-9.\-]{0,14}$/.test(ticker)) {
      throw new Error(
        `Ticker no válido en ${column.label}${column.firstDataRow + index}: ${ticker}`
      );
    }

    const background = String(backgrounds[index][0] || '').toLowerCase();
    const owned = MARKET_TICKER_EXPORT.ownedBackgrounds.includes(background);
    records.push({
      ticker,
      owned,
      ownership_source: owned ? 'Mercado:ticker_background' : null,
    });
  }

  return records;
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

function exportTickerProfileToGcs_(profileName, showToast) {
  if (showToast === undefined) {
    showToast = true;
  }

  const profile = tickerExportProfile_(profileName);
  const spreadsheet = SpreadsheetApp.getActiveSpreadsheet();
  const sheet = spreadsheet.getSheetByName(profile.sheetName);

  if (!sheet) {
    throw new Error(`Sheet not found: ${profile.sheetName}`);
  }

  const tickerRecords = readTickerRecords_(
    sheet,
    profile.firstDataRow,
    profile.tickerColumn,
    profile.ownershipColumn,
    `${profile.label}:${profile.ownershipColumnLabel}`
  );
  const tickers = tickerRecords.map((record) => record.ticker);
  const payload = {
    generated_at: new Date().toISOString(),
    source_sheet: profile.sheetName,
    profile: profile.label,
    ticker_column: profile.tickerColumnLabel,
    ownership_column: profile.ownershipColumnLabel,
    count: tickers.length,
    tickers,
    ticker_records: tickerRecords,
  };

  uploadJsonToGcs_(TICKER_EXPORT_BUCKET, profile.objectName, payload);

  if (showToast) {
    SpreadsheetApp.getActiveSpreadsheet().toast(
      `Exportados ${tickers.length} tickers ${profile.label} a GCS`,
      'Análisis IA'
    );
  }

  return payload;
}

function readTickerRecords_(
  sheet,
  firstDataRow,
  tickerColumn,
  ownershipColumn,
  ownershipSource
) {
  const lastRow = sheet.getLastRow();

  if (lastRow < firstDataRow) {
    return [];
  }

  const firstColumn = Math.min(tickerColumn, ownershipColumn);
  const lastColumn = Math.max(tickerColumn, ownershipColumn);
  const values = sheet
    .getRange(
      firstDataRow,
      firstColumn,
      lastRow - firstDataRow + 1,
      lastColumn - firstColumn + 1
    )
    .getValues();
  const tickerOffset = tickerColumn - firstColumn;
  const ownershipOffset = ownershipColumn - firstColumn;
  const seen = new Set();
  const records = [];

  values.forEach((row) => {
    const ticker = String(row[tickerOffset]).trim().toUpperCase();

    if (!ticker || seen.has(ticker)) {
      return;
    }

    seen.add(ticker);
    const owned = isOwnedTickerValue_(row[ownershipOffset]);
    records.push({
      ticker,
      owned,
      ownership_source: owned ? ownershipSource : null,
    });
  });

  return records;
}

function isOwnedTickerValue_(value) {
  if (value === true) {
    return true;
  }
  if (typeof value === 'number') {
    return value !== 0;
  }
  const normalized = String(value || '').trim().toLowerCase();
  return normalized !== '' && !['0', 'false', 'no', 'n'].includes(normalized);
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
