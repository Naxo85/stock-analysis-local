/* =======================================================================
   0.  Utilidades genéricas
   =======================================================================*/
function _fmtSmart(n){                         // redondeo “inteligente”
  const abs = Math.abs(n);
  const d   = (abs < 5 ? 3 : abs < 20 ? 2 : abs < 100 ? 1 : 0);
  return n.toFixed(d).replace('.', ',');
}

/* =======================================================================
   0.b  Alias de tickers por proveedor
   =======================================================================*/

function _providerSym(sym) {
  const s = String(sym || '').trim().toUpperCase();

  const aliases = {
    // En la Sheet usamos BNY, pero algunos proveedores siguen funcionando mejor con BK.
    BNY: 'BK'
  };

  return aliases[s] || s;
}

function _displaySym(sym) {
  return String(sym || '').trim().toUpperCase();
}

/* cache en memoria  ---------------------------------------------------- */
function _cacheMem(key, getter, ttl_ms){
  const c  = CacheService.getScriptCache();
  const hit= c.get(key);
  if (hit) return JSON.parse(hit);
  const val= getter();
  if (val!=null) c.put(key, JSON.stringify(val), ttl_ms/1000);
  return val;
}

/* =======================================================================
   1.  Descarga de precios diarios  (Yahoo ➊ → Finnhub ➋ → FMP ➌)
   =======================================================================*/
function _dailyOHLC(sym){
  sym = _providerSym(sym);
  return _cacheMem('OHLC_'+sym, () => {

    /* ---------- ➊ YAHOO (3 meses) ----------------------------------- */
    try{
      const yURL = `https://query1.finance.yahoo.com/v8/finance/chart/${sym}` +
                   `?range=3mo&interval=1d`;
      const yJS  = JSON.parse(UrlFetchApp.fetch(yURL).getContentText());
      const q    = yJS?.chart?.result?.[0]?.indicators?.quote?.[0];
      const ts   = yJS?.chart?.result?.[0]?.timestamp;
      if (q && ts){
        const rows=[];
        for (let i=0;i<ts.length;i++){
          const c=q.close[i];
          if (c==null) continue;              // elimina velas “vacías”
          const v = yJS?.chart?.result?.[0]?.indicators?.quote?.[0]?.volume?.[i];
          rows.push({h:q.high[i]??c, l:q.low[i]??c, c:c, v:v, d: ts[i]*1000});
        }
        if (rows.length >= 10) return rows;
      }
    }catch(e){}

    /* ---------- ➋ FINNHUB (últimos 90 d) ---------------------------- */
    try{
      const to   = Math.floor(Date.now()/1000);
      const from = to - 90*24*3600;
      const k    = PropertiesService.getScriptProperties().getProperty('FINN_KEY');
      const fURL = `https://finnhub.io/api/v1/stock/candle?symbol=${sym}` +
                   `&resolution=D&from=${from}&to=${to}&token=${k}`;
      const fJS  = JSON.parse(UrlFetchApp.fetch(fURL).getContentText());
      if (fJS.s === 'ok'){
        const rows = fJS.c.map((c,i)=>({h:fJS.h[i], l:fJS.l[i], c:c, d:fJS.t[i]*1000}));
        if (rows.length >= 10) return rows;
      }
    }catch(e){}

    /* ---------- ➌ FMP (últimos 90 d) -------------------------------- */
    try{
      const k   = PropertiesService.getScriptProperties().getProperty('FMP_KEY');
      const u   = `https://financialmodelingprep.com/api/v3/historical-price-full/`+
                  `${sym}?timeseries=90&apikey=${k}`;
      const js  = JSON.parse(UrlFetchApp.fetch(u).getContentText());
      const h   = js?.historical;
      if (h?.length){
        const rows = h.map(o=>({h:o.high,l:o.low,c:o.close,d:Date.parse(o.date)})).reverse();
        if (rows.length >= 10) return rows;
      }
    }catch(e){}

    return null;                                // ningún proveedor válido
  }, 15*60*1000);                               // cache 15 min
}

/* ======================================================================
   2.  ATR “robusto” (hasta 60 velas, media recortada 10 %)
   =====================================================================*/
/* =======================================================================
   2.  ATR “robusto” (cap TR + trim 10% + Wilder smoothing)
   =====================================================================*/
