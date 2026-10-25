const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync('apps_script/market_portfolio_menu.gs', 'utf8');
const context = {console};
vm.createContext(context);
vm.runInContext(source, context);
const layout = {groups: [{id: 'chips', sector:'Semis', label:'Chips', tickers:['AMD','TSM']}]};
const base = {positions:{}, applied_tracking_commands:[]};
const buy = id => ({id, action:'portfolio_buy_shot', ticker:'AMD'});
let state = context.marketShotState_(layout, base, buy('one'), '2026-10-21T10:00:00Z');
assert.equal(state.portfolio.positions.AMD, 1);
state = context.marketShotState_(state.layout, state.portfolio, buy('two'), '2026-10-21T10:01:00Z');
state = context.marketShotState_(state.layout, state.portfolio, buy('three'), '2026-10-21T10:02:00Z');
assert.equal(state.portfolio.positions.AMD, 3);
state = context.marketShotState_(state.layout, state.portfolio, buy('three'), '2026-10-21T10:03:00Z');
assert.equal(state.portfolio.positions.AMD, 3, 'replayed ID must not increment');
state = context.marketShotState_(state.layout, state.portfolio,
  {id:'sell',action:'portfolio_sell_shot',ticker:'AMD'}, '2026-10-21T10:04:00Z');
assert.equal(state.portfolio.positions.AMD, 2, 'selling from 3 uses exact durable count');
assert.equal(base.positions.AMD, undefined, 'input immutable');
assert.throws(() => context.marketShotState_(layout, base,
  {id:'empty',action:'portfolio_sell_shot',ticker:'AMD'}, '2026-10-21T10:00:00Z'), /No hay shots/);
const added = context.marketShotState_(layout, base,
  {id:'new',action:'portfolio_buy_shot',ticker:'NEW',group_id:'chips'}, '2026-10-21T10:00:00Z');
assert(added.layout.groups[0].tickers.includes('NEW'));
assert.equal(added.result.structure_changed, true);
assert.throws(() => context.marketShotState_(state.layout, state.portfolio,
  {id:'one',action:'portfolio_sell_shot',ticker:'AMD'}, '2026-10-21T10:00:00Z'), /Identidad/);

// Exercise the menu path without real trades or cloud writes. Persist before
// painting, flush before returning, and release its lock even on failure.
let calls = [];
Object.assign(context, {
  LockService: {getScriptLock:()=>({waitLock:()=>calls.push('lock'),releaseLock:()=>calls.push('unlock')})},
  SpreadsheetApp: {flush:()=>calls.push('flush'),getActiveSpreadsheet:()=>({toast:()=>calls.push('toast')})},
  marketTickerIndex_:()=>({AMD:{shots:0}, snapshotTakenAt:'2026-10-21T10:00:00Z'}),
  enqueueAnalysisCommand_:values=>{calls.push('enqueue');assert.equal(values.portfolio_snapshot.AMD,0);return buy('menu');},
  commitMarketShotImmediately_:command=>{calls.push('commit');return {layout,portfolio:{positions:{AMD:1}}};},
  paintMarketPortfolioImmediately_:()=>calls.push('paint'),
});
context.applyMarketShotFromMenu_('portfolio_buy_shot','AMD',null);
assert.deepEqual(calls, ['lock','enqueue','commit','paint','flush','toast','unlock']);
calls=[];
context.commitMarketShotImmediately_=()=>{throw Error('offline');};
assert.throws(()=>context.applyMarketShotFromMenu_('portfolio_buy_shot','AMD',null), /offline/);
assert.deepEqual(calls,['lock','enqueue','unlock']);

// Runtime compare-and-set never overwrites a newer generation.
const casContext={console, Date, ScriptApp:{getOAuthToken:()=> 'test'}, UrlFetchApp:{fetch:(url, options)=>({getResponseCode:()=>412})}};
vm.createContext(casContext);vm.runInContext(source,casContext);
assert.equal(casContext.writeMarketRuntimeJson_('runtime/config/portfolio.json',{},'7'),false);

// Paint exact counts against the live ticker/summary order, including a third
// shot whose color is the same as two shots. No market data cells are touched.
const painted=[];
const grid=Array.from({length:16},()=>Array(38).fill(''));
grid[12][6]='Pos.';grid[12][7]='Shots';
grid[13][0]='Industrial / Espacio';grid[14][0]='Semis / Chips';
const mockSheet={
  getRange:(row,column,height,width)=>({
    getA1Notation:()=>`R${row}C${column}`,
    setValues:values=>painted.push({row,column,values}),
  }),
  getRangeList:cells=>({setBackground:color=>painted.push({cells,color})}),
  getDataRange:()=>({getDisplayValues:()=>grid}),
};
context.marketTickerIndex_=()=>({AMD:{ticker:'AMD',row:4,column:11},RKLB:{ticker:'RKLB',row:4,column:26}});
context.findMarketTickerColumns_=()=>[{firstDataRow:4,column:11},{firstDataRow:4,column:26}];
context.SpreadsheetApp.getActiveSpreadsheet=()=>({getSheetByName:()=>mockSheet});
context.MARKET_TICKER_EXPORT={sheetName:'Mercado'};
context.paintMarketPortfolioImmediately_=undefined;
vm.runInContext(source.slice(source.indexOf('function paintMarketPortfolioImmediately_')),context);
context.paintMarketPortfolioImmediately_({groups:[
  {id:'chips',sector:'Semis',label:'Chips',tickers:['AMD']},
  {id:'space',sector:'Industrial',label:'Espacio',tickers:['RKLB']},
]},{positions:{AMD:3,RKLB:1}});
assert(painted.some(x=>x.color==='#00b8d4' && x.cells.includes('R4C11')));
assert(painted.some(x=>x.color==='#00ffff' && x.cells.includes('R4C26')));
assert.deepEqual(JSON.parse(JSON.stringify(painted.find(x=>x.row===14 && x.column===7).values)),[[1,1],[1,3]]);
assert.deepEqual(JSON.parse(JSON.stringify(painted.find(x=>x.column===10).values)),[[3]]);
console.log('Immediate shots: exact counts, idempotency, empty sale, new ticker, menu ordering, failure and CAS passed.');
