/* =========================================================
   recalcYPRICE (con YPRICE directo + logs por fases)
   ========================================================= */
function recalcYPRICE2() {
  const tStart = _ms();
  console.log(`[recalcYPRICE] START ts=${new Date().toISOString()}`);

  /* ----------- AJUSTES BÁSICOS ------------ */
  const SHEET_NAME = 'Bolsa_2026';
  const FIRST      = 2;
  const LAST_CAP = 200;
  const CF_URL     = 'https://support-resistance-values-714254943648.europe-southwest1.run.app/';
  /* ---------------------------------------- */

  // 👇 tamaño de bloque para Cloud Run
  const BATCH_SIZE = 12;
  const BATCH_SLEEP_MS = 2000;

  const C = {
    TKR: 4, ATR: 5, PRICE: 6, PCT: 7,
    PUT: 8, CALL: 9, EMA: 10, HVN: 11, AVW: 12,
    RSI: 13, PCR: 14, ZG: 15, RVL: 16, SLP: 17, 
    MOM: 29 // AC
  };

  let t = _ms();

  const sh   = SpreadsheetApp.getActive().getSheetByName(SHEET_NAME);
  const qqqCloses = _qqqLast5ClosesForMomentum_();
  const strengthHistory = _strengthTrendLoad_('trading');
  const strengthToday = _strengthTrendToday_();
  const strengthUpdates = {};
  const COL_52H = _colByHeader(sh, '%63high') || 22; // fallback a V por si acaso
  const lastByTickers = sh.getRange(FIRST, C.TKR, LAST_CAP, 1)
    .getValues()
    .flat()
    .reduce((last, v, i) => (String(v||'').trim() ? (FIRST + i) : last), FIRST - 1);

  if (lastByTickers < FIRST) {
    console.log('[recalcYPRICE] no hay tickers, salgo');
    return;
  }

  const LAST = lastByTickers;
  const rows = LAST - FIRST + 1;

  t = _logPhase('init_sheet', t, `rows=${rows} FIRST=${FIRST} LAST=${LAST}`);

  /* 1) Precios con YPRICE DIRECTO (sin fórmulas) ----------------------- */
  const tRead = _ms();
  const tickers = sh.getRange(FIRST, C.TKR, rows, 1).getValues().flat();
  const priceR  = sh.getRange(FIRST, C.PRICE, rows, 1);
  const oldPrices = priceR.getValues().flat();

  t = _logPhase('read_tickers_ranges', tRead, `tickers_nonempty=${tickers.filter(x=>String(x||'').trim()!=='').length}`);

  const tClear = _ms();
  priceR.clearContent();
  t = _logPhase('clear_price_range', tClear);

  const tYp = _ms();
  const pricesFlat = [];     // [Number|''] por índice
  const prices2D   = [];     // [[Number|'']] para setValues

  let okP = 0, badP = 0;

  for (let i = 0; i < tickers.length; i++) {
    const tkr = String(tickers[i] || '').trim().toUpperCase();
    if (!tkr) {
      pricesFlat.push('');
      prices2D.push(['']);
      continue;
    }

    let p = null;
    try {
      p = YPRICE(tkr, true);
    } catch (e) {
      console.log(`[recalcYPRICE][YPRICE] ${tkr} ERROR: ${e && e.stack ? e.stack : e}`);
      p = null;
    }

    if (p != null && isFinite(p)) {
      const n = Math.round(Number(p) * 100) / 100; 
      pricesFlat.push(n);
      prices2D.push([n]);
      okP++;
    } else {
      pricesFlat.push('');
      prices2D.push(['']);
      badP++;
    }
  }

  // escribe precios en la hoja
  priceR.setValues(prices2D);
  SpreadsheetApp.flush();

  t = _logPhase('YPRICE_direct+write', tYp, `ok=${okP} bad=${badP}`);

  const writtenPrices = priceR.getValues().flat();
  const samplePrices = tickers
    .map((tkr, i) => ({
      row: FIRST + i,
      tkr: String(tkr || '').trim().toUpperCase(),
      old: oldPrices[i],
      calc: pricesFlat[i],
      sheet: writtenPrices[i]
    }))
    .filter(x => x.tkr)
    .slice(0, 5);
  console.log('[recalcYPRICE][PRICE_SAMPLE] ' + JSON.stringify(samplePrices));

  const blanksAfter = pricesFlat
    .map((v, i) => ({ row: FIRST + i, tkr: tickers[i], val: v }))
    .filter(x => x.val === '' || !isFinite(x.val));
  if (blanksAfter.length) {
    console.log('[recalcYPRICE] precios inválidos tras YPRICE directo:', JSON.stringify(blanksAfter));
  }

  /* 2) Cloud Run por bloques ------------------------------------------ */
  const tReq = _ms();
  const requests = tickers.map((tkr, idx) => ({
    url: CF_URL,
    method: 'post',
    contentType: 'application/json',
    payload: JSON.stringify({ symbol: String(tkr||'').trim().toUpperCase(), price: +pricesFlat[idx] || undefined }),
    muteHttpExceptions: true
  }));
  t = _logPhase('build_requests', tReq);

  const chunk = (arr, size) => {
    const out = [];
    for (let i = 0; i < arr.length; i += size) out.push(arr.slice(i, i + size));
    return out;
  };

  const requestChunks = chunk(requests, BATCH_SIZE);
  console.log(`[recalcYPRICE] requestChunks=${requestChunks.length} BATCH_SIZE=${BATCH_SIZE}`);

  const responses = new Array(requests.length);
  let offset = 0;

  const tFetchAll = _ms();

  /* 2.1) Batches principales */
  requestChunks.forEach((reqs, bi) => {
    const tb = _ms();
    const resps = UrlFetchApp.fetchAll(reqs);
    const dtb = _ms() - tb;

    const codes = resps.map(r => (
      typeof r.getResponseCode === 'function' ? r.getResponseCode() : ''
    ));

    console.log(
      `[recalcYPRICE][FETCH] batch ${bi + 1}/${requestChunks.length} ` +
      `size=${reqs.length} dt=${_msTo(dtb)} codes=${JSON.stringify(codes)}`
    );

    resps.forEach((r, j) => responses[offset + j] = r);
    offset += reqs.length;

    if (BATCH_SLEEP_MS && bi < requestChunks.length - 1) {
      Utilities.sleep(BATCH_SLEEP_MS);
    }
  });

  /* 2.2) Reintentos SOLO para 429 */
  const RETRY_429_SLEEP_MS = 2000;
  const MAX_429_RETRY_WAVES = 5;

  for (let wave = 1; wave <= MAX_429_RETRY_WAVES; wave++) {
    const retryItems = [];

    responses.forEach((resp, idx) => {
      const code = _responseCode(resp);

      if (code === 429) {
        retryItems.push({
          idx,
          req: requests[idx],
          tkr: String(tickers[idx] || '').trim().toUpperCase()
        });
      }
    });

    if (!retryItems.length) {
      console.log(`[recalcYPRICE][RETRY_429] no quedan 429 tras wave=${wave - 1}`);
      break;
    }

    console.log(
      `[recalcYPRICE][RETRY_429] wave=${wave}/${MAX_429_RETRY_WAVES} ` +
      `count=${retryItems.length} tickers=${retryItems.map(x => x.tkr).join(',')} ` +
      `sleep=${RETRY_429_SLEEP_MS}ms`
    );

    Utilities.sleep(RETRY_429_SLEEP_MS);

    const tb = _ms();
    const retryResps = UrlFetchApp.fetchAll(retryItems.map(x => x.req));
    const dtb = _ms() - tb;

    const retryCodes = retryResps.map(r => _responseCode(r));

    console.log(
      `[recalcYPRICE][RETRY_429] wave=${wave} dt=${_msTo(dtb)} ` +
      `codes=${JSON.stringify(retryCodes)}`
    );

    retryResps.forEach((r, j) => {
      responses[retryItems[j].idx] = r;
    });
  }

  const final429 = responses
    .map((resp, idx) => ({
      tkr: String(tickers[idx] || '').trim().toUpperCase(),
      code: _responseCode(resp)
    }))
    .filter(x => x.code === 429);

  if (final429.length) {
    console.log(
      `[recalcYPRICE][RETRY_429] quedan 429 finales: ` +
      JSON.stringify(final429)
    );
  }

  t = _logPhase('fetchAll_total', tFetchAll);

  /* 3) Procesa respuestas --------------------------------------------- */
  const tProcess = _ms();
  let ok = 0, jsonErr = 0, skip = 0;

  responses.forEach((resp, idx) => {
    const row   = FIRST + idx;
    const price = Number(pricesFlat[idx]);
    const tkr   = String(tickers[idx] || '').trim().toUpperCase();

    if (!tkr || !isFinite(price) || price <= 0) {
      skip++;
      sh.getRange(row, C.PCT).clearContent();       // %d
      sh.getRange(row, COL_52H).clearContent();     // %52high en V
      sh.getRange(row, C.ATR, 1, 1).clearContent();
      sh.getRange(row, C.PUT, 1, (C.SLP - C.PUT + 1)).clearContent();
      return;
    }

    let d;
    try {
      d = JSON.parse(resp.getContentText());
      ok++;
    } catch (e) {
      jsonErr++;
      const code = (typeof resp.getResponseCode === 'function') ? resp.getResponseCode() : '';
      console.log('[recalcYPRICE]', tkr, '→ JSON_ERROR', 'status=', code, 'resp=', resp.getContentText().slice(0, 120));
      sh.getRange(row, C.PCT).setValue('#ERROR');
      sh.getRange(row, COL_52H).clearContent();
      sh.getRange(row, C.PUT, 1, (C.SLP - C.PUT + 1)).clearContent();
      return;
    }

    const dayPctFrac = d.pct_change != null ? d.pct_change / 100 : '';
    const p6mFrac    = d.pct_from_6m_high != null ? d.pct_from_6m_high / 100 : '';

    const rsi   = +d.rsi14               || '';
    const ema20 = +d.ema20               || '';
    const slope = +d.ema20_slope         || '';
    const pcr   = +d.pcr_oi              || '';
    const hvn   = +d.hvn_poc             || '';
    const avwap = +d.anchored_vwap_swing || '';
    const zgam  = +d.zero_gamma          || '';
    const rvol  = +d.rel_volume          || '';

    const putR  = (d.put_wall  != null) ? Number(d.put_wall)  : null;
    const callR = (d.call_wall != null) ? Number(d.call_wall) : null;

    if (d.ATR10 && price) {
      const atrPct = d.ATR10 / price;   // ATR10 porcentual
      sh.getRange(row, C.ATR)
        .setNumberFormat('0.00%')
        .setValue(atrPct);
    } else {
      sh.getRange(row, C.ATR).clearContent();
    }

    if (dayPctFrac !== '') {
      sh.getRange(row, C.PCT).setNumberFormat('0.00%').setValue(dayPctFrac);
    } else {
      sh.getRange(row, C.PCT).clearContent();
    }

    if (p6mFrac !== '') {
      sh.getRange(row, COL_52H).setNumberFormat('0.00%').setValue(p6mFrac); // V
    } else {
      sh.getRange(row, COL_52H).clearContent();
    }

    sh.getRange(row, C.PUT, 1, 10).setValues([[
      putR, callR, ema20, hvn, avwap, rsi, pcr, zgam, rvol, slope
    ]]);

    const fuerza = _num(sh.getRange(row, 18).getValue()); // R
    const momentumBase = _momentumScore_(fuerza, d.last_5_closes, qqqCloses, slope, rvol, rsi);
    const strengthTrend = _strengthTrendForTicker_(
      strengthHistory,
      tkr,
      fuerza,
      strengthToday
    );
    const momentum = _momentumApplyContextAdjustments_(momentumBase, strengthTrend, rsi);


    if (momentum !== '') {
      sh.getRange(row, C.MOM)
        .setNumberFormat('@')
        .setValue(_momentumLabel_(momentum));
    } else {
      sh.getRange(row, C.MOM).clearContent();
    }

    if (isFinite(fuerza)) {
      strengthUpdates[tkr] = fuerza;
    }



  });

  _strengthTrendSave_('trading', strengthHistory, strengthToday, strengthUpdates);

  t = _logPhase('process_write_sheet', tProcess, `ok=${ok} jsonErr=${jsonErr} skip=${skip}`);
  SpreadsheetApp.flush();

  /* 4) Diagnóstico ----------------------------------------------------- */
  const DO_DIAG = false;

  if (DO_DIAG) {
    const tDiag = _ms();
    const filled = sh.getRange(FIRST, C.PRICE, rows, 1)
      .getValues()
      .filter(r => r[0] !== '' && !isNaN(r[0]))
      .length;

    console.log('[recalcYPRICE] rows_with_price:', filled);
    _logPhase('diagnostic', tDiag, `filled=${filled}/${rows}`);
  }

  console.log(`[recalcYPRICE] END total=${_msTo(_ms()-tStart)}`);
}