function _atr(sym, days){
  days = days || 60;

  const rows = _dailyOHLC(sym);
  if (!rows || rows.length < 10) return {atr:null, close:null};

  // --- Parámetros robustez ---
  const capPct   = 0.25;   // TR máximo permitido = prevClose * 25%
  const trimFrac = 0.10;   // recorte 10%

  // 1) True Range diario (con cap)
  const tr = [];
  for (let i = 1; i < rows.length; i++){
    const hi   = rows[i]?.h;
    const lo   = rows[i]?.l;
    const prev = rows[i-1]?.c;

    if (![hi, lo, prev].every(v => v != null && isFinite(v))) continue;

    let trVal = Math.max(hi - lo, Math.abs(hi - prev), Math.abs(lo - prev));

    // cap anti-outlier (splits mal ajustados, gaps raros, etc.)
    const cap = Math.abs(prev) * capPct;
    if (isFinite(cap) && cap > 0 && trVal > cap) trVal = cap;

    if (isFinite(trVal) && trVal >= 0) tr.push(trVal);
  }

  // 2) Ventana últimos ≤days TR
  const win = tr.slice(-Math.min(days, tr.length));
  if (!win.length) return {atr:null, close: rows.at(-1)?.c ?? null};

  // 3) Trim 10% (robusto) sin romper si hay pocos puntos
  const sorted = win.slice().sort((a,b)=>a-b);
  const k = Math.floor(trimFrac * sorted.length);
  const trimmed = (sorted.length > 2*k) ? sorted.slice(k, sorted.length - k) : sorted;
  if (!trimmed.length) return {atr:null, close: rows.at(-1)?.c ?? null};

  // 4) Wilder smoothing sobre la serie recortada
  // Usamos n = min(days, trimmed.length) para que el smoothing sea coherente si hay menos datos
  const n = Math.min(days, trimmed.length);
  let atr = trimmed[0];
  for (let i = 1; i < trimmed.length; i++){
    atr = (atr * (n - 1) + trimmed[i]) / n;
  }

  // 5) Close actual (como antes)
  const lastClose = rows.at(-1)?.c ?? null;

  return {atr: atr, close: lastClose};
}

/* ======================================================================
   3.  Rango de soporte / resistencia con multiplicador dinámico
   =====================================================================*/
function _atrRange(sym, side, m1, m2){
  const {atr, close} = _atr(sym, 60);           // usa ATR-60 robusto
  if (!atr) return 'N/A';

  /* --------- multiplicadores automáticos si el usuario no los pasa --- */
  if (m1 == null || m2 == null){
    const atrPct = atr / close;                 // volatilidad relativa
    if (atrPct < 0.02){       // volatilidad muy baja  (< 2 %)
      m1 = 2.0;  m2 = 2.5;
    } else if (atrPct > 0.05){ // volatilidad muy alta (> 5 %)
      m1 = 0.8;  m2 = 1.2;
    } else {                  // rango “normal” (2–5 %)
      m1 = 1.0;  m2 = 1.5;
    }
  }

  const vals = (side === 'S')
      ? [close - m2 * atr, close - m1 * atr]    // soporte
      : [close + m1 * atr, close + m2 * atr];   // resistencia

  return vals.map(_fmtSmart).join(' - ');
}

/* ======================================================================
   4.  Funciones para la hoja  (sin cambios)
   =====================================================================*/
function SOPORTE(sym, m1, m2){
  return _atrRange(String(sym).toUpperCase(), 'S', m1, m2);
}
function RESISTENCIA(sym, m1, m2){
  return _atrRange(String(sym).toUpperCase(), 'R', m1, m2);
}

/* ======================================================================
   5.  Indicadores auxiliares para la hoja
   =====================================================================*/

/**  ATR robusto de 60 días (mismo cálculo que en _atr) */
function ATR30(sym){
  const {atr} = _atr(String(sym).toUpperCase(), 30);
  return atr != null ? +(atr.toFixed(2)) : null;
}

function ATR30P(sym){
  const {atr, close} = _atr(String(sym).toUpperCase(), 30);
  return (atr && close) ? +(atr / close).toFixed(4) : null;
}

function ATR20P(sym){
  const {atr, close} = _atr(String(sym).toUpperCase(), 20);
  return (atr && close) ? +(atr / close).toFixed(4) : null;
}

/**  SMA de 60 cierres (precio medio de los últimos 60 días) */
function SMA60(sym){                  // =SMA60("AAPL")
  sym = String(sym).toUpperCase();
  const rows = _dailyOHLC(sym);
  if (!rows || rows.length === 0) return 'N/A';
  const closes = rows.slice(-60).map(r => r.c);          // últimos ≤ 60
  if (closes.length === 0) return 'N/A';
  const sma = closes.reduce((s, x) => s + x, 0) / closes.length;
  return _fmtSmart(sma);
}

