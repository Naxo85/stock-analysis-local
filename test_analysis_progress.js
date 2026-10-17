const assert = require('assert');
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const context = {
  console,
  Session: { getScriptTimeZone: () => 'Europe/Madrid' },
  Utilities: { formatDate: date => date.toISOString() },
};
vm.createContext(context);
vm.runInContext(
  fs.readFileSync(
    path.join(__dirname, 'apps_script', 'analysis_completion_sync.gs'),
    'utf8'
  ),
  context
);

const progress = {
  status: 'running',
  heartbeat_at: new Date().toISOString(),
  total: 34,
  completed: 12,
  counts: {
    prepared: 20,
    validated: 13,
    published: 12,
    failed: 1,
    retries: 2,
    chatgpt_web_retries: 1,
    pipeline_retries: 1,
  },
  current: { phase: 'analyze', ticker: 'NVDA' },
  provider: 'chatgpt-browser',
  generation_providers: {
    'chatgpt-browser': 8,
    codex: 3,
    unknown: 1,
  },
  fallback_tickers: ['AMD', 'RKLB', 'IONQ'],
  elapsed_seconds: 4200,
  eta_seconds: 3600,
  failed_tickers: ['PLTR'],
  chatgpt_web: {
    worker_count: 2,
    chat_group_size: 10,
    chat_group_tickers: 3,
    rate_limit_count: 2,
    rate_limit_waiting: true,
    all_workers_rate_limited: false,
    rate_limit_resume_at: new Date(Date.now() + 15 * 60 * 1000).toISOString(),
    workers: [
      {
        worker_id: 1,
        chat_group_size: 5,
        chat_group_tickers: 2,
        active_ticker: 'NVDA',
        active_attempt: 1,
        active_stage: 'wait_response',
        active_stage_elapsed_seconds: 180,
      },
      {
        worker_id: 2,
        chat_group_size: 5,
        chat_group_tickers: 1,
        active_ticker: 'TSLA',
        active_attempt: 2,
        active_stage: 'attach',
        active_stage_elapsed_seconds: 12,
        rate_limit_waiting: false,
      },
    ],
  },
};

assert.strictEqual(
  context.analysisProgressCellValue_('RUNNING', progress),
  'RUNNING 12/34'
);
assert.strictEqual(context.analysisProgressIsStale_(progress), false);
assert.strictEqual(context.analysisProgressIsActive_(progress), true);
assert.strictEqual(
  context.analysisProgressDisplayStatus_('RUNNING', progress),
  'RUNNING'
);
assert.strictEqual(
  context.analysisProgressIsActive_({
    status: 'completed',
    heartbeat_at: new Date().toISOString(),
  }),
  false
);
const recoveredProgress = {
  command_id: 'market-123',
  status: 'completed',
  heartbeat_at: '2026-09-18T18:55:05+02:00',
  total: 47,
  counts: { published: 47, failed: 0 },
};
const failedCommand = {
  id: 'market-123',
  status: 'failed',
  finished_at: '2026-09-18T17:58:35+02:00',
};
assert.strictEqual(
  context.analysisProgressRecoversFailure_(recoveredProgress, failedCommand),
  true
);
assert.strictEqual(
  context.analysisProgressRecoversFailure_(
    { ...recoveredProgress, counts: { published: 46, failed: 1 } },
    failedCommand
  ),
  false
);
assert.strictEqual(
  context.analysisProgressRecoversFailure_(
    { ...recoveredProgress, command_id: 'another-command' },
    failedCommand
  ),
  false
);
assert.strictEqual(
  context.analysisProgressIsStale_({
    heartbeat_at: new Date(Date.now() - 4 * 60 * 1000).toISOString(),
  }),
  true
);
const note = context.analysisProgressNote_(progress, false);
assert.match(note, /Ticker actual: NVDA/);
assert.match(note, /Publicados: 12\/34/);
assert.match(note, /Reintentos: 2 \(1 Web · 1 de lote\)/);
assert.match(note, /Bloqueos por demasiadas peticiones: 2/);
assert.match(note, /Un trabajador Web limitado; el otro puede continuar/);
assert.match(note, /Trabajadores Web: 2/);
assert.match(note, /Web 1: NVDA · intento 1 · Esperar respuesta completa · 3 min · chat 2\/5/);
assert.match(note, /Web 2: TSLA · intento 2 · Adjuntar archivos · 0 min · chat 1\/5/);
assert.match(note, /Chats actuales: 3\/10 tickers/);
assert.match(note, /Generación real: ChatGPT Web 8 · Codex fallback 3 · Sin registrar 1/);
assert.match(note, /Codex fallback: AMD, RKLB, IONQ/);
assert.match(note, /Reanudación Web prevista:/);
assert.match(note, /ETA: 1 h 0 min/);
assert.match(note, /Tickers fallidos: PLTR/);