/* =========================================================
   Helpers de logging / timing
   ========================================================= */
function _ms() { return Date.now(); }
function _msTo(ms){ return (ms/1000).toFixed(2) + 's'; }
function _logPhase(name, t0, extra){
  const dt = Date.now() - t0;
  console.log(`[recalcYPRICE][PHASE] ${name} dt=${_msTo(dt)}${extra ? ' ' + extra : ''}`);
  return Date.now();
}

/* =========================================================
   YPRICE (tu función)
   ========================================================= */
function YPRICE(sym, forceExt){
  sym = String(sym).trim().toUpperCase();

  /* ---------- caché 60 s ---------- */
  const cache = CacheService.getScriptCache();
  const key   = `YP_${sym}_${forceExt}`;
  const hit   = cache.get(key);
  if (hit) return Number(hit);

  /* ---------- descarga intradía ---------- */
  const chart = prePost => {
    const url = `https://query1.finance.yahoo.com/v8/finance/chart/${sym}` +
                `?range=1d&interval=1m&includePrePost=${prePost}`;
    return JSON.parse(UrlFetchApp.fetch(url).getContentText())
           ?.chart?.result?.[0];
  };

  let r = chart(true);                          // 1) con pre/after-hours
  if (!r?.timestamp?.length) r = chart(false);  // 2) sin extended

  let price = null;

  /* ---------- protección ---------- */
  const quote = r?.indicators?.quote?.[0];
  if (quote?.close?.length && r?.timestamp?.length){
    const close      = quote.close;
    const timestamps = r.timestamp;

    for (let i = close.length - 1; i >= 0; i--) {
      if (close[i] == null) continue;
      const hET = Utilities.formatDate(new Date(timestamps[i] * 1000), 'GMT-4', 'HHmm');
      const isExt = (hET < '0930' || hET >= '1600');
      price = forceExt ? (isExt ? close[i] : null) : close[i];
      if (!price) price = close[i]; // fallback precio regular
      break;
    }
  }

  /* ---------- Fallback quoteSummary ---------- */
  if (price == null){
    const url = `https://query1.finance.yahoo.com/v10/finance/quoteSummary/${sym}?modules=price`;
    price = JSON.parse(UrlFetchApp.fetch(url).getContentText())
            ?.quoteSummary?.result?.[0]?.price?.regularMarketPrice?.raw
            || null;
  }

  /* ---------- Último precio temporal por ticker ---------- */
  const lastPriceKey = `LP_${sym}`;

  if (price == null){
    const prev = cache.get(lastPriceKey);
    if (prev != null) return Number(prev);
    return null;
  }

  /* ---------- guarda caché temporal ---------- */
  cache.put(key, String(price), 60);              // precio fresco: 60 s
  cache.put(lastPriceKey, String(price), 21600);  // último precio temporal: 6 h

  return Number(price);
}

