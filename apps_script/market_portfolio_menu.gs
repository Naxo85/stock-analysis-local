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
  enqueueAnalysisCommand_({
    action: 'portfolio_buy_shot',
    ticker,
    group_id: groupId,
    observed_shots: record ? record.shots : 0,
    portfolio_snapshot: marketPortfolioSnapshot_(marketIndex),
    portfolio_snapshot_at: marketIndex.snapshotTakenAt,
    track_analysis_status: false,
  });
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
  enqueueAnalysisCommand_({
    action: 'portfolio_sell_shot',
    ticker,
    observed_shots: record.shots,
    portfolio_snapshot: marketPortfolioSnapshot_(marketIndex),
    portfolio_snapshot_at: marketIndex.snapshotTakenAt,
    track_analysis_status: false,
  });
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
        shots: background === '#00b8d4' ? 2 : background === '#00ffff' ? 1 : 0,
      };
    }
  });
  return result;
}
