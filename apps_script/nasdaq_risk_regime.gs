/************************************************************
 * MARKET REGIME - NASDAQ
 *
 * Celda en Google Sheets:
 * =MKT_NASDAQ_RISK_REGIME()
 *
 * Trigger manual recomendado:
 * MKT_UPDATE_NASDAQ_RISK_REGIME_CACHE cada 5 minutos
 ************************************************************/

const MKT_TARGET_SHEET_NAME = "Bolsa_2026";
const MKT_TARGET_CELL_AD2 = "AD2";
const MKT_TARGET_CELL_AD3 = "AD3";

function MKT_NASDAQ_RISK_REGIME() {
  const cache = CacheService.getScriptCache();

  const value = cache.get("MKT_NASDAQ_RISK_REGIME_VALUE");
  const ts = cache.get("MKT_NASDAQ_RISK_REGIME_TS");

  if (!value) {
    return "⚪ Macro sin actualizar";
  }

  if (ts) {
    const ageMin = Math.round((Date.now() - Number(ts)) / 60000);

    if (ageMin > 60) {
      return value + " | stale " + ageMin + "m";
    }
  }

  return value;
}

function MKT_UPDATE_NASDAQ_RISK_REGIME_CACHE() {
  const lock = LockService.getScriptLock();

  if (!lock.tryLock(1000)) {
    Logger.log("MKT update skipped: lock busy");
    return;
  }

  try {
    const value = MKT_CALC_NASDAQ_RISK_REGIME_();

    const cache = CacheService.getScriptCache();
    cache.put("MKT_NASDAQ_RISK_REGIME_VALUE", value, 60 * 60 * 6);
    cache.put("MKT_NASDAQ_RISK_REGIME_TS", String(Date.now()), 60 * 60 * 6);

    const ss = SpreadsheetApp.getActiveSpreadsheet();
    const sheet = ss.getSheetByName(MKT_TARGET_SHEET_NAME);

    if (!sheet) {
      throw new Error("No existe la hoja: " + MKT_TARGET_SHEET_NAME);
    }

    const range = sheet.getRange(MKT_TARGET_CELL_AD2);
    range.setValue(value);

    const qqqDip = MKT_QQQ_DIP_FROM_RECENT_HIGH_();

    if (qqqDip !== null) {
      sheet.getRange(MKT_TARGET_CELL_AD3)
        .setValue(qqqDip)
        .setNote("Distancia de QQQ al máximo intradía de los últimos 6 meses");
    }

    Logger.log(value);
    return value;

  } finally {
    lock.releaseLock();
  }
}

function MKT_CALC_NASDAQ_RISK_REGIME_() {
  const cnnScore = MKT_CNN_FEAR_GREED_SCORE_();
  const vxnData = MKT_YF_LAST_AND_PREV_("^VXN");

  if (cnnScore === null) return "ERR CNN";
  if (!vxnData) return "ERR VXN";

  const vxn = vxnData.last;
  const vxnPrev = vxnData.prev;

  if (!vxnPrev || vxnPrev === 0) return "ERR VXN prev";

  const vxnChangePct = ((vxn - vxnPrev) / vxnPrev) * 100;

  let adjusted = cnnScore;
  let vxnLabel = "VXN OK";

  if (vxn < 20) {
    adjusted += 4;
    vxnLabel = "VXN tranquilo";
  } else if (vxn < 25) {
    adjusted += 0;
    vxnLabel = "VXN OK";
  } else if (vxn < 30) {
    adjusted -= 8;
    vxnLabel = "VXN tensión";
  } else if (vxn < 35) {
    adjusted -= 15;
    vxnLabel = "VXN risk-off";
  } else {
    adjusted -= 25;
    vxnLabel = "VXN shock";
  }

  // Movimiento rápido del VXN: afecta al score, no al texto visible.
  if (vxnChangePct >= 20) {
    adjusted -= 18;
  } else if (vxnChangePct >= 10) {
    adjusted -= 10;
  } else if (vxnChangePct <= -10) {
    adjusted += 5;
  }

  adjusted = Math.max(0, Math.min(100, Math.round(adjusted)));

  if (adjusted >= 76) return "🟢 Strong Risk-on " + adjusted + "/100 | " + vxnLabel;
  if (adjusted >= 56) return "🟢 Risk-on " + adjusted + "/100 | " + vxnLabel;
  if (adjusted >= 45) return "🟡 Mixto " + adjusted + "/100 | " + vxnLabel;
  if (adjusted >= 25) return "🟠 Risk-off " + adjusted + "/100 | " + vxnLabel;
  return "🔴 Strong Risk-off " + adjusted + "/100 | " + vxnLabel;
}