function _isPropertyQuotaError(e) {
  const msg = String((e && e.message) || e || '').toLowerCase();
  return msg.indexOf('property storage quota') >= 0;
}

function _colByHeader(sh, header, headerRow = 1) {
  const headers = sh.getRange(headerRow, 1, 1, sh.getLastColumn()).getDisplayValues()[0];
  const idx = headers.findIndex(h => String(h || '').trim() === header);
  return idx >= 0 ? idx + 1 : null;
}

function _responseCode(resp) {
  try {
    return resp && typeof resp.getResponseCode === 'function'
      ? resp.getResponseCode()
      : null;
  } catch (e) {
    return null;
  }
}


function runBolsaScheduler5m() {
  const lock = LockService.getScriptLock();

  // Evita que se solapen dos ejecuciones si una tarda demasiado.
  if (!lock.tryLock(1000)) {
    console.log('[BolsaScheduler] SKIP: ejecución anterior todavía activa');
    return;
  }

  try {
    const gate = _bolsaSchedulerGate_();

    if (!gate.run) {
      console.log(
        `[BolsaScheduler] SKIP reason=${gate.reason} ` +
        `session=${gate.session} nowET=${gate.nowEt} ` +
        `minsSinceLast=${gate.minsSinceLast}`
      );
      return;
    }

    console.log(
      `[BolsaScheduler] RUN reason=${gate.reason} ` +
      `session=${gate.session} nowET=${gate.nowEt}`
    );

    // Marca el inicio, no el final
    _markBolsaSchedulerRun_(gate);

    recalcYPRICE2();

  } finally {
    lock.releaseLock();
  }
}


