const MARKET_TRACKING_GROUPS = [
  {id: 'chips_hardware', label: 'Semis / Chips'},
  {id: 'memory', label: 'Semis / Memoria'},
  {id: 'chip_equipment', label: 'Semis / Equipamiento'},
  {id: 'ai_infrastructure', label: 'IA / Infraestructura'},
  {id: 'ai_platforms', label: 'IA / Plataformas'},
  {id: 'nuclear_grid', label: 'Energía / Nuclear y red'},
  {id: 'space', label: 'Industrial / Espacio'},
  {id: 'fintech_crypto', label: 'Finanzas / Fintech y cripto'},
  {id: 'critical_minerals', label: 'Recursos / Minerales'},
  {id: 'biotechnology', label: 'Salud / Biotecnología'},
  {id: 'digital_health', label: 'Salud / Salud digital'},
  {id: 'quantum', label: 'Tecnología / Cuántica'},
  {id: 'autonomy', label: 'Tecnología / Autonomía'},
  {id: 'industrials', label: 'Industrial / Industriales'},
];

function promptMarketShotPurchase() {
  const ui = SpreadsheetApp.getUi();
  const ticker = promptMarketTicker_(ui, 'He comprado 1 shot');
  if (!ticker) return;
  const marketIndex = marketTickerIndex_();
  const record = marketIndex[ticker] || null;
  let groupId = null;
  if (!record) {
    groupId = promptMarketGroup_(ui, ticker);
    if (!groupId) return;
  }
  applyMarketShotFromMenu_('portfolio_buy_shot', ticker, groupId);
}

function promptMarketShotSale() {
  const ui = SpreadsheetApp.getUi();
  const ticker = promptMarketTicker_(ui, 'He vendido 1 shot');
  if (!ticker) return;
  const marketIndex = marketTickerIndex_();
  const record = marketIndex[ticker] || null;
  if (!record) {
    ui.alert(`${ticker} no está en el seguimiento de Mercado.`);
    return;
  }
  if (record.shots < 1) {
    ui.alert(`${ticker} no aparece como posición abierta.`);
    return;
  }
  applyMarketShotFromMenu_('portfolio_sell_shot', ticker, null);
}

function promptRemoveMarketTicker() {
  const ui = SpreadsheetApp.getUi();
  const ticker = promptMarketTicker_(ui, 'Quitar ticker del seguimiento');
  if (!ticker) return;
  const marketIndex = marketTickerIndex_();
  const record = marketIndex[ticker] || null;
  if (!record) {
    ui.alert(`${ticker} no está en el seguimiento de Mercado.`);
    return;
  }
  const positionWarning = record.shots > 0
    ? ` También se eliminará su posición de ${record.shots === 1 ? '1 shot' : '2 o más shots'}.`
    : '';
  const confirmation = ui.alert(
    'Quitar del seguimiento',
    `¿Quitar ${ticker} de la tabla?${positionWarning}`,
    ui.ButtonSet.YES_NO
  );
  if (confirmation !== ui.Button.YES) return;
  enqueueAnalysisCommand_({
    action: 'market_remove_ticker',
    ticker,
    observed_shots: record.shots,
    portfolio_snapshot: marketPortfolioSnapshot_(marketIndex),
    portfolio_snapshot_at: marketIndex.snapshotTakenAt,
    track_analysis_status: false,
  });
}

function promptMarketTicker_(ui, title) {
  const response = ui.prompt(title, 'Introduce el ticker:', ui.ButtonSet.OK_CANCEL);
  if (response.getSelectedButton() !== ui.Button.OK) return null;
  const ticker = String(response.getResponseText() || '').trim().toUpperCase();
  if (!/^[A-Z][A-Z0-9.\-]{0,14}$/.test(ticker)) {
    ui.alert(`Ticker no válido: ${ticker}`);
    return null;
  }
  return ticker;
}

