const ANALYSIS_STATUS_BUCKET = 'stock-analysis-reports-naxo85';
const ANALYSIS_STATUS_OBJECT = 'commands/status/latest.json';
const ANALYSIS_LATEST_PROGRESS_OBJECT = 'commands/progress/latest.json';
const ANALYSIS_LAST_APPLIED_PROPERTY = 'ANALYSIS_LAST_APPLIED_COMMAND_ID';
const ANALYSIS_LAST_STATUS_PROPERTY = 'ANALYSIS_LAST_COMMAND_STATUS';
const ANALYSIS_LAST_MARKET_SUMMARY_PROPERTY =
  'ANALYSIS_LAST_MARKET_SUMMARY_FINISHED_AT';
const ANALYSIS_PENDING_COMMANDS_PROPERTY = 'ANALYSIS_PENDING_COMMANDS';
const ANALYSIS_COMMAND_MAX_WAIT_MS = 4 * 60 * 60 * 1000;
const ANALYSIS_PROGRESS_SHEET = 'Mercado';
const ANALYSIS_PROGRESS_LEGACY_CELLS = ['AI1', 'AJ1'];
const ANALYSIS_PROGRESS_CELL = 'C4';
const ANALYSIS_MARKET_DATE_CELL = 'A9';
const ANALYSIS_MARKET_LEGACY_DATE_CELL = 'A10';
const ANALYSIS_PROGRESS_PENDING = 'PENDING';
const ANALYSIS_PROGRESS_RUNNING = 'RUNNING';
const ANALYSIS_PROGRESS_WAITING = 'ESPERA WEB';
const ANALYSIS_PROGRESS_STALE = 'SIN SEÑAL';
const ANALYSIS_PROGRESS_FAILED = 'FALLÓ';
const ANALYSIS_PROGRESS_STALE_MS = 3 * 60 * 1000;
const ANALYSIS_PROGRESS_BACKGROUNDS = {
  PENDING: '#fff2cc',
  RUNNING: '#d9ead3',
  'ESPERA WEB': '#fff2cc',
  'SIN SEÑAL': '#f4cccc',
  'FALLÓ': '#f4cccc',
};