function _bolsaSchedulerGate_() {
  const session = _getUsMarketSessionNow_();

  if (!session.open) {
    return {
      run: false,
      reason: session.reason,
      session: session.session,
      nowEt: session.nowEt,
      minsSinceLast: null
    };
  }

  const props = PropertiesService.getScriptProperties();

  const lastRunMs = Number(props.getProperty('BOLSA_LAST_RUN_MS') || 0);
  const lastSession = props.getProperty('BOLSA_LAST_SESSION') || '';

  const nowMs = Date.now();

  // Market regular cada 5 min.
  // Premarket y postmarket cada 10 min.
  const intervalMs = session.session === 'market'
    ? 5 * 60 * 1000
    : 10 * 60 * 1000;

  const elapsedMs = lastRunMs ? nowMs - lastRunMs : Number.POSITIVE_INFINITY;
  const minsSinceLast = lastRunMs ? Math.round(elapsedMs / 60000 * 10) / 10 : null;

  // Si cambia de sesión, ejecuta directamente:
  // premarket -> market, market -> postmarket, o día nuevo.
  if (lastSession !== session.session) {
    return {
      run: true,
      reason: `session_changed_${lastSession || 'none'}_to_${session.session}`,
      session: session.session,
      nowEt: session.nowEt,
      minsSinceLast
    };
  }

  const MIN_INTERVAL_RATIO = 0.80; // 80% del intervalo objetivo

  if (elapsedMs >= intervalMs * MIN_INTERVAL_RATIO) {
    return {
      run: true,
      reason: `interval_ok_${session.session}`,
      session: session.session,
      nowEt: session.nowEt,
      minsSinceLast
    };
  }

  return {
    run: false,
    reason: `too_soon_${session.session}`,
    session: session.session,
    nowEt: session.nowEt,
    minsSinceLast
  };
}