function promptMarketGroup_(ui, ticker) {
  const choices = MARKET_TRACKING_GROUPS.map(
    (group, index) => `${index + 1}. ${group.label}`
  ).join('\n');
  const response = ui.prompt(
    `Grupo para ${ticker}`,
    `Es un ticker nuevo. Escribe el número de su grupo:\n\n${choices}`,
    ui.ButtonSet.OK_CANCEL
  );
  if (response.getSelectedButton() !== ui.Button.OK) return null;
  const selected = Number(String(response.getResponseText() || '').trim());
  if (!Number.isInteger(selected) || selected < 1 || selected > MARKET_TRACKING_GROUPS.length) {
    ui.alert('Grupo no válido. Usa uno de los números mostrados.');
    return null;
  }
  return MARKET_TRACKING_GROUPS[selected - 1].id;
}

function marketPortfolioSnapshot_(marketIndex) {
  return Object.keys(marketIndex).reduce((snapshot, ticker) => {
    snapshot[ticker] = marketIndex[ticker].shots;
    return snapshot;
  }, {});
}

function marketTickerIndex_() {
  const spreadsheet = SpreadsheetApp.getActiveSpreadsheet();
  const sheet = spreadsheet.getSheetByName(MARKET_TICKER_EXPORT.sheetName);
  if (!sheet) throw new Error(`Sheet not found: ${MARKET_TICKER_EXPORT.sheetName}`);
  const result = {};
  Object.defineProperty(result, 'snapshotTakenAt', {value: new Date().toISOString()});
  findMarketTickerColumns_(sheet).forEach((column) => {
    const rowCount = sheet.getLastRow() - column.firstDataRow + 1;
    if (rowCount < 1) return;
    const range = sheet.getRange(column.firstDataRow, column.column, rowCount, 1);
    const values = range.getValues();
    const backgrounds = range.getBackgrounds();
    for (let index = 0; index < values.length; index += 1) {
      const ticker = String(values[index][0] || '').trim().toUpperCase();
      if (!ticker) break;
      const background = String(backgrounds[index][0] || '').toLowerCase();
      result[ticker] = {
        ticker,
        row: column.firstDataRow + index,
        column: column.column,
        shots: background === '#00b8d4' ? 2 : background === '#00ffff' ? 1 : 0,
      };
    }
  });
  return result;
}

// A confirmed menu action commits the portfolio and paints the sheet in this
// invocation. The queued request only reconciles mirrors/structure afterwards.
function applyMarketShotFromMenu_(action, ticker, groupId) {
  const lock = LockService.getScriptLock();
  lock.waitLock(15000);
  try {
    const index = marketTickerIndex_();
    const record = index[ticker];
    const command = enqueueAnalysisCommand_({
      action, ticker, group_id: groupId,
      observed_shots: record ? record.shots : 0,
      portfolio_snapshot: marketPortfolioSnapshot_(index),
      portfolio_snapshot_at: index.snapshotTakenAt,
      track_analysis_status: false,
    });
    const state = commitMarketShotImmediately_(command);
    paintMarketPortfolioImmediately_(state.layout, state.portfolio);
    SpreadsheetApp.flush();
    SpreadsheetApp.getActiveSpreadsheet().toast(
      `${ticker}: ${state.portfolio.positions[ticker] || 0} shots. Cartera actualizada.`,
      'Cartera', 5
    );
    return command;
  } finally {
    lock.releaseLock();
  }
}

// Re-render the committed portfolio without recording a purchase or sale.
function refreshMarketPortfolioNow() {
  const layout = readMarketRuntimeJson_(MARKET_RUNTIME_LAYOUT).value;
  const portfolio = readMarketRuntimeJson_(MARKET_RUNTIME_PORTFOLIO).value;
  paintMarketPortfolioImmediately_(layout, portfolio);
  SpreadsheetApp.flush();
  return {positions: Object.keys(portfolio.positions).length,
    shots: Object.values(portfolio.positions).reduce((sum, shots) => sum + shots, 0)};
}

const MARKET_RUNTIME_BUCKET = 'stock-analysis-system-naxo85';
const MARKET_RUNTIME_LAYOUT = 'runtime/config/market_sheet_layout.json';
const MARKET_RUNTIME_PORTFOLIO = 'runtime/config/portfolio.json';