function VOL30(sym){
  const rows = _dailyOHLC(String(sym).toUpperCase());
  if (!rows || rows.length === 0) return null;

  const vols = rows.slice(-30).map(r => r.v).filter(v => v != null);
  if (!vols.length) return null;

  const avgVol = vols.reduce((s, v) => s + v, 0) / vols.length;
  return +(avgVol / 1000000).toFixed(2);
}

/**  Volumen medio de los últimos 10 días (en millones)  */
function VOL10(sym){                                   
  sym = String(sym).toUpperCase();
  const rows = _dailyOHLC(sym);
  if (!rows || rows.length === 0) return null;

  const vols = rows.slice(-10).map(r => r.v).filter(v => v != null);
  if (!vols.length) return null;

  const avgVol = vols.reduce((s, v) => s + v, 0) / vols.length;
  return +(avgVol / 1000000).toFixed(2);        
}

/**
 * Diferencia del volumen del ÚLTIMO DÍA DE MERCADO completo frente a la
 * media de los 20 días anteriores. Devuelve un número decimal
 * (-0.702 → –70,2 %), listo para formatear como “%”.
 */
function VOLDELTA20(sym){
  sym = String(sym).toUpperCase();

  const rows = _dailyOHLC(sym);
  if (!rows || rows.length < 31) return null;        // necesitamos ≥31 velas

  /* ---------- 1) identifica la última vela completa ----------------- */
  const nowNY   = new Date().toLocaleString('en-US', {timeZone:'America/New_York'});
  const todayNY = new Date(nowNY);                   // día civil en NY
  todayNY.setHours(0,0,0,0);                         // 00:00 NY

  // empezamos por la última fila y retrocedemos hasta hallar d < hoy
  let idx = rows.length - 1;
  while (idx >= 0 && rows[idx].d >= todayNY.getTime()){
    idx--;
  }
  if (idx < 0) return null;                          // nunca debería ocurrir

  const prevVol = rows[idx].v;
  if (prevVol == null) return null;

  /* ---------- 2) media de los 20 días anteriores a esa fecha -------- */
  const start = Math.max(0, idx - 20);               // 20 velas previas
  const vols20 = rows.slice(start, idx)
                     .map(r => r.v)
                     .filter(v => v != null);
  if (!vols20.length) return null;

  const avgVol = vols20.reduce((s,v)=>s+v,0) / vols20.length;

  /* ---------- 3) desviación relativa ------------------------------- */
  return +((prevVol / avgVol) - 1).toFixed(3);       //  -0.702  →  -70,2 %
}

/* ======================================================================
6. Variación % vs. hace 7 y 20 TRADING DAYS
=====================================================================*/

/** Índice de la última vela COMPLETA (día cerrado en NY) */
function _lastCloseIdx(rows){
const nowNY = new Date().toLocaleString('en-US',{timeZone:'America/New_York'});
const todayNY = new Date(nowNY); todayNY.setHours(0,0,0,0);
let i = rows.length - 1;
while (i >= 0 && rows[i].d >= todayNY.getTime()) i--; // salta vela “de hoy”
return i; // −1 si no hay
}

/** % variación entre un precio “actual” (opcional) y la vela N‑trading‑days atrás
 *
 *    _priceDeltaTD("AAPL", 5)          → usa el último cierre
 *    _priceDeltaTD("AAPL", 5, 213.45)  → usa 213,45 como precio actual
 */
function _priceDeltaTD(sym, nTD, spot){
  sym = String(sym).toUpperCase();
  const rows = _dailyOHLC(sym);
  if (!rows) return null;

  /* ── índice de la última vela COMPLETA ───────────────────────────── */
  const last = _lastCloseIdx(rows);
  if (last < nTD) return null;               // no hay suficientes velas

  /* ── precio “actual” ── */
  let cLast = Number(spot);
  if (!isFinite(cLast) || cLast <= 0) {      // si no se pasó, usa el close
    cLast = rows[last]?.c;
  }
  const cPast = rows[last - nTD]?.c;
  if (cLast == null || cPast == null || cPast === 0) return null;

  return +((cLast / cPast) - 1).toFixed(4);  // 0.083 → 8,3 %
}

/** % cambio de los últimos 5 trading‑days */
function DELTA5(sym, spot){                  // =DELTA5("AAPL"; E2)
  return _priceDeltaTD(sym, 5, spot);
}

/** % cambio de los últimos 20 trading‑days */
function DELTA20(sym, spot){                 // =DELTA20("AAPL"; E2)
  return _priceDeltaTD(sym, 20, spot);
}