function _markBolsaSchedulerRun_(gate) {
  const props = PropertiesService.getScriptProperties();

  props.setProperties({
    BOLSA_LAST_RUN_MS: String(Date.now()),
    BOLSA_LAST_SESSION: gate.session,
    BOLSA_LAST_RUN_ET: gate.nowEt
  });
}


function _getUsMarketSessionNow_() {
  const tz = 'America/New_York';
  const now = new Date();

  const dateEt = Utilities.formatDate(now, tz, 'yyyy-MM-dd');
  const timeEt = Utilities.formatDate(now, tz, 'HH:mm');
  const nowEt = Utilities.formatDate(now, tz, 'yyyy-MM-dd HH:mm:ss');

  const parts = dateEt.split('-').map(Number);
  const y = parts[0];
  const m = parts[1];
  const d = parts[2];

  // Día de la semana en fecha ET.
  // 0 = domingo, 1 = lunes, ..., 6 = sábado
  const dow = new Date(Date.UTC(y, m - 1, d)).getUTCDay();

  if (dow === 0 || dow === 6) {
    return {
      open: false,
      session: 'closed',
      reason: 'weekend',
      nowEt
    };
  }

  const hm = timeEt.split(':').map(Number);
  const mins = hm[0] * 60 + hm[1];

  const PRE_START = 4 * 60;        // 04:00
  const MKT_START = 9 * 60 + 30;   // 09:30
  const MKT_END   = 16 * 60;       // 16:00
  const POST_END  = 20 * 60;       // 20:00

  if (mins < PRE_START) {
    return {
      open: false,
      session: 'closed',
      reason: 'before_premarket',
      nowEt
    };
  }

  if (mins >= POST_END) {
    return {
      open: false,
      session: 'closed',
      reason: 'after_postmarket',
      nowEt
    };
  }

  if (mins < MKT_START) {
    return {
      open: true,
      session: 'premarket',
      reason: 'premarket',
      nowEt
    };
  }

  if (mins < MKT_END) {
    return {
      open: true,
      session: 'market',
      reason: 'market',
      nowEt
    };
  }

  return {
    open: true,
    session: 'postmarket',
    reason: 'postmarket',
    nowEt
  };
}

