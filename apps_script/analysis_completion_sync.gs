const ANALYSIS_STATUS_BUCKET = 'stock-analysis-reports-naxo85';
const ANALYSIS_STATUS_OBJECT = 'commands/status/latest.json';
const ANALYSIS_LAST_APPLIED_PROPERTY = 'ANALYSIS_LAST_APPLIED_COMMAND_ID';
const ANALYSIS_LAST_STATUS_PROPERTY = 'ANALYSIS_LAST_COMMAND_STATUS';
const ANALYSIS_PENDING_COMMANDS_PROPERTY = 'ANALYSIS_PENDING_COMMANDS';
const ANALYSIS_COMMAND_MAX_WAIT_MS = 4 * 60 * 60 * 1000;

function installAnalysisCompletionTrigger() {
  ensureAnalysisCompletionTrigger_();

  SpreadsheetApp.getActiveSpreadsheet().toast(
    'Sincronización preparada. Solo se activa mientras haya órdenes.',
    'Análisis IA',
    8
  );
}

function registerPendingAnalysisCommand_(command) {
  const pending = readPendingAnalysisCommands_();
  const commandId = String(command.id || '');

  if (!commandId) {
    throw new Error('No se puede registrar una orden sin id.');
  }

  if (!pending.some((item) => String(item.id) === commandId)) {
    pending.push({
      id: commandId,
      action: command.action || '',
      ticker: command.ticker || '',
      created_at: command.created_at || new Date().toISOString(),
    });
  }

  writePendingAnalysisCommands_(pending.slice(-20));
  ensureAnalysisCompletionTrigger_();
}

function ensureAnalysisCompletionTrigger_() {
  const exists = ScriptApp.getProjectTriggers().some((trigger) =>
    trigger.getHandlerFunction() === 'syncLatestAnalysisCompletion'
  );

  if (!exists) {
    ScriptApp.newTrigger('syncLatestAnalysisCompletion')
      .timeBased()
      .everyMinutes(1)
      .create();
  }
}

function removeAnalysisCompletionTrigger() {
  ScriptApp.getProjectTriggers().forEach((trigger) => {
    if (trigger.getHandlerFunction() === 'syncLatestAnalysisCompletion') {
      ScriptApp.deleteTrigger(trigger);
    }
  });
}

function syncLatestAnalysisCompletion() {
  const lock = LockService.getScriptLock();

  if (!lock.tryLock(5000)) {
    return;
  }

  try {
    const pending = readPendingAnalysisCommands_();

    if (pending.length === 0) {
      removeAnalysisCompletionTrigger();
      return;
    }

    const properties = PropertiesService.getScriptProperties();
    const remaining = [];

    pending.forEach((command) => {
      const completed = readAnalysisCommandResult_(command.id, 'completed');
      const failed = completed
        ? null
        : readAnalysisCommandResult_(command.id, 'failed');
      let result = completed || failed;

      if (!result && analysisCommandExpired_(command)) {
        result = {
          id: command.id,
          action: command.action,
          ticker: command.ticker,
          status: 'failed',
          finished_at: new Date().toISOString(),
          error_message: 'Tiempo máximo de espera superado.',
        };
      }

      if (!result) {
        remaining.push(command);
        return;
      }

      if (result.status === 'ok') {
        applyCompletedAnalysisCommand_(result);
        console.log(
          `Análisis aplicado a la Sheet: ${result.id} (${result.action})`
        );
      } else {
        console.log(
          `Análisis ${result.id} no aplicado: status=${result.status}`
        );
      }

      properties.setProperty(
        ANALYSIS_LAST_STATUS_PROPERTY,
        JSON.stringify(compactAnalysisCommandStatus_(result))
      );
      properties.setProperty(
        ANALYSIS_LAST_APPLIED_PROPERTY,
        String(result.id)
      );
    });

    writePendingAnalysisCommands_(remaining);

    if (remaining.length === 0) {
      removeAnalysisCompletionTrigger();
    }
  } finally {
    lock.releaseLock();
  }
}

function readPendingAnalysisCommands_() {
  const raw = PropertiesService.getScriptProperties().getProperty(
    ANALYSIS_PENDING_COMMANDS_PROPERTY
  );

  if (!raw) {
    return [];
  }

  try {
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed : [];
  } catch (error) {
    console.log(`Pending commands inválido: ${error}`);
    return [];
  }
}