/* =====================================================================
   HL_P — % de sesiones con rango intradía ≥ umbral elegido (caché 12 h)
   =====================================================================*/
/**
 * Devuelve la frecuencia (en %) con la que un ticker cumple
 * (High‑Low)/Close ≥ pct % en la ventana de los últimos `days` días.
 *
 *   =HL_P("TSM")              → usa 5 % y 60 días (por defecto)
 *   =HL_P("TSM"; 4)           → 4 % y 60 días
 *   =HL_P("TSM"; 4; 120)      → 4 % y 120 días
 *   =HL_P(A2; 0.035)          → 3.5 % en decimal
 *
 *  ▸ `pct` puede pasarse como 4  → 0.04,  5 → 0.05,  o ya en decimal (0.04).
 */
function HL_P(sym, pct, days) {
  sym  = String(sym).toUpperCase();
  pct  = (pct === undefined) ? 5 : pct;     // 5 % por defecto
  days = days || 60;

  // Si el usuario pasó 4 ó 5 lo convertimos a 0,04 / 0,05
  const thr = (pct >= 1) ? pct / 100 : pct; // umbral en decimal

  const cacheKey = `HL_P_${sym}_${days}_${thr}`;
  return _cacheMem(cacheKey, () => {
    const rows = _dailyOHLC(sym);           // ya cachea 15 min
    if (!rows || rows.length < 2) return null;

    const slice = rows.slice(-days);
    const hits  = slice.filter(r => (r.h - r.l) / r.c >= thr).length;
    const pctHits = (hits / slice.length) * 100;

    return +pctHits.toFixed(1);             // redondeo a 0,1 %
  }, 12 * 60 * 60 * 1000);                  // TTL = 12 h
}


/**********************************************************
 * DD90 (Drawdown Percentile) - stack independiente
 * - No toca _dailyOHLC()
 * - Descarga Yahoo 2y (interval 1d)
 * - Caché alta (CacheService + ScriptProperties)
 **********************************************************/

const DD_CACHE_BUSTER = 'dd_v2025-12-21_1';   // cambia esto si quieres “reset” total
const DD_TTL_MS = 24 * 60 * 60 * 1000;        // 24h (caché alta)
const DD_RANGE = '2y';                        // 2y recomendado

/**
 * API pública para Sheets:
 * =DD90("RKLB")     -> percentil 90 del drawdown (decimal negativo)
 * =DDP("RKLB", 0.8) -> percentil 80
 * =DDMAX("RKLB")    -> peor drawdown (mínimo)
 *
 * Formato recomendado en Sheet: porcentaje.
 */
function DD90(sym) { return DDP(sym, 0.90); }

function DDP(sym, p) {
  sym = String(sym || '').trim().toUpperCase();
  p = (p == null) ? 0.90 : Number(p);
  if (!sym) return '';
  if (!isFinite(p)) p = 0.90;
  if (p > 1) p = p / 100;          // por si pasan 90 en vez de 0.90
  p = Math.max(0, Math.min(1, p));

  const key = `DDP_${DD_CACHE_BUSTER}_${sym}_${p}`;
  return _dd_cache(key, () => {
    const closes = _dd_closes_2y(sym);
    if (!closes || closes.length < 30) return 'N/A';

    const dds = _dd_drawdownSeries(closes); // negativos (0..-1)
    if (!dds.length) return 'N/A';

    // percentil p de la “profundidad”:
    // p=0.90 -> un drawdown “típico severo” (no el peor)
    const val = _dd_quantile(dds, p);

    // Redondeo razonable (decimal)
    return isFinite(val) ? Number(val.toFixed(4)) : 'N/A';
  }, DD_TTL_MS);
}

function DDMAX(sym) {
  sym = String(sym || '').trim().toUpperCase();
  if (!sym) return '';
  const key = `DDMAX_${DD_CACHE_BUSTER}_${sym}`;
  return _dd_cache(key, () => {
    const closes = _dd_closes_2y(sym);
    if (!closes || closes.length < 30) return 'N/A';
    const dds = _dd_drawdownSeries(closes);
    if (!dds.length) return 'N/A';
    const min = Math.min.apply(null, dds);
    return isFinite(min) ? Number(min.toFixed(4)) : 'N/A';
  }, DD_TTL_MS);
}

/**********************************************************
 * Internals
 **********************************************************/