function _momentumScore_(fuerza, last5Closes, qqqCloses, slope, relVol, rsi) {
  const fuerzaScore = isFinite(fuerza) ? _clamp(fuerza, 0, 10) : 5;
  const relativeScore = _relativeQqqScore_(last5Closes, qqqCloses);
  const slopeScore = isFinite(slope) ? _scale(slope, -2, 2) : 5;
  const relVolScore = isFinite(relVol) ? _relVolumeScore_(relVol) : 5;
  const rsiScore = isFinite(rsi) ? _rsiQualityScore_(rsi) : 5;

  const score =
    fuerzaScore * 0.40 +
    relativeScore * 0.25 +
    slopeScore * 0.15 +
    relVolScore * 0.10 +
    rsiScore * 0.10;

  return Math.round(_clamp(score, 0, 10) * 10) / 10;
}

function _relativeQqqScore_(last5Closes, qqqCloses) {
  if (!last5Closes || !qqqCloses) return 5;

  const ticker = last5Closes
    .map(x => Number(x.close))
    .filter(x => isFinite(x));

  const qqq = qqqCloses
    .map(x => Number(x))
    .filter(x => isFinite(x));

  if (ticker.length < 2 || qqq.length < 2) return 5;

  const tickerRet = ticker[ticker.length - 1] / ticker[0] - 1;
  const qqqRet = qqq[qqq.length - 1] / qqq[0] - 1;
  const relativePp = (tickerRet - qqqRet) * 100;

  return _scale(relativePp, -8, 8);
}

function _qqqLast5ClosesForMomentum_() {
  try {
    if (typeof MKT_QQQ_LAST_5_CLOSES !== 'function') return [];

    const rows = MKT_QQQ_LAST_5_CLOSES();
    if (!rows || rows.length <= 1) return [];

    return rows
      .slice(1)
      .map(row => Number(row[1]))
      .filter(x => isFinite(x));
  } catch (e) {
    console.log('[recalcYPRICE][MOM] QQQ last5 error:', e);
    return [];
  }
}

function _relVolumeScore_(relVol) {
  if (relVol <= 0.5) return 4;
  if (relVol <= 0.8) return _interp(relVol, 0.5, 0.8, 4, 5);
  if (relVol <= 1.0) return _interp(relVol, 0.8, 1.0, 5, 6);
  if (relVol <= 1.5) return _interp(relVol, 1.0, 1.5, 6, 8.5);
  return 10;
}