function marketRuntimeFetch_(url, options) {
  return UrlFetchApp.fetch(url, Object.assign({
    headers: {Authorization: `Bearer ${ScriptApp.getOAuthToken()}`},
    muteHttpExceptions: true,
  }, options || {}));
}

function readMarketRuntimeJson_(name) {
  const url = `https://storage.googleapis.com/storage/v1/b/${MARKET_RUNTIME_BUCKET}/o/${encodeURIComponent(name)}`;
  const metadata = marketRuntimeFetch_(url);
  if (metadata.getResponseCode() !== 200) throw new Error(`No se pudo leer el estado de cartera (${metadata.getResponseCode()}).`);
  const generation = JSON.parse(metadata.getContentText()).generation;
  const content = marketRuntimeFetch_(`${url}?alt=media&generation=${generation}`);
  if (content.getResponseCode() !== 200) throw new Error(`No se pudo leer la versión de cartera (${content.getResponseCode()}).`);
  return {value: JSON.parse(content.getContentText()), generation};
}

function writeMarketRuntimeJson_(name, value, generation) {
  const url = `https://storage.googleapis.com/upload/storage/v1/b/${MARKET_RUNTIME_BUCKET}/o` +
    `?uploadType=media&name=${encodeURIComponent(name)}&ifGenerationMatch=${generation}`;
  const response = marketRuntimeFetch_(url, {
    method: 'post', contentType: 'application/json; charset=utf-8', payload: JSON.stringify(value),
  });
  if (response.getResponseCode() === 412) return false;
  if (response.getResponseCode() < 200 || response.getResponseCode() >= 300) {
    throw new Error(`No se pudo guardar la cartera (${response.getResponseCode()}). La orden sigue en cola.`);
  }
  return true;
}

function marketShotState_(layoutInput, portfolioInput, command, now) {
  const layout = JSON.parse(JSON.stringify(layoutInput));
  const portfolio = JSON.parse(JSON.stringify(portfolioInput));
  const history = portfolio.applied_tracking_commands || [];
  const action = command.action === 'portfolio_buy_shot' ? 'buy' :
    command.action === 'portfolio_sell_shot' ? 'sell' : null;
  if (!action) throw new Error('Operación de shots no válida.');
  const prior = history.find(item => item.command_id === command.id);
  if (prior) {
    if (prior.ticker !== command.ticker || prior.action !== action) throw new Error('Identidad de operación contradictoria.');
    return {layout, portfolio, result: prior.result};
  }
  let group = layout.groups.find(item => item.tickers.includes(command.ticker));
  const structureChanged = !group;
  if (!group) {
    group = layout.groups.find(item => item.id === command.group_id);
    if (action !== 'buy' || !group) throw new Error('Grupo requerido para el ticker nuevo.');
    group.tickers.push(command.ticker);
  }
  const positions = portfolio.positions || {};
  // The durable count is exact, including three or more shots. Ticker colors
  // distinguish only zero/one/two-or-more and cannot supply an exact delta.
  const current = Number(positions[command.ticker] || 0);
  if (!Number.isInteger(current) || current < 0) throw new Error('Número de shots no válido.');
  if (action === 'sell' && current === 0) throw new Error('No hay shots abiertos para vender.');
  const shots = current + (action === 'buy' ? 1 : -1);
  if (shots) positions[command.ticker] = shots;
  else delete positions[command.ticker];
  portfolio.positions = positions;
  portfolio.updated_at = now.slice(0, 10);
  const result = {ticker: command.ticker, shots, tracked: true, group_id: group.id, structure_changed: structureChanged};
  history.push({command_id: command.id, action, ticker: command.ticker,
    applied_at: now, publication_pending: true, source: 'google_sheets_immediate', result});
  portfolio.applied_tracking_commands = history.slice(-100);
  return {layout, portfolio, result};
}

