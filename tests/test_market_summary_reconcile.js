const assert = require('assert');
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const summary = {
  strategy: 'adaptive-codex-v1',
  started_at: '2026-10-21T06:52:46.291667+00:00',
  finished_at: '2026-10-21T07:33:33.301972+00:00',
  success: 46, total: 46, failed: 0, duration_seconds: 2447.01,
  regenerated_reports: 2, updated_reports: 0, retained_reports: 44,
};
let applied = new Date(summary.finished_at).toISOString();
let writes = 0;
let missingSheet = false;
const cells = {};
function cell(address) {
  if (!cells[address]) cells[address] = {
    value: '', note: '',
    getDisplayValue() { return this.value; },
    getNote() { return this.note; },
    setValue(value) { this.value = value; writes++; return this; },
    setNumberFormat() { return this; },
    setBackground() { return this; },
    setNote(note) { this.note = note; return this; },
    clearContent() { this.value = ''; return this; },
    clearNote() { this.note = ''; return this; },
  };
  return cells[address];
}
const context = {
  PropertiesService: { getScriptProperties: () => ({
    getProperty: () => applied,
    setProperty: (key, value) => { applied = value; },
  }) },
  SpreadsheetApp: { getActiveSpreadsheet: () => ({
    getSheetByName: () => missingSheet ? null : { getRange: cell },
  }) },
  Session: { getScriptTimeZone: () => 'Europe/Madrid' },
  Utilities: { formatDate(date, timeZone, format) {
    const parts = new Intl.DateTimeFormat('en-GB', {
      timeZone, day: '2-digit', month: '2-digit', year: 'numeric',
      hour: '2-digit', minute: '2-digit', hourCycle: 'h23',
    }).formatToParts(date);
    const get = type => parts.find(p => p.type === type).value;
    const day = `${get('day')}/${get('month')}/${get('year')}`;
    return format === 'dd/MM/yyyy' ? day : `${day} ${get('hour')}:${get('minute')}`;
  } },
};
vm.createContext(context);
vm.runInContext(fs.readFileSync(path.join(__dirname, '..', 'apps_script',
  'analysis_completion_sync.gs'), 'utf8'), context);
context.readAnalysisGcsJson_ = object => {
  assert.strictEqual(object, 'batch/status/latest_trading.json');
  return summary;
};

// The receipt survives, but the visible cell and note have been erased.
assert.strictEqual(context.reconcileLatestMarketBatchSummary_(), true);
assert.strictEqual(cell('A9').value, 'Mercado: 21/10/2026');
assert.match(cell('A9').note, /46\/46 revisados y publicados · 0 pendientes\/fallidos/);
assert.match(cell('A9').note, /Informes completos: 2/);
assert.match(cell('A9').note, /Conservados en revisión: 44/);
assert.match(cell('A9').note, /Fin: 21\/10\/2026 09:33/);
assert.strictEqual(writes, 1);
assert.strictEqual(context.reconcileLatestMarketBatchSummary_(), false);
assert.strictEqual(writes, 1);

// A surviving date alone is insufficient; restore the detailed note too.
cell('A9').note = '';
assert.strictEqual(context.reconcileLatestMarketBatchSummary_(), true);
assert.strictEqual(writes, 2);
summary.retained_reports = 43;
summary.updated_reports = 1;
assert.strictEqual(context.reconcileLatestMarketBatchSummary_(), true);
assert.match(cell('A9').note, /Actualizados en revisión: 1/);

missingSheet = true;
applied = '';
assert.strictEqual(context.reconcileLatestMarketBatchSummary_(), false);
assert.strictEqual(applied, '');
assert.strictEqual(writes, 3);
console.log('Market summary reconciliation tests passed.');