function _rsiQualityScore_(rsi) {
  if (rsi <= 30) return 2;
  if (rsi <= 35) return _interp(rsi, 30, 35, 2, 4);
  if (rsi <= 40) return _interp(rsi, 35, 40, 4, 6);
  if (rsi <= 50) return _interp(rsi, 40, 50, 6, 9);
  if (rsi <= 65) return _interp(rsi, 50, 65, 9, 10);
  if (rsi <= 72) return _interp(rsi, 65, 72, 10, 8);
  if (rsi <= 78) return _interp(rsi, 72, 78, 8, 5);
  if (rsi <= 85) return _interp(rsi, 78, 85, 5, 2);
  return 1;
}

function _scale(value, minValue, maxValue) {
  return _clamp(((Number(value) - minValue) / (maxValue - minValue)) * 10, 0, 10);
}

function _interp(value, x1, x2, y1, y2) {
  if (x1 === x2) return y1;
  return y1 + ((Number(value) - x1) / (x2 - x1)) * (y2 - y1);
}

function _clamp(value, minValue, maxValue) {
  return Math.max(minValue, Math.min(maxValue, Number(value)));
}

function _num(value) {
  if (value === null || value === undefined || value === '') return NaN;
  return Number(String(value).replace(',', '.'));
}

function _momentumLabel_(score) {
  const s = Number(score);

  let label = 'Neutro';
  if (s >= 8.5) label = 'Explosivo';
  else if (s >= 7.5) label = 'Fuerte';
  else if (s >= 6.5) label = 'Sano';
  else if (s >= 5.5) label = 'Neutro+';
  else if (s >= 4.5) label = 'Neutro';
  else if (s >= 3.5) label = 'Débil';
  else label = 'Muy débil';

  return s.toFixed(1).replace('.', ',') + ' ' + label;
}

function clearLegacyYpricePropertiesNow() {
  PropertiesService.getScriptProperties().deleteProperty('LP_DICT_V1');
  Logger.log('LP_DICT_V1 deleted');
}

function _momentumNumber_(value) {
  if (value === null || value === undefined || value === '') return NaN;

  const match = String(value).match(/([0-9]+(?:[.,][0-9]+)?)/);
  if (!match) return NaN;

  return Number(match[1].replace(',', '.'));
}

function _momentumApplyContextAdjustments_(score, strengthTrend, rsi) {
  const base = Number(score);

  if (!isFinite(base)) {
    return score;
  }

  const trendAdjustment = _momentumStrengthTrendAdjustment_(strengthTrend);
  const rsiAdjustment = _momentumRsiContextAdjustment_(rsi, strengthTrend);
  const totalAdjustment = _clamp(trendAdjustment + rsiAdjustment, -1.6, 1.6);

  return Math.round(_clamp(base + totalAdjustment, 0, 10) * 10) / 10;
}

function _momentumStrengthTrendAdjustment_(strengthTrend) {
  if (!strengthTrend || !isFinite(Number(strengthTrend.delta))) {
    return 0;
  }

  const delta = Number(strengthTrend.delta);

  if (Math.abs(delta) < 0.3) {
    return 0;
  }

  return _clamp(delta * 0.35, -1.2, 1.2);
}