function commitMarketShotImmediately_(command) {
  let structureChanged = false;
  for (let attempt = 0; attempt < 5; attempt += 1) {
    const layout = readMarketRuntimeJson_(MARKET_RUNTIME_LAYOUT);
    const portfolio = readMarketRuntimeJson_(MARKET_RUNTIME_PORTFOLIO);
    const state = marketShotState_(layout.value, portfolio.value, command, new Date().toISOString());
    if ((portfolio.value.applied_tracking_commands || []).some(item => item.command_id === command.id)) return state;
    structureChanged = structureChanged || state.result.structure_changed;
    state.result.structure_changed = structureChanged;
    if (JSON.stringify(state.layout) !== JSON.stringify(layout.value) &&
        !writeMarketRuntimeJson_(MARKET_RUNTIME_LAYOUT, state.layout, layout.generation)) continue;
    if (writeMarketRuntimeJson_(MARKET_RUNTIME_PORTFOLIO, state.portfolio, portfolio.generation)) return state;
  }
  throw new Error('La cartera cambió simultáneamente. La orden sigue guardada en cola.');
}

function marketGroupKey_(label) {
  return String(label).normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase().trim();
}

function paintMarketPortfolioImmediately_(layout, portfolio) {
  const sheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName(MARKET_TICKER_EXPORT.sheetName);
  let index = marketTickerIndex_();
  const positions = portfolio.positions;
  // A new symbol appears immediately; the existing background worker reconciles
  // the native table geometry and its analysis fields afterwards.
  layout.groups.forEach(group => group.tickers.forEach(ticker => {
    if (index[ticker]) return;
    const columns = findMarketTickerColumns_(sheet);
    columns.sort((a, b) => Object.values(index).filter(x => x.column === a.column).length -
      Object.values(index).filter(x => x.column === b.column).length);
    const column = columns[0];
    const count = Object.values(index).filter(x => x.column === column.column).length;
    const row = column.firstDataRow + count;
    if (row > sheet.getMaxRows()) sheet.insertRowsAfter(sheet.getMaxRows(), row - sheet.getMaxRows());
    if (count) sheet.getRange(row - 1, column.column - 1, 1, 14)
      .copyTo(sheet.getRange(row, column.column - 1, 1, 14), {formatOnly: true});
    sheet.getRange(row, column.column).setValue(ticker);
    index[ticker] = {ticker, row, column: column.column, shots: positions[ticker] || 0};
  }));
  const byTicker = {};
  const byLabel = {};
  layout.groups.forEach(group => {
    const counts = {positions: 0, shots: 0};
    group.tickers.forEach(ticker => {
      const shots = positions[ticker] || 0;
      counts.shots += shots;
      if (shots > 0) counts.positions += 1;
      byTicker[ticker] = counts;
    });
    byLabel[marketGroupKey_(`${group.sector} / ${group.label}`)] = counts;
  });
  const colors = {'#ffffff': [], '#00ffff': [], '#00b8d4': []};
  Object.values(index).forEach(record => {
    const shots = positions[record.ticker] || 0;
    colors[shots >= 2 ? '#00b8d4' : shots === 1 ? '#00ffff' : '#ffffff']
      .push(sheet.getRange(record.row, record.column).getA1Notation());
  });
  Object.keys(colors).forEach(color => {
    if (colors[color].length) sheet.getRangeList(colors[color]).setBackground(color);
  });
  findMarketTickerColumns_(sheet).forEach(column => {
    const records = Object.values(index).filter(x => x.column === column.column).sort((a, b) => a.row - b.row);
    if (records.length) sheet.getRange(column.firstDataRow, column.column - 1, records.length, 1)
      .setValues(records.map(record => [byTicker[record.ticker] ? byTicker[record.ticker].shots : 0]));
  });
  // The summary has its own live sorting; match labels instead of fixed rows.
  const values = sheet.getDataRange().getDisplayValues();
  const headerRow = values.findIndex(row => row.includes('Pos.') && row.includes('Shots'));
  if (headerRow < 0) throw new Error('No se encuentra el resumen de cartera.');
  const positionColumn = values[headerRow].indexOf('Pos.') + 1;
  const counts = values.slice(headerRow + 1, headerRow + 1 + layout.groups.length).map(row => {
    const group = byLabel[marketGroupKey_(row[0])];
    if (!group) throw new Error(`Grupo no reconocido en el resumen: ${row[0]}`);
    return [group.positions, group.shots];
  });
  sheet.getRange(headerRow + 2, positionColumn, counts.length, 2).setValues(counts);
}