// Devuelve array de cierres (Number) en orden cronológico asc
function _dd_closes_2y(sym){
  sym = _providerSym(sym);
  const cacheKey = `DD_CLOSES_${DD_CACHE_BUSTER}_${sym}_${DD_RANGE}`;

  // 1) ScriptCache (rápido)
  const c = CacheService.getScriptCache();
  const hit = c.get(cacheKey);
  if (hit) {
    try {
      const arr = JSON.parse(hit);
      if (Array.isArray(arr) && arr.length) return arr;
    } catch(_) {}
  }

  // 2) ScriptProperties (persistente, “caché alta” real)
  const P = PropertiesService.getScriptProperties();
  const raw = P.getProperty(cacheKey);
  if (raw) {
    try {
      const obj = JSON.parse(raw);
      const fresh = obj && isFinite(obj.ts) && (Date.now() - obj.ts) < DD_TTL_MS;
      if (fresh && Array.isArray(obj.val) && obj.val.length) {
        // repuebla ScriptCache para acelerar
        c.put(cacheKey, JSON.stringify(obj.val), Math.floor(DD_TTL_MS/1000));
        return obj.val;
      }
    } catch(_) {}
  }

  // 3) fetch Yahoo (2y, 1d)
  const url = `https://query1.finance.yahoo.com/v8/finance/chart/${encodeURIComponent(sym)}?range=${DD_RANGE}&interval=1d`;
  try {
    const res = UrlFetchApp.fetch(url, { muteHttpExceptions: true });
    const code = res.getResponseCode();
    const txt  = res.getContentText();
    if (code !== 200) return 'N/A';

    const js = JSON.parse(txt);
    const r0 = js?.chart?.result?.[0];
    const q  = r0?.indicators?.quote?.[0];
    const cs = q?.close;

    if (!Array.isArray(cs) || !cs.length) return 'N/A';

    // Filtra nulls y no-finitos, conserva orden
    const closes = cs.filter(v => v != null && isFinite(v)).map(Number);
    if (closes.length < 30) return 'N/A';

    // guarda en caches
    c.put(cacheKey, JSON.stringify(closes), Math.floor(DD_TTL_MS/1000));
    try {
      const payload = JSON.stringify({ ts: Date.now(), val: closes });
      // ojo límite ~9KB, por 2y suele caber; si no, simplemente no lo guardamos
      if (payload.length < 9000) P.setProperty(cacheKey, payload);
    } catch(_) {}

    return closes;
  } catch(e) {
    return 'N/A';
  }
}

// Serie de drawdown vs máximo acumulado: valores en [-1..0]
function _dd_drawdownSeries(closes){
  let peak = -Infinity;
  const dds = [];
  for (let i = 0; i < closes.length; i++){
    const c = closes[i];
    if (!isFinite(c) || c <= 0) continue;
    if (c > peak) peak = c;
    const dd = (c / peak) - 1;     // 0..negativo
    if (isFinite(dd)) dds.push(dd);
  }
  return dds;
}

// Quantile “nearest rank” (simple y estable para Sheets)
function _dd_quantile(arr, p){
  if (!arr.length) return NaN;
  const s = arr.slice().sort((a,b)=>a-b); // más negativo -> más “profundo”
  if (p <= 0) return s[0];
  if (p >= 1) return s[s.length - 1];
  const idx = Math.max(0, Math.min(s.length - 1, Math.ceil(p * s.length) - 1));
  return s[idx];
}

// Caché genérico para DD (solo guarda si valor útil)
function _dd_cache(key, getter, ttl_ms){
  const c = CacheService.getScriptCache();
  const hit = c.get(key);
  if (hit != null) {
    try { return JSON.parse(hit); } catch(_) { return hit; }
  }

  const val = getter();

  // No guardar negativos “vacíos”
  const isBad = (v) => v === 'N/A' || v === '' || v == null;
  if (!isBad(val)) {
    c.put(key, JSON.stringify(val), Math.floor(ttl_ms/1000));
    // (para ddp/ddmax, también podríamos persistir en properties, pero ya persistimos closes)
  }
  return val;
}