function _momentumRsiContextAdjustment_(rsi, strengthTrend) {
  const r = Number(rsi);

  if (!isFinite(r) || !strengthTrend || !isFinite(Number(strengthTrend.delta))) {
    return 0;
  }

  const delta = Number(strengthTrend.delta);
  const strongUp = delta >= 1.5;
  const up = delta >= 0.7;
  const down = delta <= -0.7;
  const strongDown = delta <= -1.5;

  if (r < 30) {
    if (strongUp) return 0.5;
    if (up) return 0.2;
    if (strongDown) return -0.9;
    if (down) return -0.5;
    return -0.2;
  }

  if (r < 36) {
    if (strongUp) return 0.9;
    if (up) return 0.5;
    if (strongDown) return -0.8;
    if (down) return -0.4;
    return 0.0;
  }

  if (r < 42) {
    if (strongUp) return 0.7;
    if (up) return 0.4;
    if (strongDown) return -0.5;
    if (down) return -0.2;
    return 0.1;
  }

  if (r < 50) {
    if (strongUp) return 0.4;
    if (up) return 0.2;
    if (strongDown) return -0.3;
    if (down) return -0.1;
    return 0.0;
  }

  if (r < 65) {
    if (strongUp) return 0.3;
    if (up) return 0.2;
    if (strongDown) return -0.2;
    return 0.1;
  }

  if (r < 72) {
    if (strongDown) return -0.3;
    if (down) return -0.1;
    if (strongUp) return 0.0;
    if (up) return 0.1;
    return 0.0;
  }

  if (r < 78) {
    if (strongDown) return -0.4;
    if (down) return -0.2;
    if (strongUp) return 0.1;
    if (up) return 0.0;
    return -0.1;
  }

  if (r < 85) {
    if (strongDown) return -0.9;
    if (down) return -0.6;
    if (strongUp) return -0.2;
    if (up) return -0.3;
    return -0.5;
  }

  return -1.1;
}

function _strengthTrendToday_() {
  return Utilities.formatDate(
    new Date(),
    Session.getScriptTimeZone(),
    'yyyy-MM-dd'
  );
}

function _strengthTrendPropertyKey_(profileName) {
  return `F_STRENGTH_HISTORY_V1_${String(profileName || 'default').toUpperCase()}`;
}

function _strengthTrendLoad_(profileName) {
  const key = _strengthTrendPropertyKey_(profileName);
  const raw = PropertiesService.getScriptProperties().getProperty(key);

  if (!raw) {
    return { version: 1, tickers: {} };
  }

  try {
    const parsed = JSON.parse(raw);
    if (!parsed || typeof parsed !== 'object') {
      return { version: 1, tickers: {} };
    }

    if (!parsed.tickers || typeof parsed.tickers !== 'object') {
      parsed.tickers = {};
    }

    return parsed;
  } catch (e) {
    console.log('[strengthTrend] bad history json:', e);
    return { version: 1, tickers: {} };
  }
}

function _strengthTrendSave_(profileName, history, today, updates) {
  const tickers = history.tickers || {};
  const symbols = Object.keys(updates || {});

  if (!symbols.length) {
    return;
  }

  symbols.forEach((symbol) => {
    const value = Number(updates[symbol]);

    if (!isFinite(value)) {
      return;
    }

    const arr = Array.isArray(tickers[symbol]) ? tickers[symbol] : [];
    const existing = arr.find((item) => item && item.date === today);

    if (existing) {
      existing.value = Math.round(value * 10) / 10;
    } else {
      arr.push({
        date: today,
        value: Math.round(value * 10) / 10,
      });
    }

    arr.sort((a, b) => String(a.date).localeCompare(String(b.date)));
    tickers[symbol] = arr.slice(-10);
  });

  history.version = 1;
  history.tickers = tickers;

  PropertiesService.getScriptProperties().setProperty(
    _strengthTrendPropertyKey_(profileName),
    JSON.stringify(history)
  );
}

function _strengthTrendForTicker_(history, ticker, currentStrength, today) {
  const current = Number(currentStrength);

  if (!ticker || !isFinite(current)) {
    return null;
  }

  const arr = ((history && history.tickers && history.tickers[ticker]) || [])
    .filter((item) => item && item.date && item.date < today && isFinite(Number(item.value)))
    .sort((a, b) => String(a.date).localeCompare(String(b.date)));

  if (!arr.length) {
    return null;
  }

  const refIndex = Math.max(0, arr.length - 5);
  const ref = arr[refIndex];
  const reference = Number(ref.value);

  if (!isFinite(reference)) {
    return null;
  }

  return {
    delta: Math.round((current - reference) * 10) / 10,
    reference,
    referenceDate: ref.date,
  };
}