function writePendingAnalysisCommands_(commands) {
  const properties = PropertiesService.getScriptProperties();

  if (!commands || commands.length === 0) {
    properties.deleteProperty(ANALYSIS_PENDING_COMMANDS_PROPERTY);
    return;
  }

  properties.setProperty(
    ANALYSIS_PENDING_COMMANDS_PROPERTY,
    JSON.stringify(commands)
  );
}

function analysisCommandExpired_(command) {
  const createdMs = Date.parse(command.created_at || '');

  if (!Number.isFinite(createdMs)) {
    return false;
  }

  return Date.now() - createdMs > ANALYSIS_COMMAND_MAX_WAIT_MS;
}

function compactAnalysisCommandStatus_(result) {
  return {
    id: result.id || '',
    action: result.action || '',
    ticker: result.ticker || '',
    label: result.label || '',
    status: result.status || '',
    finished_at: result.finished_at || '',
    error_message: String(result.error_message || '').slice(0, 500),
  };
}

function applyCompletedAnalysisCommand_(result) {
  if (result.action === 'analyze_trading') {
    updateTradingTargetsAndNotes();
    return;
  }

  if (result.action === 'analyze_core') {
    updateCoreTargetsAndNotes();
    return;
  }

  if (result.action === 'analyze_ticker') {
    updateCompletedTickerRows_(String(result.ticker || '').toUpperCase());
    return;
  }

  throw new Error(`Acción completada no soportada: ${result.action}`);
}

function updateCompletedTickerRows_(ticker) {
  if (!ticker) {
    throw new Error('Resultado analyze_ticker sin ticker.');
  }

  const spreadsheet = SpreadsheetApp.getActiveSpreadsheet();
  const profiles = ['trading', 'core'];

  profiles.forEach((profileName) => {
    const profile = TARGET_UPDATE_PROFILES[profileName];

    if (!profile) {
      return;
    }

    const sheet = spreadsheet.getSheetByName(profile.sheetName);

    if (!sheet) {
      return;
    }

    const lastRow = sheet.getLastRow();

    if (lastRow < profile.firstDataRow) {
      return;
    }

    const values = sheet
      .getRange(
        profile.firstDataRow,
        profile.tickerColumn,
        lastRow - profile.firstDataRow + 1,
        1
      )
      .getValues();
    const matchingRows = [];

    values.forEach((row, index) => {
      const rowTicker = String(row[0] || '').trim().toUpperCase();
      if (rowTicker === ticker) {
        matchingRows.push(profile.firstDataRow + index);
      }
    });

    if (matchingRows.length === 0) {
      return;
    }

    if (typeof updateTargetAndNoteForRow_ === 'function') {
      matchingRows.forEach((rowNumber) => {
        updateTargetAndNoteForRow_(profileName, rowNumber);
      });
      return;
    }

    if (profileName === 'trading') {
      updateTradingTargetsAndNotes();
    } else {
      updateCoreTargetsAndNotes();
    }
  });
}

function readLatestAnalysisCommandStatus_() {
  return readAnalysisGcsJson_(ANALYSIS_STATUS_OBJECT);
}

function readAnalysisCommandResult_(commandId, resultType) {
  const objectName = `commands/${resultType}/${commandId}.json`;
  return readAnalysisGcsJson_(objectName);
}

function readAnalysisGcsJson_(objectName) {
  const encodedName = encodeURIComponent(objectName);
  const url =
    `https://storage.googleapis.com/storage/v1/b/` +
    `${ANALYSIS_STATUS_BUCKET}/o/${encodedName}?alt=media`;
  const response = UrlFetchApp.fetch(url, {
    method: 'get',
    headers: {
      Authorization: `Bearer ${ScriptApp.getOAuthToken()}`,
    },
    muteHttpExceptions: true,
  });
  const status = response.getResponseCode();

  if (status === 404) {
    return null;
  }

  if (status !== 200) {
    throw new Error(
      `GCS JSON read failed (${status}) para ${objectName}: ` +
      response.getContentText()
    );
  }

  return JSON.parse(response.getContentText());
}

function showLatestAnalysisStatus() {
  const result = readLatestAnalysisCommandStatus_();
  const ui = SpreadsheetApp.getUi();

  if (!result) {
    ui.alert('No existe todavía ningún estado de análisis.');
    return;
  }

  const label = result.ticker || result.label || result.action || '';
  const status = String(result.status || 'unknown').toUpperCase();
  const finished = result.finished_at || '';
  const error = result.error_message ? `\n\n${result.error_message}` : '';

  ui.alert(
    'Última ejecución',
    `${status} ${label}\n${finished}${error}`,
    ui.ButtonSet.OK
  );
}