function MKT_CNN_FEAR_GREED_SCORE_() {
  const cache = CacheService.getScriptCache();

  const cached = cache.get("MKT_CNN_FEAR_GREED_SCORE");
  if (cached !== null) return Number(cached);

  const apiKey = PropertiesService
    .getScriptProperties()
    .getProperty("RAPID_YH_KEY");

  if (!apiKey) {
    Logger.log("Missing RAPID_YH_KEY");
    return null;
  }

  const url = "https://fear-and-greed-index.p.rapidapi.com/v1/fgi";

  const res = UrlFetchApp.fetch(url, {
    muteHttpExceptions: true,
    headers: {
      "x-rapidapi-key": apiKey,
      "x-rapidapi-host": "fear-and-greed-index.p.rapidapi.com",
      "Accept": "application/json"
    }
  });

  const code = res.getResponseCode();
  const text = res.getContentText();

  if (code !== 200) {
    Logger.log("Fear & Greed API error: " + code);
    Logger.log(text.slice(0, 1000));
    return null;
  }

  const json = JSON.parse(text);
  const score = json?.fgi?.now?.value;

  if (score === null || score === undefined || isNaN(Number(score))) {
    Logger.log("No Fear & Greed score found");
    Logger.log(JSON.stringify(json).slice(0, 2000));
    return null;
  }

  const rounded = Math.round(Number(score));

  // CNN / Fear & Greed: 15 min
  cache.put("MKT_CNN_FEAR_GREED_SCORE", String(rounded), 60 * 15);

  return rounded;
}

function MKT_YF_LAST_AND_PREV_(symbol) {
  const cache = CacheService.getScriptCache();
  const key = "MKT_YF_LAST_PREV_" + symbol;

  const cached = cache.get(key);
  if (cached !== null) return JSON.parse(cached);

  const url =
    "https://query1.finance.yahoo.com/v8/finance/chart/" +
    encodeURIComponent(symbol) +
    "?range=5d&interval=1d";

  const res = UrlFetchApp.fetch(url, {
    muteHttpExceptions: true,
    headers: {
      "User-Agent": "Mozilla/5.0"
    }
  });

  if (res.getResponseCode() !== 200) {
    Logger.log("Yahoo error " + symbol + ": " + res.getResponseCode());
    Logger.log(res.getContentText().slice(0, 500));
    return null;
  }

  const json = JSON.parse(res.getContentText());
  const result = json?.chart?.result?.[0];

  if (!result) return null;

  const meta = result.meta || {};

  let last = Number(meta.regularMarketPrice);
  let prev = Number(meta.chartPreviousClose || meta.previousClose);

  if (!last || !prev || isNaN(last) || isNaN(prev)) {
    const closes = result?.indicators?.quote?.[0]?.close;

    if (!closes || closes.length < 2) return null;

    const clean = closes
      .filter(v => v !== null && v !== undefined && !isNaN(Number(v)))
      .map(Number);

    if (clean.length < 2) return null;

    last = clean[clean.length - 1];
    prev = clean[clean.length - 2];
  }

  const data = {
    last: last,
    prev: prev
  };

  // VXN: 5 min
  cache.put(key, JSON.stringify(data), 60 * 5);

  return data;
}

/************************************************************
 * TESTS / CACHE
 ************************************************************/

function MKT_TEST_CNN_FEAR_GREED() {
  Logger.log(MKT_CNN_FEAR_GREED_SCORE_());
}

function MKT_TEST_NASDAQ_RISK_REGIME() {
  Logger.log(MKT_UPDATE_NASDAQ_RISK_REGIME_CACHE());
}

