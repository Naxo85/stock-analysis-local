/* =========================================================
   recalcYPRICE2_CORE
   Tabla CORE desde AG.
   Usa YPRICE_CORE() con diccionario separado: LP_DICT_CORE_V1
   No toca LP_DICT_V1 del trading principal.
   ========================================================= */

function recalcYPRICE2_CORE() {
  const tStart = _coreMs();
  console.log(`[recalcYPRICE_CORE] START ts=${new Date().toISOString()}`);

  /* ----------- AJUSTES BÁSICOS ------------ */
  const SHEET_NAME = 'Bolsa_2026';
  const FIRST      = 2;
  const LAST_CAP   = 200;
  const CF_URL     = 'https://support-resistance-values-714254943648.europe-southwest1.run.app/';
  /* ---------------------------------------- */

  const BATCH_SIZE = 18;
  const BATCH_SLEEP_MS = 5000;

  /*
    COLUMNAS CORE:
    AG = Ticker
    AH = ATR
    AI = Valor
    AJ = %d
    AK..AT = indicadores
  */
  const C = {
    TKR:   33, // AG
    ATR:   34, // AH
    PRICE: 35, // AI
    PCT:   36, // AJ

    PUT:  37, // AK
    CALL: 38, // AL
    EMA:  39, // AM
    HVN:  40, // AN
    AVW:  41, // AO
    RSI:  42, // AP
    PCR:  43, // AQ
    ZG:   44, // AR
    RVL:  45, // AS
    SLP:  46, // AT
    FUE:  47, // AU
    MOM:  58  // BF
  };

  let t = _coreMs();

  const sh = SpreadsheetApp.getActive().getSheetByName(SHEET_NAME);
  const qqqCloses = _qqqLast5ClosesForMomentum_();
  const strengthHistory = _strengthTrendLoad_('core');
  const strengthToday = _strengthTrendToday_();
  const strengthUpdates = {};
  if (!sh) {
    console.log(`[recalcYPRICE_CORE] no existe la hoja ${SHEET_NAME}`);
    return;
  }

  const COL_52H =
    _coreColByHeader(sh, '%63high_core') ||
    _coreColByHeader(sh, '%63high') ||
    51;

  const lastByTickers = sh.getRange(FIRST, C.TKR, LAST_CAP, 1)
    .getValues()
    .flat()
    .reduce((last, v, i) => (String(v || '').trim() ? (FIRST + i) : last), FIRST - 1);

  if (lastByTickers < FIRST) {
    console.log('[recalcYPRICE_CORE] no hay tickers, salgo');
    return;
  }

  const LAST = lastByTickers;
  const rows = LAST - FIRST + 1;

  t = _coreLogPhase('init_sheet', t, `rows=${rows} FIRST=${FIRST} LAST=${LAST}`);

  /* 1) Precios con YPRICE_CORE ----------------------- */
  const tRead = _coreMs();

  const tickers = sh.getRange(FIRST, C.TKR, rows, 1).getValues().flat();
  const priceR  = sh.getRange(FIRST, C.PRICE, rows, 1);

  t = _coreLogPhase(
    'read_tickers_ranges',
    tRead,
    `tickers_nonempty=${tickers.filter(x => String(x || '').trim() !== '').length}`
  );

  const tClear = _coreMs();
  priceR.clearContent();
  t = _coreLogPhase('clear_price_range', tClear);

  const tYp = _coreMs();

  const pricesFlat = [];
  const prices2D   = [];

  let okP = 0;
  let badP = 0;

  for (let i = 0; i < tickers.length; i++) {
    const tkr = String(tickers[i] || '').trim().toUpperCase();

    if (!tkr) {
      pricesFlat.push('');
      prices2D.push(['']);
      continue;
    }

    let p = null;

    try {
      p = YPRICE_CORE(tkr, true);
    } catch (e) {
      console.log(`[recalcYPRICE_CORE][YPRICE_CORE] ${tkr} ERROR: ${e && e.stack ? e.stack : e}`);
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

  priceR.setValues(prices2D);

  t = _coreLogPhase('YPRICE_CORE_direct+write', tYp, `ok=${okP} bad=${badP}`);

  const blanksAfter = pricesFlat
    .map((v, i) => ({ row: FIRST + i, tkr: tickers[i], val: v }))
    .filter(x => x.val === '' || !isFinite(x.val));

  if (blanksAfter.length) {
    console.log('[recalcYPRICE_CORE] precios inválidos tras YPRICE_CORE:', JSON.stringify(blanksAfter));
  }

  /* 2) Cloud Run por bloques ---------------------------- */
  const tReq = _coreMs();

  const requests = tickers.map((tkr, idx) => ({
    url: CF_URL,
    method: 'post',
    contentType: 'application/json',
    payload: JSON.stringify({
      symbol: String(tkr || '').trim().toUpperCase(),
      price: +pricesFlat[idx] || undefined
    }),
    muteHttpExceptions: true
  }));

  t = _coreLogPhase('build_requests', tReq);

  const chunk = (arr, size) => {
    const out = [];
    for (let i = 0; i < arr.length; i += size) {
      out.push(arr.slice(i, i + size));
    }
    return out;
  };

  const requestChunks = chunk(requests, BATCH_SIZE);
  console.log(`[recalcYPRICE_CORE] requestChunks=${requestChunks.length} BATCH_SIZE=${BATCH_SIZE}`);

  const responses = new Array(requests.length);
  let offset = 0;

  const tFetchAll = _coreMs();

  requestChunks.forEach((reqs, bi) => {
    const tb = _coreMs();
    const resps = UrlFetchApp.fetchAll(reqs);
    const dtb = _coreMs() - tb;

    const codes = resps.map(r => _coreResponseCode(r));

    console.log(
      `[recalcYPRICE_CORE][FETCH] batch ${bi + 1}/${requestChunks.length} ` +
      `size=${reqs.length} dt=${_coreMsTo(dtb)} codes=${JSON.stringify(codes)}`
    );

    resps.forEach((r, j) => {
      responses[offset + j] = r;
    });

    offset += reqs.length;

    if (BATCH_SLEEP_MS && bi < requestChunks.length - 1) {
      Utilities.sleep(BATCH_SLEEP_MS);
    }
  });

  /* Reintentos SOLO para 429 */
  const RETRY_429_SLEEP_MS = 2000;
  const MAX_429_RETRY_WAVES = 5;

  for (let wave = 1; wave <= MAX_429_RETRY_WAVES; wave++) {
    const retryItems = [];

    responses.forEach((resp, idx) => {
      const code = _coreResponseCode(resp);

      if (code === 429) {
        retryItems.push({
          idx,
          req: requests[idx],
          tkr: String(tickers[idx] || '').trim().toUpperCase()
        });
      }
    });

    if (!retryItems.length) {
      console.log(`[recalcYPRICE_CORE][RETRY_429] no quedan 429 tras wave=${wave - 1}`);
      break;
    }

    console.log(
      `[recalcYPRICE_CORE][RETRY_429] wave=${wave}/${MAX_429_RETRY_WAVES} ` +
      `count=${retryItems.length} tickers=${retryItems.map(x => x.tkr).join(',')} ` +
      `sleep=${RETRY_429_SLEEP_MS}ms`
    );

    Utilities.sleep(RETRY_429_SLEEP_MS);

    const tb = _coreMs();
    const retryResps = UrlFetchApp.fetchAll(retryItems.map(x => x.req));
    const dtb = _coreMs() - tb;

    const retryCodes = retryResps.map(r => _coreResponseCode(r));

    console.log(
      `[recalcYPRICE_CORE][RETRY_429] wave=${wave} dt=${_coreMsTo(dtb)} ` +
      `codes=${JSON.stringify(retryCodes)}`
    );

    retryResps.forEach((r, j) => {
      responses[retryItems[j].idx] = r;
    });
  }

  const final429 = responses
    .map((resp, idx) => ({
      tkr: String(tickers[idx] || '').trim().toUpperCase(),
      code: _coreResponseCode(resp)
    }))
    .filter(x => x.code === 429);

  if (final429.length) {
    console.log(`[recalcYPRICE_CORE][RETRY_429] quedan 429 finales: ${JSON.stringify(final429)}`);
  }

  t = _coreLogPhase('fetchAll_total', tFetchAll);

  /* 3) Procesa respuestas -------------------------------- */
  const tProcess = _coreMs();

  let ok = 0;
  let jsonErr = 0;
  let skip = 0;

  responses.forEach((resp, idx) => {
    const row   = FIRST + idx;
    const price = Number(pricesFlat[idx]);
    const tkr   = String(tickers[idx] || '').trim().toUpperCase();

    if (!tkr || !isFinite(price) || price <= 0) {
      skip++;
      sh.getRange(row, C.ATR).clearContent();
      sh.getRange(row, C.PCT).clearContent();
      sh.getRange(row, COL_52H).clearContent();
      sh.getRange(row, C.PUT, 1, C.SLP - C.PUT + 1).clearContent();
      return;
    }

    let d;

    try {
      d = JSON.parse(resp.getContentText());
      ok++;
    } catch (e) {
      jsonErr++;

      const code = _coreResponseCode(resp);
      const text = resp && typeof resp.getContentText === 'function'
        ? resp.getContentText()
        : '';

      console.log(
        '[recalcYPRICE_CORE]',
        tkr,
        '→ JSON_ERROR',
        'status=',
        code,
        'resp=',
        text.slice(0, 120)
      );

      sh.getRange(row, C.ATR).clearContent();
      sh.getRange(row, C.PCT).setValue('#ERROR');
      sh.getRange(row, COL_52H).clearContent();
      sh.getRange(row, C.PUT, 1, C.SLP - C.PUT + 1).clearContent();
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

    const putR  = d.put_wall  != null ? Number(d.put_wall)  : null;
    const callR = d.call_wall != null ? Number(d.call_wall) : null;

    if (d.ATR10 && price) {
      const atrPct = d.ATR10 / price;
      sh.getRange(row, C.ATR)
        .setNumberFormat('0.00%')
        .setValue(atrPct);
    } else {
      sh.getRange(row, C.ATR).clearContent();
    }

    if (dayPctFrac !== '') {
      sh.getRange(row, C.PCT)
        .setNumberFormat('0.00%')
        .setValue(dayPctFrac);
    } else {
      sh.getRange(row, C.PCT).clearContent();
    }

    if (p6mFrac !== '') {
      sh.getRange(row, COL_52H)
        .setNumberFormat('0.00%')
        .setValue(p6mFrac);
    } else {
      sh.getRange(row, COL_52H).clearContent();
    }

    sh.getRange(row, C.PUT, 1, 10).setValues([[
      putR,
      callR,
      ema20,
      hvn,
      avwap,
      rsi,
      pcr,
      zgam,
      rvol,
      slope
    ]]);

    const fuerza = _num(sh.getRange(row, C.FUE).getValue());
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

  _strengthTrendSave_('core', strengthHistory, strengthToday, strengthUpdates);

  t = _coreLogPhase('process_write_sheet', tProcess, `ok=${ok} jsonErr=${jsonErr} skip=${skip}`);

  console.log(`[recalcYPRICE_CORE] END total=${_coreMsTo(_coreMs() - tStart)}`);
}


/* =========================================================
   YPRICE_CORE
   Copia aislada para CORE.
   Usa:
   - CacheService 60 s con key YP_CORE_...
   - PropertiesService con LP_DICT_CORE_V1
   No usa LP_DICT_V1.
   ========================================================= */

function YPRICE_CORE(sym, forceExt) {
  sym = String(sym).trim().toUpperCase();

  /* ---------- caché 60 s separada ---------- */
  const cache = CacheService.getScriptCache();
  const key   = `YP_CORE_${sym}_${forceExt}`;
  const hit   = cache.get(key);

  if (hit) return Number(hit);

  /* ---------- descarga intradía ---------- */
  const chart = prePost => {
    const url = `https://query1.finance.yahoo.com/v8/finance/chart/${sym}` +
                `?range=1d&interval=1m&includePrePost=${prePost}`;

    return JSON.parse(UrlFetchApp.fetch(url).getContentText())
      ?.chart?.result?.[0];
  };

  let r = chart(true);
  if (!r?.timestamp?.length) r = chart(false);

  let price = null;

  const quote = r?.indicators?.quote?.[0];

  if (quote?.close?.length && r?.timestamp?.length) {
    const close      = quote.close;
    const timestamps = r.timestamp;

    for (let i = close.length - 1; i >= 0; i--) {
      if (close[i] == null) continue;

      const hET = Utilities.formatDate(
        new Date(timestamps[i] * 1000),
        'America/New_York',
        'HHmm'
      );

      const isExt = hET < '0930' || hET >= '1600';

      price = forceExt ? (isExt ? close[i] : null) : close[i];

      if (!price) price = close[i];

      break;
    }
  }

  /* ---------- Fallback quoteSummary ---------- */
  if (price == null) {
    const url = `https://query1.finance.yahoo.com/v10/finance/quoteSummary/${sym}?modules=price`;

    price = JSON.parse(UrlFetchApp.fetch(url).getContentText())
      ?.quoteSummary?.result?.[0]?.price?.regularMarketPrice?.raw
      || null;
  }

  /* ---------- Último precio persistente separado para CORE ---------- */
  const store   = PropertiesService.getScriptProperties();
  const dictKey = 'LP_DICT_CORE_V1';

  let dict = {};

  try {
    dict = JSON.parse(store.getProperty(dictKey) || '{}') || {};
  } catch (e) {
    dict = {};
  }

  if (price == null) {
    const prev = dict?.[sym]?.p;
    if (prev != null) return Number(prev);
    return null;
  }

  /* ---------- guarda caché rápida ---------- */
  cache.put(key, String(price), 60);

  /* ---------- guarda fallback persistente CORE ---------- */
  dict[sym] = {
    p: Number(price),
    t: Date.now()
  };

  let entries = Object.entries(dict);

  // CORE tiene pocos tickers. Guardar 60 es suficiente y evita quota.
  if (entries.length > 60) {
    entries.sort((a, b) => (b[1]?.t || 0) - (a[1]?.t || 0));
    dict = Object.fromEntries(entries.slice(0, 60));
  }

  try {
    store.setProperty(dictKey, JSON.stringify(dict));
  } catch (e) {
    if (_coreIsPropertyQuotaError(e)) {
      console.log(`[YPRICE_CORE] quota exceeded -> purging ${dictKey}`);

      try {
        store.deleteProperty(dictKey);
      } catch (e2) {
        console.log(`[YPRICE_CORE] purge failed: ${e2 && e2.stack ? e2.stack : e2}`);
      }
    } else {
      throw e;
    }
  }

  return Number(price);
}


/* =========================================================
   Helpers CORE
   Nombres únicos para no pisar los helpers del fichero trading.
   ========================================================= */

function _coreMs() {
  return Date.now();
}

function _coreMsTo(ms) {
  return (ms / 1000).toFixed(2) + 's';
}

function _coreLogPhase(name, t0, extra) {
  const dt = Date.now() - t0;

  console.log(
    `[recalcYPRICE_CORE][PHASE] ${name} dt=${_coreMsTo(dt)}` +
    `${extra ? ' ' + extra : ''}`
  );

  return Date.now();
}

function _coreColByHeader(sh, header, headerRow = 1) {
  const headers = sh
    .getRange(headerRow, 1, 1, sh.getLastColumn())
    .getDisplayValues()[0];

  const idx = headers.findIndex(h => String(h || '').trim() === header);

  return idx >= 0 ? idx + 1 : null;
}

function _coreResponseCode(resp) {
  try {
    return resp && typeof resp.getResponseCode === 'function'
      ? resp.getResponseCode()
      : null;
  } catch (e) {
    return null;
  }
}

function _coreIsPropertyQuotaError(e) {
  const msg = String((e && e.message) || e || '').toLowerCase();

  return (
    msg.indexOf('property storage quota') >= 0 ||
    msg.indexOf('cuota de almacenamiento de la propiedad') >= 0 ||
    (msg.indexOf('cuota') >= 0 && msg.indexOf('propiedad') >= 0) ||
    (msg.indexOf('quota') >= 0 && msg.indexOf('propert') >= 0)
  );
}


/* =========================================================
   Limpieza manual opcional SOLO para CORE
   Ejecutar a mano si alguna vez quieres resetear el fallback CORE.
   No borra LP_DICT_V1.
   ========================================================= */

function purgeYpriceCoreProps() {
  PropertiesService.getScriptProperties().deleteProperty('LP_DICT_CORE_V1');
  console.log('[recalcYPRICE_CORE] purged LP_DICT_CORE_V1');
}
