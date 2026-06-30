const ANALYSIS_COMMAND_BUCKET = 'stock-analysis-reports-naxo85';
const ANALYSIS_COMMAND_PENDING_PREFIX = 'commands/pending';
const ANALYSIS_COMMAND_DEFAULT_PARALLEL = 6;

function enqueueTradingAnalysis() {
  const exported = exportTickerProfileToGcs_('trading', false);
  enqueueAnalysisCommand_({
    action: 'analyze_trading',
    max_parallel: ANALYSIS_COMMAND_DEFAULT_PARALLEL,
    ticker_count: exported.count,
    config_generated_at: exported.generated_at,
  });
}

function enqueueCoreAnalysis() {
  const exported = exportTickerProfileToGcs_('core', false);
  enqueueAnalysisCommand_({
    action: 'analyze_core',
    max_parallel: ANALYSIS_COMMAND_DEFAULT_PARALLEL,
    ticker_count: exported.count,
    config_generated_at: exported.generated_at,
  });
}

function promptAndEnqueueTickerAnalysis() {
  const ui = SpreadsheetApp.getUi();
  const response = ui.prompt(
    'Analizar ticker',
    'Introduce el ticker:',
    ui.ButtonSet.OK_CANCEL
  );

  if (response.getSelectedButton() !== ui.Button.OK) {
    return;
  }

  const ticker = String(response.getResponseText() || '')
    .trim()
    .toUpperCase();

  if (!/^[A-Z0-9.\-]{1,15}$/.test(ticker)) {
    ui.alert(`Ticker no válido: ${ticker}`);
    return;
  }

  enqueueAnalysisCommand_({
    action: 'analyze_ticker',
    ticker,
  });
}

function enqueueAnalysisCommand_(values) {
  const now = new Date();
  const suffix = Utilities.getUuid().slice(0, 8);
  const timestamp = Utilities.formatDate(now, 'UTC', 'yyyyMMdd-HHmmss');
  const actionLabel = String(values.action || '').replace(/^analyze_/, '');
  const commandId = `${timestamp}-${actionLabel}-${suffix}`;
  const payload = {
    id: commandId,
    action: values.action,
    created_at: now.toISOString(),
    source: 'google_sheets',
  };

  if (values.ticker) {
    payload.ticker = values.ticker;
  }

  if (values.max_parallel) {
    payload.max_parallel = values.max_parallel;
  }

  if (values.ticker_count !== undefined) {
    payload.ticker_count = values.ticker_count;
  }

  if (values.config_generated_at) {
    payload.config_generated_at = values.config_generated_at;
  }

  const objectName = `${ANALYSIS_COMMAND_PENDING_PREFIX}/${commandId}.json`;
  commandQueueUploadJsonToGcs_(
    ANALYSIS_COMMAND_BUCKET,
    objectName,
    payload
  );
  registerPendingAnalysisCommand_(payload);

  const description = values.ticker || actionLabel.toUpperCase();
  SpreadsheetApp.getActiveSpreadsheet().toast(
    `Orden ${description} enviada. El PC la procesará cuando el worker esté activo.`,
    'Análisis IA',
    8
  );

  return payload;
}

function commandQueueUploadJsonToGcs_(bucket, objectName, payload) {
  const encodedName = encodeURIComponent(objectName).replace(/%2F/g, '/');
  const url =
    `https://storage.googleapis.com/upload/storage/v1/b/${bucket}/o` +
    `?uploadType=media&name=${encodedName}`;
  const response = UrlFetchApp.fetch(url, {
    method: 'post',
    contentType: 'application/json; charset=utf-8',
    payload: JSON.stringify(payload, null, 2),
    headers: {
      Authorization: `Bearer ${ScriptApp.getOAuthToken()}`,
    },
    muteHttpExceptions: true,
  });
  const status = response.getResponseCode();

  if (status < 200 || status >= 300) {
    throw new Error(
      `GCS command upload failed (${status}): ${response.getContentText()}`
    );
  }
}