const attachmentLimited = JSON.parse(JSON.stringify(progress));
attachmentLimited.chatgpt_web.request_rate_limit_count = 2;
attachmentLimited.chatgpt_web.attachment_rate_limit_count = 1;
attachmentLimited.chatgpt_web.attachment_rate_limit_waiting = true;
attachmentLimited.chatgpt_web.all_workers_rate_limited = true;
attachmentLimited.chatgpt_web.workers.forEach(worker => {
  worker.attachment_rate_limit_waiting = true;
  worker.rate_limit_waiting = true;
  worker.rate_limit_resume_at = attachmentLimited.chatgpt_web.rate_limit_resume_at;
  worker.active_stage = 'attachment_limit_wait';
});
const attachmentNote = context.analysisProgressNote_(attachmentLimited, false);
assert.match(attachmentNote, /sin cupo temporal de adjuntos; lote en espera/);
assert.match(attachmentNote, /Bloqueos por demasiadas peticiones: 2/);
assert.match(attachmentNote, /Límites temporales de adjuntos: 1/);
assert.match(attachmentNote, /espera global por cupo de adjuntos hasta/);

const codexProgress = {
  ...progress,
  provider: 'codex',
  current: {
    phase: 'analyze', ticker: 'NVDA',
    preparing: ['MU'], analyzing: ['NVDA', 'CAT'], publishing: ['RKLB'],
  },
  counts: { ...progress.counts, retained_reports: 7, regenerated_reports: 5 },
  // Obsolete data must not affect Codex labels, status, or retry accounting.
  chatgpt_web: attachmentLimited.chatgpt_web,
  eta_seconds: null,
};
const codexNote = context.analysisProgressNote_(codexProgress, false);
assert.strictEqual(context.analysisProgressDisplayStatus_('RUNNING', codexProgress), 'RUNNING');
assert.match(codexNote, /^Mercado en curso · 12\/34 publicados/);
assert.doesNotMatch(codexNote, /Analizando:|Preparando:|Publicando:|Preparados:|Validados:|Publicados:/);
assert.match(codexNote, /Revisión: 7 conservados · 0 actualizados/);
assert.match(codexNote, /Informes completos: 5/);
assert.match(codexNote, /Reintentos: 1/);
assert.match(codexNote, /Fallidos: 1/);
assert.match(codexNote, /Fallidos: 1 \(PLTR\)/);
assert.match(codexNote, /1 h 10 min transcurridos · restante sin estimación/);
assert.doesNotMatch(codexNote, /sin clasificar|Heartbeat|Última señal|Flujo:|Ticker actual:/);
const updateNote = context.analysisProgressNote_({
  ...codexProgress,
  counts: { ...codexProgress.counts, retained_reports: 4, updated_reports: 4, regenerated_reports: 4 },
}, false);
assert.match(updateNote, /Revisión: 4 conservados · 4 actualizados/);
assert.doesNotMatch(updateNote, /sin clasificar|Web|fallback/);
assert.match(context.analysisProgressNote_({
  ...codexProgress, counts: { published: 1, retained_reports: 0, regenerated_reports: 0 },
}, false), /Sin clasificar: 1 publicado/);
assert.doesNotMatch(codexNote, /Web|chat|adjuntos|fallback|Generación real|Sin registrar/i);
assert.match(context.analysisProgressNote_(codexProgress, true), /^SIN SEÑAL:/);
assert.match(context.analysisProgressNote_({ ...codexProgress, status: 'failed' }, false), /^Mercado con errores/);
assert.match(context.analysisProgressNote_({ ...codexProgress, status: 'completed' }, false), /^Mercado completado/);
const minimalCodexNote = context.analysisProgressNote_({ provider: 'codex' }, false);
assert.doesNotMatch(minimalCodexNote, /Web|NaN|Informes conservados|Informes regenerados/);
assert.match(minimalCodexNote, /restante sin estimación/);
assert.doesNotMatch(minimalCodexNote, /conservados|\(Luna\)|\(Sol\)/);
assert.match(minimalCodexNote, /Reparto revisión\/completos: pendiente/);
const compactExample = {
  provider: 'codex', total: 46, status: 'running',
  counts: { prepared: 17, validated: 8, published: 7, failed: 0, pipeline_retries: 0,
    retained_reports: 4, updated_reports: 3, regenerated_reports: 0 },
  current: { phase: 'analyze', ticker: 'IREN', preparing: ['CIFR'],
    analyzing: ['IREN', 'GEV', 'IBKR', 'AMD', 'SNDK', 'GOOG'], publishing: ['ASML'] },
  elapsed_seconds: 300, eta_seconds: 1620,
  heartbeat_at: '2026-10-05T10:36:44.470138+00:00',
};
assert.strictEqual(context.analysisProgressNote_(compactExample, false), [
  'Mercado en curso · 7/46 publicados',
  'Revisión: 4 conservados · 3 actualizados',
  'Informes completos: 0',
  'Fallidos: 0 · Reintentos: 0',
  '5 min transcurridos · ~27 min restantes',
].join('\n'));
assert.match(context.analysisProgressNote_(compactExample, true), /Última señal: 2026-10-05T10:36:44/);
assert.match(context.analysisProgressNote_({ provider: 'codex',
  current: { phase: 'analyze', ticker: 'IREN' } }, true), /Última actividad: IREN/);