/** Precio spot (último) SIN Yahoo: Finnhub -> FMP -> fallback close */
function SPOT(sym){
  sym = _providerSym(sym);
  if (!sym) return null;

  return _cacheMem('SPOT_' + sym, () => {
    // 1) Finnhub quote
    try{
      const k = PropertiesService.getScriptProperties().getProperty('FINN_KEY');
      if (k){
        const u = `https://finnhub.io/api/v1/quote?symbol=${encodeURIComponent(sym)}&token=${k}`;
        const r = UrlFetchApp.fetch(u, { muteHttpExceptions:true });
        if (r.getResponseCode() === 200){
          const js = JSON.parse(r.getContentText());
          // Finnhub: c = current price, pc = prev close
          const p = Number(js?.c);
          if (isFinite(p) && p > 0) return p;
        }
      }
    } catch(e){}

    // 2) FMP quote
    try{
      const k = PropertiesService.getScriptProperties().getProperty('FMP_KEY');
      if (k){
        const u = `https://financialmodelingprep.com/api/v3/quote/${encodeURIComponent(sym)}?apikey=${k}`;
        const r = UrlFetchApp.fetch(u, { muteHttpExceptions:true });
        if (r.getResponseCode() === 200){
          const js = JSON.parse(r.getContentText());
          const p = Number(js?.[0]?.price);
          if (isFinite(p) && p > 0) return p;
        }
      }
    } catch(e){}

    return null;
  }, 3600 * 1000); // cache 1h
}

/***********************
 * NEXT_EARN (Finnhub -> Nasdaq fallback)
 * Custom function para Google Sheets:
 *  - Devuelve la próxima fecha de earnings (>= hoy) para un ticker
 *  - Fuente principal: Finnhub /calendar/earnings
 *  - Backup: calendario publico de Nasdaq
 * FINN_KEY solo es necesaria para la fuente principal.
 ***********************/

const NEXT_EARN_CACHE_TTL_SEC = 6 * 60 * 60; // 6h
const NEXT_EARN_UNKNOWN_CACHE_TTL_SEC = 5 * 60; // 5 min
const NEXT_EARN_LOOKAHEAD_DAYS = 270;        // ~9 meses
const NEXT_EARN_VISIBLE_DAYS = 30;
const NEXT_EARN_UNKNOWN = '?';
const NEXT_EARN_REPORTS_URL =
  'https://reports-714254943648.europe-southwest1.run.app';
const NEXT_EARN_REPORTS_CACHE_VERSION = 'v1';
const NEXT_EARN_NASDAQ_URL = 'https://api.nasdaq.com/api/calendar/earnings';
const NEXT_EARN_NASDAQ_CACHE_VERSION = 'v4';
const NEXT_EARN_NASDAQ_LOCK_WAIT_MS = 10 * 1000;

function NEXT_EARN(tickerOrRange) {
  // Soporta rango/array
  if (Array.isArray(tickerOrRange)) {
    return tickerOrRange.map(row => [ _safeNextEarnOne(row[0]) ]);
  }
  return _safeNextEarnOne(tickerOrRange);
}

function _safeNextEarnOne(ticker) {
  try {
    return _nextEarnFinnhubOne(ticker);
  } catch (e) {
    return '';
  }
}

function _nextEarnFinnhubOne(ticker) {
  const sym = _providerSym(ticker);
  if (!sym) return '';

  const k = PropertiesService.getScriptProperties().getProperty('FINN_KEY');
  const tz = Session.getScriptTimeZone();
  const today = _ymd(new Date(), tz);
  const publishedDate = _nextEarnPublishedReportDate(sym, today);

  if (_isYmd(publishedDate)) {
    return _nextEarnDisplayValue(publishedDate, today);
  }

  if (!k) return _nextEarnNasdaqOne(sym, today);

  const to = _ymd(new Date(Date.now() + NEXT_EARN_LOOKAHEAD_DAYS * 24 * 3600 * 1000), tz);

  // Cache por ticker+today (si cambia el día, recalcula)
  const cache = CacheService.getScriptCache();
  const ckey = `NEXT_EARN_FH_v2_${sym}_${today}`;
  const hit = cache.get(ckey);
  if (hit !== null && hit !== undefined) {
    return _isYmd(hit)
      ? _nextEarnDisplayValue(hit, today)
      : _nextEarnNasdaqOne(sym, today);
  }

  let out = '';
  try {
    const url =
      `https://finnhub.io/api/v1/calendar/earnings` +
      `?symbol=${encodeURIComponent(sym)}` +
      `&from=${today}` +
      `&to=${to}` +
      `&token=${encodeURIComponent(k)}`;

    const resp = UrlFetchApp.fetch(url, { muteHttpExceptions: true });
    if (resp.getResponseCode() !== 200) {
      cache.put(ckey, NEXT_EARN_UNKNOWN, NEXT_EARN_UNKNOWN_CACHE_TTL_SEC);
      return _nextEarnNasdaqOne(sym, today);
    }

    const js = JSON.parse(resp.getContentText());
    const arr = Array.isArray(js) ? js : (js && (js.earningsCalendar || js.data) || []);
    if (!Array.isArray(arr) || !arr.length) {
      cache.put(ckey, NEXT_EARN_UNKNOWN, NEXT_EARN_UNKNOWN_CACHE_TTL_SEC);
      return _nextEarnNasdaqOne(sym, today);
    }

    const fut = arr
      .map(it => _norm10(it && (it.date || it.reportDate || it.reportedDate || it.actualReleaseDate)))
      .filter(_isYmd)
      .filter(d => d >= today)
      .sort(); // asc

    out = fut[0] || '';
  } catch (e) {
    out = NEXT_EARN_UNKNOWN;
  }

  // Cachea también el estado desconocido para evitar martillar el API.
  const cachedValue = out || NEXT_EARN_UNKNOWN;
  cache.put(
    ckey,
    cachedValue,
    _isYmd(cachedValue)
      ? NEXT_EARN_CACHE_TTL_SEC
      : NEXT_EARN_UNKNOWN_CACHE_TTL_SEC
  );

  return _isYmd(cachedValue)
    ? _nextEarnDisplayValue(cachedValue, today)
    : _nextEarnNasdaqOne(sym, today);
}

