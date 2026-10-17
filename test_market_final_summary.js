const assert = require('assert');
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const cells = {};
const properties = {};
function rangeFor(a1) {
  cells[a1] = cells[a1] || {};
  const state = cells[a1];
  return {
    setValue(value) { state.value = value; return this; },
    setNumberFormat(value) { state.numberFormat = value; return this; },
    setBackground(value) { state.background = value; return this; },
    setNote(value) { state.note = value; return this; },
    clearContent() { state.value = ''; return this; },
    clearNote() { state.note = ''; return this; },
  };
}

const sheet = { getRange: rangeFor };
const context = {
  console,
  SpreadsheetApp: {
    getActiveSpreadsheet() {
      return { getSheetByName: (name) => name === 'Mercado' ? sheet : null };
    },
  },
  Session: { getScriptTimeZone: () => 'Europe/Madrid' },
  Utilities: {
    formatDate(_date, _zone, format) {
      return format === 'dd/MM/yyyy' ? '10/09/2026' : '10/09/2026 13:30';
    },
  },
  PropertiesService: {
    getScriptProperties() {
      return {
        getProperty: (key) => properties[key] || null,
        setProperty: (key, value) => { properties[key] = value; },
      };
    },
  },
};
vm.createContext(context);
vm.runInContext(
  fs.readFileSync(
    path.join(__dirname, 'apps_script', 'analysis_completion_sync.gs'),
    'utf8'
  ),
  context
);

const summary = {
  started_at: '2026-09-10T10:00:00Z',
  finished_at: '2026-09-10T11:30:00Z',
  duration_seconds: 5400,
  success: 3,
  failed: 1,
  total: 4,
  generation_providers: { 'chatgpt-browser': { count: 2 } },
  generation_fallback: { used: true, count: 1, tickers: ['BBB'] },
  retry_summary: { batch: 1, chatgpt_web: 2, total: 3 },
  results: [
    { ticker: 'AAA', status: 'ok', attempt: 1 },
    { ticker: 'BBB', status: 'ok', attempt: 2 },
    { ticker: 'CCC', status: 'ok', attempt: 1 },
    { ticker: 'DDD', status: 'failed', error_message: 'validation failed' },
  ],
};
context.readMatchingMarketBatchStatus_ = () => summary;
context.applyMarketBatchSummary_({
  action: 'analyze_market',
  started_at: summary.started_at,
  finished_at: summary.finished_at,
});

assert.strictEqual(cells.A9.value, 'Mercado: 10/09/2026');
assert.strictEqual(cells.A9.background, '#fff2cc');
assert.match(cells.A9.note, /Resultado: 3\/4 publicados · 1 fallidos/);
assert.match(cells.A9.note, /ChatGPT Web: 2/);
assert.match(cells.A9.note, /Codex fallback: 1/);
assert.match(cells.A9.note, /Reintentos: 3 \(2 Web · 1 de lote\)/);
assert.match(cells.A9.note, /DDD: validation failed/);
assert.strictEqual(cells.A10.value, '');
assert.strictEqual(cells.A10.note, '');

context.readAnalysisGcsJson_ = () => summary;
assert.strictEqual(context.reconcileLatestMarketBatchSummary_(), true);
assert.strictEqual(
  properties.ANALYSIS_LAST_MARKET_SUMMARY_FINISHED_AT,
  '2026-09-10T11:30:00.000Z'
);
assert.strictEqual(context.reconcileLatestMarketBatchSummary_(), false);

// Old adaptive summaries lack updated_reports; new ones distinguish all outcomes.
const oldAdaptive = { ...summary, strategy: 'adaptive-codex-v1',
  retained_reports: 1, regenerated_reports: 2 };
const oldAdaptiveNote = context.analysisFinalSummaryNote_({}, oldAdaptive);
assert.match(oldAdaptiveNote, /Informes completos: 2/);
assert.match(oldAdaptiveNote, /Actualizados en revisión: 0/);
assert.match(oldAdaptiveNote, /Conservados en revisión: 1 · sin cambiar su fecha/);
assert.match(oldAdaptiveNote, /Reintentos de lote: 1/);
assert.match(oldAdaptiveNote, /DDD: validation failed/);
assert.doesNotMatch(oldAdaptiveNote, /Web|fallback/i);
const updatedAdaptive = { ...oldAdaptive, updated_reports: 1, retained_reports: 1, regenerated_reports: 1 };
const updateNote = context.analysisFinalSummaryNote_({}, updatedAdaptive);
assert.match(updateNote, /Informes completos: 1/);
assert.match(updateNote, /Actualizados en revisión: 1/);
assert.match(updateNote, /Conservados en revisión: 1/);
assert.match(updateNote, /Resultado: 3\/4 revisados y publicados · 1 pendientes\/fallidos/);
assert.doesNotMatch(updateNote, /Web|fallback|NaN/i);
context.readMatchingMarketBatchStatus_ = () => updatedAdaptive;
context.applyMarketBatchSummary_({ action: 'analyze_market',
  started_at: updatedAdaptive.started_at, finished_at: updatedAdaptive.finished_at });
assert.strictEqual(cells.A9.note, updateNote);

console.log('Market final summary tests passed.');