function MKT_CLEAR_MARKET_REGIME_CACHE() {
  const cache = CacheService.getScriptCache();

  cache.remove("MKT_CNN_FEAR_GREED_SCORE");
  cache.remove("MKT_YF_LAST_PREV_^VXN");
  cache.remove("MKT_NASDAQ_RISK_REGIME_VALUE");
  cache.remove("MKT_NASDAQ_RISK_REGIME_TS");
  cache.remove("MKT_QQQ_DIP_FROM_6M_HIGH");

  Logger.log("Market regime cache cleared");
}

/************************************************************
 * OPCIONAL: QQQ últimos 5 cierres
 ************************************************************/

function MKT_QQQ_LAST_5_CLOSES() {
  const url =
    "https://query1.finance.yahoo.com/v8/finance/chart/QQQ?range=10d&interval=1d";

  const res = UrlFetchApp.fetch(url, {
    muteHttpExceptions: true,
    headers: {
      "User-Agent": "Mozilla/5.0"
    }
  });

  if (res.getResponseCode() !== 200) {
    return [["ERR " + res.getResponseCode()]];
  }

  const json = JSON.parse(res.getContentText());
  const result = json?.chart?.result?.[0];

  if (!result) return [["ERR no data"]];

  const timestamps = result.timestamp || [];
  const closes = result.indicators?.quote?.[0]?.close || [];

  const rows = [];

  for (let i = 0; i < timestamps.length; i++) {
    const close = closes[i];

    if (close === null || close === undefined || isNaN(Number(close))) continue;

    const date = Utilities.formatDate(
      new Date(timestamps[i] * 1000),
      Session.getScriptTimeZone(),
      "yyyy-MM-dd"
    );

    rows.push([date, Math.round(Number(close) * 100) / 100]);
  }

  const last5 = rows.slice(-5);

  return [["Fecha", "QQQ Close"], ...last5];
}

function MKT_QQQ_LAST_5_CLOSES_TEXT() {
  const data = MKT_QQQ_LAST_5_CLOSES();

  if (!data || data.length <= 1) return "ERR QQQ";

  const closes = data
    .slice(1)
    .map(row => row[1]);

  return "QQQ 5d: " + closes.join(" -> ");
}

function MKT_QQQ_DIP_FROM_RECENT_HIGH_() {
  const cache = CacheService.getScriptCache();
  const cacheKey = "MKT_QQQ_DIP_FROM_6M_HIGH";
  const cached = cache.get(cacheKey);

  if (cached !== null) {
    return cached;
  }

  const url =
    "https://query1.finance.yahoo.com/v8/finance/chart/QQQ" +
    "?range=6mo&interval=1d";
  const res = UrlFetchApp.fetch(url, {
    muteHttpExceptions: true,
    headers: {
      "User-Agent": "Mozilla/5.0"
    }
  });

  if (res.getResponseCode() !== 200) {
    Logger.log("QQQ dip error: HTTP " + res.getResponseCode());
    return null;
  }

  const json = JSON.parse(res.getContentText());
  const result = json?.chart?.result?.[0];

  if (!result) {
    Logger.log("QQQ dip error: no chart result");
    return null;
  }

  const highs = (result.indicators?.quote?.[0]?.high || [])
    .filter(value => value !== null && value !== undefined)
    .map(Number)
    .filter(Number.isFinite);
  const current = Number(result.meta?.regularMarketPrice);

  if (!Number.isFinite(current) || current <= 0 || highs.length === 0) {
    Logger.log("QQQ dip error: invalid current/high data");
    return null;
  }

  const recentHigh = Math.max(...highs);
  const dipPct = Math.min(0, ((current / recentHigh) - 1) * 100);
  const formattedDip = dipPct.toFixed(1).replace(".", ",");
  const formattedHigh = recentHigh.toFixed(2).replace(".", ",");
  const text = `Nasdaq: ${formattedDip}% desde máximo 6m (${formattedHigh})`;

  cache.put(cacheKey, text, 60 * 5);
  return text;
}