function _nextEarnPublishedReportDate(sym, today) {
  const cache = CacheService.getScriptCache();
  const cacheKey =
    `NEXT_EARN_REPORT_${NEXT_EARN_REPORTS_CACHE_VERSION}_${sym}_${today}`;
  const cached = cache.get(cacheKey);

  if (_isYmd(cached)) return cached;

  try {
    const response = UrlFetchApp.fetch(
      `${NEXT_EARN_REPORTS_URL}?symbol=${encodeURIComponent(sym)}`,
      { muteHttpExceptions: true }
    );

    if (response.getResponseCode() !== 200) return null;

    const json = JSON.parse(response.getContentText());
    const earnings = json && json.analyst_ratings_summary;
    const nextDate = _norm10(earnings && earnings.next_earnings_date);

    if (!_isYmd(nextDate) || nextDate < today) return null;

    cache.put(cacheKey, nextDate, NEXT_EARN_CACHE_TTL_SEC);
    return nextDate;
  } catch (e) {
    return null;
  }
}

function refreshUnknownNextEarnFormulasOncePerDay_(sheet) {
  const timezone = Session.getScriptTimeZone();
  const today = _ymd(new Date(), timezone);
  const propertyKey = 'NEXT_EARN_UNKNOWN_FORMULA_REFRESH_v1';
  const properties = PropertiesService.getDocumentProperties();

  if (properties.getProperty(propertyKey) === today) return;

  const formulaCells = sheet
    .createTextFinder('NEXT_EARN')
    .matchFormulaText(true)
    .findAll();
  let refreshed = 0;

  formulaCells.forEach(cell => {
    if (String(cell.getDisplayValue() || '').trim() !== '?') return;
    const formula = cell.getFormula();
    if (!formula) return;
    cell.setFormula(`${formula} `);
    refreshed++;
  });

  if (refreshed > 0) {
    SpreadsheetApp.flush();
  }

  properties.setProperty(propertyKey, today);
  console.log(`[NEXT_EARN] refreshed unknown formulas=${refreshed} date=${today}`);
}

/********** Helpers fecha **********/
/** Busca el ticker en los calendarios diarios de Nasdaq dentro de la ventana visible. */
function _nextEarnNasdaqOne(sym, today) {
  // Aunque la carga sea parcial, busca en todas las fechas que sí estén
  // disponibles. Un fallo ajeno a este ticker no debe ocultar su fecha.
  _ensureNasdaqEarningsWindow(today);

  const dates = _nasdaqCandidateDates(today);
  for (const candidateDate of dates) {
    const symbols = _nasdaqEarningsSymbolsFromCache(candidateDate);

    if (symbols === null) continue;
    if (symbols.indexOf(sym) !== -1) return _nextEarnDisplayValue(candidateDate, today);
  }

  return '';
}

/**
 * Carga la ventana completa en paralelo una sola vez para toda la hoja.
 * El lock evita que varias celdas lancen simultaneamente las mismas 31 peticiones.
 */
