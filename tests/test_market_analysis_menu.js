const assert = require('assert');
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const columns = {
  2: {
    values: [['AMD'], ['TSM'], [''], ['SOXX'], [''], [''], ['']],
    backgrounds: [['#00FFFF'], ['#ffffff'], ['#ffffff'], ['#ffffff'], ['#ffffff'], ['#ffffff'], ['#ffffff']],
  },
  17: {
    values: [['RKLB'], [''], ['UFO'], [''], [''], [''], ['']],
    backgrounds: [['#00B8D4'], ['#ffffff'], ['#ffffff'], ['#ffffff'], ['#ffffff'], ['#ffffff'], ['#ffffff']],
  },
};
const menus = [];
let uploaded = null;
const sheet = {
  getLastRow() {
    return 10;
  },
  getLastColumn() {
    return 17;
  },
  getRange(firstRow, column, rowCount, columnCount) {
    if (firstRow === 1 && column === 1) {
      const grid = Array.from({ length: rowCount }, () =>
        Array.from({ length: columnCount }, () => '')
      );
      grid[2][1] = 'Ticker';
      grid[2][16] = 'Ticker';
      return { getDisplayValues() { return grid; } };
    }
    if (firstRow === 1 && rowCount === undefined) {
      return {
        getA1Notation() {
          return column === 2 ? 'B1' : 'Q1';
        },
      };
    }
    assert.strictEqual(firstRow, 4);
    assert.strictEqual(rowCount, 7);
    assert.strictEqual(columnCount, 1);
    return {
      getValues() {
        return columns[column].values;
      },
      getBackgrounds() {
        return columns[column].backgrounds;
      },
    };
  },
};
const spreadsheet = {
  getSheetByName(name) {
    // The new workbook can retain a hidden legacy sheet. Mercado must win.
    return name === 'Mercado' || name === 'Bolsa_2026' ? sheet : null;
  },
  toast() {},
};
const context = {
  console,
  refreshTradingDrawdownNotesNow() {},
  refreshCoreDrawdownColorsNow() {},
  SpreadsheetApp: {
    getActiveSpreadsheet() {
      return spreadsheet;
    },
    getUi() {
      return {
        createMenu(name) {
          const menu = {
            name,
            items: [],
            addItem(label, handler) {
              this.items.push({ label, handler });
              return this;
            },
            addSeparator() {
              return this;
            },
            addToUi() {
              menus.push(this);
            },
          };
          return menu;
        },
      };
    },
  },
  ScriptApp: {
    getOAuthToken() {
      return 'test-token';
    },
  },
  UrlFetchApp: {
    fetch(url, options) {
      uploaded = { url, options };
      return {
        getResponseCode() {
          return 200;
        },
        getContentText() {
          return '{}';
        },
      };
    },
  },
};

vm.createContext(context);
const source = fs.readFileSync(
  path.join(__dirname, '..', 'apps_script', 'export_tickers_to_gcs.gs'),
  'utf8'
);
vm.runInContext(source, context);

const portfolioMenuSource = fs.readFileSync(
  path.join(__dirname, '..', 'apps_script', 'market_portfolio_menu.gs'),
  'utf8'
);
vm.runInContext(portfolioMenuSource, context);

const completionSource = fs.readFileSync(
  path.join(__dirname, '..', 'apps_script', 'analysis_completion_sync.gs'),
  'utf8'
);
vm.runInContext(completionSource, context);

const payload = context.exportMarketTickersToGcs_(false);
assert.deepStrictEqual(Array.from(payload.tickers), ['AMD', 'TSM', 'RKLB']);
assert.strictEqual(payload.count, 3);
assert.strictEqual(payload.ticker_records[0].owned, true);
assert.strictEqual(payload.ticker_records[1].owned, false);
assert.strictEqual(payload.ticker_records[2].owned, true);
assert.match(uploaded.url, /config\/tickers_market\.json/);
const marketIndex = context.marketTickerIndex_();
assert.strictEqual(marketIndex.AMD.shots, 1);
assert.strictEqual(marketIndex.TSM.shots, 0);
assert.strictEqual(marketIndex.RKLB.shots, 2);
assert.deepStrictEqual(
  Object.assign({}, context.marketPortfolioSnapshot_(marketIndex)),
  { AMD: 1, TSM: 0, RKLB: 2 }
);
assert.strictEqual(
  context.shouldApplyAnalysisResult_({
    action: 'analyze_market',
    status: 'failed',
    batch_success: 2,
  }),
  true
);
context.onOpen();
const analysisMenu = menus.find((menu) => menu.name === 'Análisis IA');
assert.ok(analysisMenu);
assert.ok(
  analysisMenu.items.some(
    (item) =>
      item.label === 'Analizar mercado en local' &&
      item.handler === 'enqueueMarketAnalysis'
  )
);
assert.ok(
  !analysisMenu.items.some((item) => item.label === 'Analizar trading en local')
);
for (const label of [
  'He comprado 1 shot...',
  'He vendido 1 shot...',
  'Quitar ticker del seguimiento...',
]) {
  assert.ok(analysisMenu.items.some((item) => item.label === label));
}
columns[17].values[0][0] = 'AMD';
assert.throws(
  () => context.exportMarketTickersToGcs_(false),
  /Ticker duplicado en Mercado: AMD/
);

console.log('Mercado IA menu tests passed.');