function installAnalysisCompletionTrigger() {
  ensureAnalysisCompletionTrigger_();

  SpreadsheetApp.getActiveSpreadsheet().toast(
    'Sincronización permanente preparada.',
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
  setAnalysisProgressIndicator_(ANALYSIS_PROGRESS_PENDING);
  ensureAnalysisCompletionTrigger_();
}

function reconcileLatestMarketBatchSummary_() {
  const summary = readAnalysisGcsJson_('batch/status/latest_trading.json');
  if (!summary || !summary.finished_at) {
    return false;
  }

  const finishedAt = new Date(summary.finished_at);
  if (!Number.isFinite(finishedAt.getTime())) {
    return false;
  }

  const properties = PropertiesService.getScriptProperties();
  const summaryKey = finishedAt.toISOString();
  if (properties.getProperty(ANALYSIS_LAST_MARKET_SUMMARY_PROPERTY) === summaryKey) {
    return false;
  }

  applyMarketBatchSummary_({
    action: 'analyze_market',
    status: Number(summary.failed || 0) > 0 ? 'failed' : 'completed',
    started_at: summary.started_at || '',
    finished_at: summary.finished_at,
    batch_success: Number(summary.success || 0),
    batch_total: Number(summary.total || 0),
    batch_failed: Number(summary.failed || 0),
  });
  properties.setProperty(ANALYSIS_LAST_MARKET_SUMMARY_PROPERTY, summaryKey);
  return true;
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
    const discoveredProgress = readDiscoverableAnalysisProgress_();
    reconcileLatestMarketBatchSummary_();

    if (pending.length === 0) {
      settleIdleAnalysisProgress_(discoveredProgress);
      return;
    }

    const properties = PropertiesService.getScriptProperties();
    const remaining = [];
    let hasRunningCommand = false;
    const liveProgress = [];

    pending.forEach((command) => {
      const commandProgress = readAnalysisCommandResult_(command.id, 'progress');
      if (analysisProgressIsActive_(commandProgress)) {
        hasRunningCommand = true;
        liveProgress.push(commandProgress);
        remaining.push(command);
        return;
      }

      const completed = readAnalysisCommandResult_(command.id, 'completed');
      const failed = completed
        ? null
        : readAnalysisCommandResult_(command.id, 'failed');
      let result = completed || failed;

      if (!result) {
        const running = readAnalysisCommandResult_(command.id, 'running');
        hasRunningCommand = hasRunningCommand || Boolean(running);
        if (running) {
          const progress = readAnalysisCommandResult_(command.id, 'progress');
          if (progress) {
            liveProgress.push(progress);
          }
        }
      }

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

      if (shouldApplyAnalysisResult_(result)) {
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
      settleIdleAnalysisProgress_(discoveredProgress);
    } else {
      const progress = latestAnalysisProgress_(
        liveProgress.concat(
          analysisProgressIsActive_(discoveredProgress)
            ? [discoveredProgress]
            : []
        )
      );
      setAnalysisProgressIndicator_(
        hasRunningCommand ? ANALYSIS_PROGRESS_RUNNING : ANALYSIS_PROGRESS_PENDING,
        progress
      );
    }
  } finally {
    lock.releaseLock();
  }
}

function settleIdleAnalysisProgress_(progress) {
  if (analysisProgressIsActive_(progress)) {
    setAnalysisProgressIndicator_(ANALYSIS_PROGRESS_RUNNING, progress);
    ensureAnalysisCompletionTrigger_();
    return;
  }

  const lastStatus = readLastAnalysisCommandStatus_();
  if (analysisProgressRecoversFailure_(progress, lastStatus)) {
    const counts = progress.counts || {};
    PropertiesService.getScriptProperties().setProperty(
      ANALYSIS_LAST_STATUS_PROPERTY,
      JSON.stringify(compactAnalysisCommandStatus_({
        id: progress.command_id,
        action: progress.action || lastStatus.action,
        status: 'ok',
        finished_at: progress.heartbeat_at || new Date().toISOString(),
        batch_success: Number(counts.published || progress.total || 0),
        batch_total: Number(progress.total || 0),
        batch_failed: 0,
      }))
    );
    clearAnalysisProgressIndicator_();
    return;
  }

  if (lastStatus && lastStatus.status === 'failed') {
    setAnalysisFailureIndicator_(lastStatus);
  } else {
    clearAnalysisProgressIndicator_();
  }
}

function analysisProgressRecoversFailure_(progress, lastStatus) {
  if (!progress || !lastStatus || lastStatus.status !== 'failed') {
    return false;
  }
  if (String(progress.status || '') !== 'completed') {
    return false;
  }
  if (!progress.command_id || String(progress.command_id) !== String(lastStatus.id || '')) {
    return false;
  }

  const counts = progress.counts || {};
  const total = Number(progress.total || 0);
  const published = Number(counts.published || 0);
  const failed = Number(counts.failed || 0);
  if (total < 1 || published < total || failed !== 0) {
    return false;
  }

  const progressMs = Date.parse(progress.heartbeat_at || '');
  const failedMs = Date.parse(lastStatus.finished_at || '');
  return !Number.isFinite(progressMs) ||
    !Number.isFinite(failedMs) ||
    progressMs >= failedMs;
}

function shouldApplyAnalysisResult_(result) {
  if (result.status === 'ok') {
    return true;
  }

  const isBatch = [
    'analyze_trading',
    'analyze_core',
    'analyze_market',
  ].includes(result.action);
  const successful = Number(result.batch_success || 0);
  return isBatch && successful > 0;
}

function setAnalysisProgressIndicator_(status, progress) {
  const spreadsheet = SpreadsheetApp.getActiveSpreadsheet();
  const sheet = spreadsheet.getSheetByName(ANALYSIS_PROGRESS_SHEET);

  if (!sheet) {
    return;
  }

  migrateAnalysisProgressRows_(sheet);

  const stale = progress && analysisProgressIsStale_(progress);
  const visibleStatus = stale
    ? ANALYSIS_PROGRESS_STALE
    : analysisProgressDisplayStatus_(status, progress);
  const value = progress && !stale
    ? analysisProgressCellValue_(visibleStatus, progress)
    : visibleStatus;
  const note = progress
    ? analysisProgressNote_(progress, stale)
    : 'Estado de la cola de análisis local: PENDING o RUNNING.';

  sheet.getRange(ANALYSIS_PROGRESS_CELL)
    .setValue(value)
    .setNumberFormat('@')
    .setBackground(ANALYSIS_PROGRESS_BACKGROUNDS[visibleStatus] || null)
    .setNote(note);
}

function latestAnalysisProgress_(items) {
  if (!items || items.length === 0) {
    return null;
  }
  return items.slice().sort((left, right) =>
    Date.parse(right.heartbeat_at || '') - Date.parse(left.heartbeat_at || '')
  )[0];
}

function analysisProgressIsStale_(progress) {
  const heartbeatMs = Date.parse(progress.heartbeat_at || '');
  return Number.isFinite(heartbeatMs) &&
    Date.now() - heartbeatMs > ANALYSIS_PROGRESS_STALE_MS;
}

function analysisProgressIsActive_(progress) {
  if (!progress || String(progress.status || '') !== 'running') {
    return false;
  }
  const heartbeatMs = Date.parse(progress.heartbeat_at || '');
  return Number.isFinite(heartbeatMs) &&
    Date.now() - heartbeatMs <= ANALYSIS_PROGRESS_STALE_MS;
}

function analysisProgressCellValue_(status, progress) {
  const completed = Number(progress.completed || 0);
  const total = Number(progress.total || 0);
  return total > 0 ? `${status} ${completed}/${total}` : status;
}

function analysisProgressDisplayStatus_(status, progress) {
  if (progress && progress.provider === 'codex') {
    return status;
  }
  const web = progress && progress.chatgpt_web;
  const allWorkersRateLimited = web && Object.prototype.hasOwnProperty.call(web, 'all_workers_rate_limited')
    ? Boolean(web.all_workers_rate_limited)
    : Boolean(web && web.rate_limit_waiting);
  return allWorkersRateLimited
    ? ANALYSIS_PROGRESS_WAITING
    : status;
}

function analysisProgressNote_(progress, stale) {
  if (progress.provider === 'codex') {
    return analysisCodexProgressNote_(progress, stale);
  }
  const counts = progress.counts || {};
  const current = progress.current || {};
  const web = progress.chatgpt_web || {};
  const webWorkers = Array.isArray(web.workers) && web.workers.length > 0
    ? web.workers
    : [web];
  const providers = progress.generation_providers || {};
  const waitingForWeb = Boolean(web.rate_limit_waiting);
  const waitingForAttachments = Boolean(web.attachment_rate_limit_waiting);
  const attachmentLimitCount = Number(web.attachment_rate_limit_count || 0);
  const requestRateLimitCount = Object.prototype.hasOwnProperty.call(web, 'request_rate_limit_count')
    ? Number(web.request_rate_limit_count || 0)
    : Math.max(0, Number(web.rate_limit_count || 0) - attachmentLimitCount);
  const allWorkersRateLimited = Object.prototype.hasOwnProperty.call(web, 'all_workers_rate_limited')
    ? Boolean(web.all_workers_rate_limited)
    : waitingForWeb;
  const webStalled = Boolean(web.active_stage_stalled);
  const waitingTickers = Array.isArray(web.waiting_tickers)
    ? web.waiting_tickers
    : [];
  const phaseLabels = {
    prepare: 'Preparación',
    analyze: 'ChatGPT Web / validación',
    publish: 'Publicación',
    queued: 'En cola',
  };
  const lines = [
    stale
      ? 'SIN SEÑAL: el heartbeat del proceso está obsoleto.'
      : allWorkersRateLimited
        ? waitingForAttachments
          ? 'ChatGPT Web sin cupo temporal de adjuntos; lote en espera'
          : 'ChatGPT Web limitado temporalmente; lote en espera'
        : waitingForWeb
          ? 'Un trabajador Web limitado; el otro puede continuar'
        : webStalled
          ? 'POSIBLE ATASCO WEB: revisar la subfase indicada'
        : 'Análisis de mercado en curso',
    `Fase actual: ${phaseLabels[current.phase] || current.phase || 'En cola'}`,
    `Ticker actual: ${current.ticker || '-'}`,
    `Trabajadores Web: ${Number(web.worker_count || webWorkers.length || 1)}`,
    `Preparados: ${Number(counts.prepared || 0)}/${Number(progress.total || 0)}`,
    `Validados (intento actual): ${Number(counts.validated || 0)}/${Number(progress.total || 0)}`,
    `Publicados: ${Number(counts.published || 0)}/${Number(progress.total || 0)}`,
    `Fallidos: ${Number(counts.failed || 0)}`,
    `Reintentos: ${Number(counts.retries || 0)} (${Number(counts.chatgpt_web_retries || 0)} Web · ${Number(counts.pipeline_retries || 0)} de lote)`,
    `Bloqueos por demasiadas peticiones: ${requestRateLimitCount}`,
    `Límites temporales de adjuntos: ${attachmentLimitCount}`,
    `Chats actuales: ${Number(web.chat_group_tickers || 0)}/${Number(web.chat_group_size || 0)} tickers`,
    `Proveedor previsto: ${analysisProgressProviderLabel_(progress.provider)}`,
    `Transcurrido: ${formatAnalysisProgressDuration_(progress.elapsed_seconds)}`,
    `ETA: ${formatAnalysisProgressDuration_(progress.eta_seconds)}`,
    `Heartbeat: ${progress.heartbeat_at || '-'}`,
  ];
  const workerLines = webWorkers.map((worker, index) => {
    const workerId = Number(worker.worker_id || index + 1);
    const chatUsage = `${Number(worker.chat_group_tickers || 0)}/${Number(worker.chat_group_size || 0)}`;
    if (worker.attachment_rate_limit_waiting) {
      return `Web ${workerId}: espera global por cupo de adjuntos hasta ${analysisProgressDateTime_(worker.rate_limit_resume_at)} · chat ${chatUsage}`;
    }
    if (worker.rate_limit_waiting) {
      return `Web ${workerId}: espera por demasiadas peticiones hasta ${analysisProgressDateTime_(worker.rate_limit_resume_at)} · chat ${chatUsage}`;
    }
    if (!worker.active_ticker) {
      return `Web ${workerId}: libre · chat ${chatUsage}`;
    }
    return `Web ${workerId}: ${worker.active_ticker} · intento ${Number(worker.active_attempt || 1)} · ${analysisWebStageLabel_(worker.active_stage)} · ${formatAnalysisProgressDuration_(worker.active_stage_elapsed_seconds)} · chat ${chatUsage}`;
  });
  lines.splice(3, 0, ...workerLines);
  if (waitingTickers.length > 0) {
    lines.splice(5, 0, `Esperando turno Web: ${waitingTickers.join(', ')}`);
  }
  if (progress.generation_providers) {
    lines.splice(
      10,
      0,
      `Generación real: ChatGPT Web ${Number(providers['chatgpt-browser'] || 0)} · ${progress.provider === 'codex' ? 'Codex' : 'Codex fallback'} ${Number(providers.codex || 0)} · Sin registrar ${Number(providers.unknown || 0)}`
    );
  }
  if (waitingForWeb && web.rate_limit_resume_at) {
    lines.splice(
      3,
      0,
      `Reanudación Web prevista: ${analysisProgressDateTime_(web.rate_limit_resume_at)}`
    );
  }
  const failedTickers = Array.isArray(progress.failed_tickers)
    ? progress.failed_tickers
    : [];
  if (failedTickers.length > 0) {
    lines.push(`Tickers fallidos: ${failedTickers.join(', ')}`);
  }
  const fallbackTickers = Array.isArray(progress.fallback_tickers)
    ? progress.fallback_tickers
    : [];
  if (fallbackTickers.length > 0) {
    lines.push(`Codex fallback: ${fallbackTickers.join(', ')}`);
  }
  return lines.join('\n');
}

function analysisCodexProgressNote_(progress, stale) {
  const counts = progress.counts || {};
  const current = progress.current || {};
  const total = Number(progress.total || 0);
  const statusLabels = {
    completed: 'Mercado completado',
    failed: 'Mercado con errores',
  };
  const status = stale ? 'SIN SEÑAL: estado sin actualizar'
    : statusLabels[progress.status] || 'Mercado en curso';
  const lines = [
    `${status} · ${Number(counts.published || 0)}/${total} publicados`,
  ];
  // Counts describe published outcomes, not paid calls. Conserved means
  // kept by routine review; a full report is not a new ticker. Name the work,
  // not a hard-coded model: routine and full roles can use the same model.
  if (Object.prototype.hasOwnProperty.call(counts, 'retained_reports') &&
      Object.prototype.hasOwnProperty.call(counts, 'regenerated_reports')) {
    const retained = Number(counts.retained_reports || 0);
    const updated = Number(counts.updated_reports || 0);
    const regenerated = Number(counts.regenerated_reports || 0);
    lines.push(`Revisión: ${retained} ${retained === 1 ? 'conservado' : 'conservados'} · ${updated} ${updated === 1 ? 'actualizado' : 'actualizados'}`);
    lines.push(`Informes completos: ${regenerated}`);
    const unclassified = Math.max(0, Number(counts.published || 0) -
      Number(counts.retained_reports || 0) - Number(counts.updated_reports || 0) -
      Number(counts.regenerated_reports || 0));
    if (unclassified > 0) {
      lines.push(`Sin clasificar: ${unclassified} ${unclassified === 1 ? 'publicado' : 'publicados'}`);
    }
  } else {
    lines.push('Reparto revisión/completos: pendiente');
  }
  const failedTickers = Array.isArray(progress.failed_tickers) ? progress.failed_tickers : [];
  lines.push(`Fallidos: ${Number(counts.failed || 0)}${failedTickers.length > 0 ? ' (' + failedTickers.join(', ') + ')' : ''} · Reintentos: ${Number(counts.pipeline_retries || 0)}`);
  const elapsed = formatAnalysisProgressDuration_(progress.elapsed_seconds);
  const remaining = formatAnalysisProgressDuration_(progress.eta_seconds);
  lines.push(`${elapsed === '-' ? 'Tiempo transcurrido: -' : elapsed + ' transcurridos'} · ${remaining === '-' ? 'restante sin estimación' : '~' + remaining + ' restantes'}`);
  // Keep the timestamp for stale diagnostics, not as noise in a healthy run.
  if (stale) {
    if (current.ticker) lines.push(`Última actividad: ${current.ticker}`);
    lines.push(`Última señal: ${analysisProgressDateTime_(progress.heartbeat_at)}`);
  }
  return lines.join('\n');
}

function analysisWebStageLabel_(stage) {
  const labels = {
    open_browser: 'Abrir navegador',
    navigate: 'Abrir chat',
    rate_limit_before_attach: 'Comprobar límite antes de adjuntar',
    attachment_limit_wait: 'Esperar cupo de adjuntos',
    locate_composer: 'Localizar editor',
    attach: 'Adjuntar archivos',
    confirm_attachments: 'Confirmar adjuntos',
    rate_limit_before_send: 'Comprobar límite antes de enviar',
    compose: 'Escribir solicitud',
    wait_send_ready: 'Esperar botón de envío',
    send: 'Enviar',
    wait_request_start: 'Confirmar inicio de solicitud',
    wait_assistant: 'Esperar comienzo de respuesta',
    wait_response: 'Esperar respuesta completa',
    extract: 'Extraer Markdown',
    complete: 'Respuesta recibida',
    request: 'Solicitud Web',
    failed: 'Fallo Web',
  };
  return labels[stage] || String(stage || '-');
}

function analysisProgressDateTime_(value) {
  const parsed = new Date(value || '');
  if (!Number.isFinite(parsed.getTime())) {
    return '-';
  }
  return Utilities.formatDate(
    parsed,
    Session.getScriptTimeZone(),
    'dd/MM/yyyy HH:mm:ss'
  );
}

function analysisProgressProviderLabel_(provider) {
  if (provider === 'codex') {
    return 'Codex';
  }
  return provider === 'chatgpt-browser'
    ? 'ChatGPT Web (Codex como fallback)'
    : String(provider || '-');
}

function formatAnalysisProgressDuration_(seconds) {
  if (seconds === null || seconds === undefined || seconds === '') {
    return '-';
  }
  const numeric = Number(seconds);
  if (!Number.isFinite(numeric) || numeric < 0) {
    return '-';
  }
  const totalMinutes = Math.round(numeric / 60);
  const hours = Math.floor(totalMinutes / 60);
  const minutes = totalMinutes % 60;
  return hours > 0 ? `${hours} h ${minutes} min` : `${minutes} min`;
}

function clearAnalysisProgressIndicator_() {
  const spreadsheet = SpreadsheetApp.getActiveSpreadsheet();
  const sheet = spreadsheet.getSheetByName(ANALYSIS_PROGRESS_SHEET);

  if (!sheet) {
    return;
  }

  migrateAnalysisProgressRows_(sheet);

  sheet.getRange(ANALYSIS_PROGRESS_CELL)
    .clearContent()
    .clearNote()
    .setBackground(null);
}

function setAnalysisFailureIndicator_(result) {
  const spreadsheet = SpreadsheetApp.getActiveSpreadsheet();
  const sheet = spreadsheet.getSheetByName(ANALYSIS_PROGRESS_SHEET);

  if (!sheet) {
    return;
  }

  migrateAnalysisProgressRows_(sheet);
  const lines = [
    'El análisis local terminó con error.',
    `Orden: ${String(result.id || '-')}`,
    `Acción: ${String(result.action || '-')}`,
  ];
  if (result.finished_at) {
    lines.push(`Fin: ${String(result.finished_at)}`);
  }
  if (result.error_type) {
    lines.push(`Tipo: ${String(result.error_type)}`);
  }
  if (result.error_message) {
    lines.push(`Motivo: ${String(result.error_message)}`);
  }

  sheet.getRange(ANALYSIS_PROGRESS_CELL)
    .setValue(ANALYSIS_PROGRESS_FAILED)
    .setNumberFormat('@')
    .setBackground(ANALYSIS_PROGRESS_BACKGROUNDS[ANALYSIS_PROGRESS_FAILED])
    .setNote(lines.join('\n'));
}

function migrateAnalysisProgressRows_(sheet) {
  if (sheet.getName() === 'Bolsa_2026') {
    const tradingCell = sheet.getRange('AD5');
    const coreCell = sheet.getRange('AD6');
    const values = [tradingCell.getDisplayValue(), coreCell.getDisplayValue()];

    if (values[0].startsWith('Trading:') && values[1].startsWith('Core:')) {
      coreCell.moveTo(sheet.getRange('AD7'));
      tradingCell.moveTo(sheet.getRange('AD6'));
    }
  }

  ANALYSIS_PROGRESS_LEGACY_CELLS.forEach((cellA1) => {
    sheet.getRange(cellA1)
      .clearContent()
      .clearNote()
      .setBackground(null);
  });
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
    error_type: String(result.error_type || '').slice(0, 120),
    error_message: String(result.error_message || '').slice(0, 500),
    batch_success: Number(result.batch_success || 0),
    batch_total: Number(result.batch_total || 0),
    batch_failed: Number(result.batch_failed || 0),
  };
}

function readLastAnalysisCommandStatus_() {
  const raw = PropertiesService.getScriptProperties().getProperty(
    ANALYSIS_LAST_STATUS_PROPERTY
  );
  if (!raw) {
    return null;
  }
  try {
    const parsed = JSON.parse(raw);
    return parsed && typeof parsed === 'object' ? parsed : null;
  } catch (error) {
    console.log(`Estado anterior de análisis inválido: ${error}`);
    return null;
  }
}

function applyCompletedAnalysisCommand_(result) {
  if (result.action === 'analyze_market') {
    applyMarketBatchSummary_(result);
    return;
  }

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

function applyMarketBatchSummary_(result) {
  const spreadsheet = SpreadsheetApp.getActiveSpreadsheet();
  const sheet = spreadsheet.getSheetByName(ANALYSIS_PROGRESS_SHEET);
  if (!sheet) {
    return;
  }

  const batchStatus = readMatchingMarketBatchStatus_(result);
  const finishedAt = new Date(
    (batchStatus && batchStatus.finished_at) || result.finished_at || Date.now()
  );
  const validFinishedAt = Number.isFinite(finishedAt.getTime())
    ? finishedAt
    : new Date();
  const updateDate = Utilities.formatDate(
    validFinishedAt,
    Session.getScriptTimeZone(),
    'dd/MM/yyyy'
  );
  const fallback = batchStatus && batchStatus.generation_fallback;
  const usedFallback = Boolean(fallback && fallback.used);

  sheet.getRange(ANALYSIS_MARKET_DATE_CELL)
    .setValue(`Mercado: ${updateDate}`)
    .setNumberFormat('@')
    .setBackground(usedFallback ? '#fff2cc' : null)
    .setNote(analysisFinalSummaryNote_(result, batchStatus));
  sheet.getRange(ANALYSIS_MARKET_LEGACY_DATE_CELL)
    .clearContent()
    .clearNote()
    .setBackground(null);
}

function readMatchingMarketBatchStatus_(result) {
  const summary = readAnalysisGcsJson_('batch/status/latest_trading.json');
  if (!summary) {
    return null;
  }
  const batchFinished = Date.parse(summary.finished_at || '');
  const commandStarted = Date.parse(result.started_at || '');
  const commandFinished = Date.parse(result.finished_at || '');
  if (!Number.isFinite(batchFinished)) {
    return null;
  }
  if (Number.isFinite(commandStarted) && batchFinished < commandStarted - 60000) {
    return null;
  }
  if (Number.isFinite(commandFinished) && batchFinished > commandFinished + 60000) {
    return null;
  }
  return summary;
}

function analysisFinalSummaryNote_(result, batchStatus) {
  const summary = batchStatus || {};
  const success = Number(summary.success ?? result.batch_success ?? 0);
  const failed = Number(summary.failed ?? result.batch_failed ?? 0);
  const total = Number(summary.total ?? result.batch_total ?? success + failed);
  const duration = Number(summary.duration_seconds ?? result.duration_seconds);
  const fallback = summary.generation_fallback || {};
  const fallbackTickers = Array.isArray(fallback.tickers)
    ? fallback.tickers
    : [];
  const fallbackCount = Number(fallback.count || fallbackTickers.length || 0);
  const providers = summary.generation_providers || {};
  const web = providers['chatgpt-browser'] || {};
  const webCount = Number.isFinite(Number(web.count))
    ? Number(web.count)
    : Math.max(0, success - fallbackCount);
  const retries = summary.retry_summary || {};
  const results = Array.isArray(summary.results) ? summary.results : [];
  const legacyBatchRetries = results.reduce(
    (sum, item) => sum + Math.max(0, Number(item.attempt || 1) - 1),
    0
  );
  const batchRetries = Number(retries.batch ?? legacyBatchRetries);
  const webRetries = Number(retries.chatgpt_web || 0);
  const lines = [
    'Última actualización completa de Mercado',
    `Resultado: ${success}/${total} publicados · ${failed} fallidos`,
    `Duración: ${formatAnalysisProgressDuration_(duration)}`,
    `ChatGPT Web: ${webCount}`,
    `Codex fallback: ${fallbackCount}`,
    `Reintentos: ${batchRetries + webRetries} (${webRetries} Web · ${batchRetries} de lote)`,
    `Inicio: ${analysisSummaryDateTime_(summary.started_at || result.started_at)}`,
    `Fin: ${analysisSummaryDateTime_(summary.finished_at || result.finished_at)}`,
  ];
  if (summary.strategy === 'adaptive-codex-v1') {
    // Ignore legacy browser metadata: these are report outcomes, not paid calls.
    lines.splice(1, lines.length - 1,
      `Resultado: ${success}/${total} revisados y publicados · ${failed} pendientes/fallidos`,
      `Duración: ${formatAnalysisProgressDuration_(duration)}`,
      `Informes completos: ${Number(summary.regenerated_reports || 0)}`,
      `Actualizados en revisión: ${Number(summary.updated_reports || 0)}`,
      `Conservados en revisión: ${Number(summary.retained_reports || 0)} · sin cambiar su fecha`,
      `Reintentos de lote: ${batchRetries}`,
      `Inicio: ${analysisSummaryDateTime_(summary.started_at || result.started_at)}`,
      `Fin: ${analysisSummaryDateTime_(summary.finished_at || result.finished_at)}`
    );
  }
  if (summary.strategy !== 'adaptive-codex-v1' && fallbackTickers.length > 0) {
    lines.push(`Fallback Codex: ${fallbackTickers.join(', ')}`);
  }
  const failedResults = results.filter((item) => item.status !== 'ok');
  if (failedResults.length > 0) {
    lines.push('', 'Errores');
    failedResults.forEach((item) => {
      const reason = String(item.error_message || item.error_type || 'fallo').slice(0, 180);
      lines.push(`- ${item.ticker}: ${reason}`);
    });
  } else if (failed > 0 && result.error_message) {
    lines.push('', `Errores: ${String(result.error_message).slice(0, 300)}`);
  }
  return lines.join('\n');
}

function analysisSummaryDateTime_(value) {
  const parsed = new Date(value || '');
  if (!Number.isFinite(parsed.getTime())) {
    return '-';
  }
  return Utilities.formatDate(
    parsed,
    Session.getScriptTimeZone(),
    'dd/MM/yyyy HH:mm'
  );
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

function readDiscoverableAnalysisProgress_() {
  const latest = readAnalysisGcsJson_(ANALYSIS_LATEST_PROGRESS_OBJECT);
  if (analysisProgressIsActive_(latest)) {
    return latest;
  }

  const status = readLatestAnalysisCommandStatus_();
  const commandId = status && String(status.id || '');
  return commandId
    ? readAnalysisCommandResult_(commandId, 'progress')
    : latest;
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