function _ensureNasdaqEarningsWindow(today) {
  const cache = CacheService.getScriptCache();
  const dates = _nasdaqCandidateDates(today);
  const dateKeys = dates.map(_nasdaqDateCacheKey);
  const readyKey = `NEXT_EARN_NQ_${NEXT_EARN_NASDAQ_CACHE_VERSION}_READY_${today}`;

  if (_nasdaqWindowIsCached(cache, readyKey, dateKeys)) return true;

  const lock = LockService.getScriptLock();
  if (!lock.tryLock(NEXT_EARN_NASDAQ_LOCK_WAIT_MS)) return false;

  try {
    // Otra celda puede haber completado la carga mientras esperabamos el lock.
    if (_nasdaqWindowIsCached(cache, readyKey, dateKeys)) return true;

    const requests = dates.map(ymd => ({
      url: `${NEXT_EARN_NASDAQ_URL}?date=${encodeURIComponent(ymd)}`,
      muteHttpExceptions: true,
      headers: {
        Accept: 'application/json, text/plain, */*',
        'User-Agent': 'Mozilla/5.0 (compatible; GoogleAppsScript)'
      }
    }));
    const responses = UrlFetchApp.fetchAll(requests);

    if (!Array.isArray(responses) || responses.length !== dates.length) return false;

    const values = {};
    let completedDates = 0;
    for (let index = 0; index < responses.length; index++) {
      const symbols = _symbolsFromNasdaqResponse(responses[index]);
      if (symbols === null) continue;
      values[dateKeys[index]] = symbols.length ? symbols.join('|') : '!';
      completedDates++;
    }

    if (completedDates === 0) return false;
    if (completedDates === dates.length) values[readyKey] = '1';
    cache.putAll(values, NEXT_EARN_CACHE_TTL_SEC);
    return completedDates === dates.length;
  } catch (e) {
    return false;
  } finally {
    lock.releaseLock();
  }
}

function _nasdaqCandidateDates(today) {
  return Array.from(
    { length: NEXT_EARN_VISIBLE_DAYS + 1 },
    (_, offset) => _addDaysYmd(today, offset)
  ).filter(ymd => {
    const [Y, M, D] = ymd.split('-').map(Number);
    const weekday = new Date(Date.UTC(Y, M - 1, D)).getUTCDay();
    return weekday >= 1 && weekday <= 5;
  });
}

function _nasdaqWindowIsCached(cache, readyKey, dateKeys) {
  if (cache.get(readyKey) !== '1') return false;
  const hits = cache.getAll(dateKeys);
  return Object.keys(hits).length === dateKeys.length;
}

function _symbolsFromNasdaqResponse(resp) {
  try {
    if (!resp || resp.getResponseCode() !== 200) return null;

    const js = JSON.parse(resp.getContentText());
    if (!js || !js.data || !Object.prototype.hasOwnProperty.call(js.data, 'rows')) return null;

    const rows = Array.isArray(js.data.rows) ? js.data.rows : [];
    return rows
      .map(row => String(row && row.symbol || '').trim().toUpperCase())
      .filter(Boolean)
      .filter((value, index, values) => values.indexOf(value) === index);
  } catch (e) {
    return null;
  }
}

function _nasdaqDateCacheKey(ymd) {
  return `NEXT_EARN_NQ_${NEXT_EARN_NASDAQ_CACHE_VERSION}_${ymd}`;
}

function _nasdaqEarningsSymbolsFromCache(ymd) {
  const hit = CacheService.getScriptCache().get(_nasdaqDateCacheKey(ymd));
  if (hit === null || hit === undefined) return null;
  return hit === '!' ? [] : hit.split('|');
}

function _isYmd(s) { return /^\d{4}-\d{2}-\d{2}$/.test(String(s || '')); }
function _norm10(s) { return String(s || '').slice(0, 10); }
function _ymd(d, tz) { return Utilities.formatDate(d, tz, 'yyyy-MM-dd'); }

function _addDaysYmd(ymd, days) {
  if (!_isYmd(ymd)) return '';
  const [Y, M, D] = ymd.split('-').map(Number);
  return Utilities.formatDate(
    new Date(Date.UTC(Y, M - 1, D + days)),
    'UTC',
    'yyyy-MM-dd'
  );
}

function _asDateObject(ymd) {
  if (!_isYmd(ymd)) return '';
  const [Y, M, D] = ymd.split('-').map(Number);
  return new Date(Date.UTC(Y, M - 1, D));
}

function _nextEarnDisplayValue(ymd, today) {
  if (!_isYmd(ymd)) return '';

  const daysAway = _daysBetweenYmd(today, ymd);
  if (daysAway < 0 || daysAway > NEXT_EARN_VISIBLE_DAYS) return '';

  return _asDateObject(ymd);
}

function _daysBetweenYmd(fromYmd, toYmd) {
  const [fromY, fromM, fromD] = fromYmd.split('-').map(Number);
  const [toY, toM, toD] = toYmd.split('-').map(Number);
  return Math.round(
    (Date.UTC(toY, toM - 1, toD) - Date.UTC(fromY, fromM - 1, fromD)) /
    (24 * 60 * 60 * 1000)
  );
}