// The screenshot-approved layout stays five lines even with many active workers.
const screenshotExample = {
  ...compactExample,
  counts: { ...compactExample.counts, published: 3, retained_reports: 2, updated_reports: 1 },
  elapsed_seconds: 240, eta_seconds: 3120,
};
assert.strictEqual(context.analysisProgressNote_(screenshotExample, false), [
  'Mercado en curso · 3/46 publicados',
  'Revisión: 2 conservados · 1 actualizado',
  'Informes completos: 0',
  'Fallidos: 0 · Reintentos: 0',
  '4 min transcurridos · ~52 min restantes',
].join('\n'));
const screenshotBefore = JSON.stringify(screenshotExample);
context.analysisProgressNote_(screenshotExample, true);
assert.strictEqual(JSON.stringify(screenshotExample), screenshotBefore);
assert.match(context.analysisProgressNote_({ ...screenshotExample,
  counts: { ...screenshotExample.counts, retained_reports: 1, regenerated_reports: 1 },
}, false), /Revisión: 1 conservado · 1 actualizado\nInformes completos: 1/);
assert.strictEqual(context.formatAnalysisProgressDuration_(undefined), '-');
assert.strictEqual(context.formatAnalysisProgressDuration_(0), '0 min');
assert.strictEqual(context.analysisProgressProviderLabel_('codex'), 'Codex');

// Exercise the actual C4 writer too, keeping the heartbeat warning and colour.
const written = {};
const c4Range = {
  setValue(value) { written.value = value; return this; },
  setNumberFormat() { return this; },
  setBackground(value) { written.background = value; return this; },
  setNote(value) { written.note = value; return this; },
};
context.SpreadsheetApp = { getActiveSpreadsheet: () => ({
  getSheetByName: name => name === 'Mercado' ? { getRange: () => c4Range } : null,
}) };
context.migrateAnalysisProgressRows_ = () => {};
context.setAnalysisProgressIndicator_('RUNNING', codexProgress);
assert.strictEqual(written.value, 'RUNNING 12/34');
assert.strictEqual(written.note, codexNote);
assert.strictEqual(written.background, '#d9ead3');
context.setAnalysisProgressIndicator_('RUNNING', {
  ...codexProgress, heartbeat_at: new Date(Date.now() - 5 * 60 * 1000).toISOString(),
});
assert.strictEqual(written.value, 'SIN SEÑAL');
assert.strictEqual(written.background, '#f4cccc');
assert.match(written.note, /^SIN SEÑAL:/);
assert.doesNotMatch(written.note, /Web|adjuntos|fallback/);

console.log('Analysis progress tests passed.');
