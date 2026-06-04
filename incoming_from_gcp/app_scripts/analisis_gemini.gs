const SHEET_NAME = 'Bolsa_2026';

const REPORT_READER_URL = 'https://reports-714254943648.europe-southwest1.run.app';
const ANALYZE_BATCH_URL = 'https://stock-analyze-batch-714254943648.europe-southwest1.run.app';

const HEADER_ROW = 1;
const FIRST_DATA_ROW = 2;

const FALLBACK_TICKER_COL = 4; // D
const FALLBACK_TARGET_COL = 26; // Z
const FALLBACK_NOTA_COL = 27; // AA

// Si vuelve a dar timeout, baja esto a 3.
const CLOUD_BATCH_CHUNK_SIZE = 5;

const CLOUD_BATCH_CURSOR_KEY = 'AI_CLOUD_BATCH_CURSOR_INDEX';
const CLOUD_BATCH_TICKERS_KEY = 'AI_CLOUD_BATCH_TICKERS_JSON';


function onOpen() {
  SpreadsheetApp.getUi()
    .createMenu('Análisis IA')
    .addItem('Generar análisis por bloques', 'startCloudRunBatchChunks')
    .addItem('Continuar análisis por bloques', 'continueCloudRunBatchChunks')
    .addItem('Reset batch por bloques', 'resetCloudRunBatchChunks')
    .addSeparator()
    .addItem('Actualizar target y nota', 'updateAnalysisTargetsAndNotes')
    .addToUi();
}


/**
 * Inicia un batch nuevo desde cero.
 * Lee tickers de Bolsa_2026, guarda cursor y lanza el primer bloque.
 */
function startCloudRunBatchChunks() {
  resetCloudRunBatchChunks();

  const tickers = _getSheetTickers_();

  if (tickers.length === 0) {
    Logger.log('No hay tickers válidos.');
    SpreadsheetApp.getActiveSpreadsheet().toast('No hay tickers válidos.', 'Análisis IA', 5);
    return;
  }

  const props = PropertiesService.getScriptProperties();

  props.setProperty(CLOUD_BATCH_TICKERS_KEY, JSON.stringify(tickers));
  props.setProperty(CLOUD_BATCH_CURSOR_KEY, '0');

  Logger.log(`Batch iniciado con ${tickers.length} tickers: ${tickers.join(', ')}`);

  SpreadsheetApp.getActiveSpreadsheet().toast(
    `Batch iniciado: ${tickers.length} tickers`,
    'Análisis IA',
    5
  );

  continueCloudRunBatchChunks();
}


/**
 * Continúa el batch pendiente.
 * Procesa CLOUD_BATCH_CHUNK_SIZE tickers y programa automáticamente el siguiente bloque.
 * Al terminar todos, actualiza target y nota.
 */
function continueCloudRunBatchChunks() {
  const props = PropertiesService.getScriptProperties();

  const tickersJson = props.getProperty(CLOUD_BATCH_TICKERS_KEY);

  if (!tickersJson) {
    Logger.log('No hay batch pendiente.');
    SpreadsheetApp.getActiveSpreadsheet().toast('No hay batch pendiente.', 'Análisis IA', 5);
    return;
  }

  const tickers = JSON.parse(tickersJson);

  let cursor = Number(props.getProperty(CLOUD_BATCH_CURSOR_KEY) || '0');

  if (!Number.isFinite(cursor) || cursor < 0) {
    cursor = 0;
  }

  if (cursor >= tickers.length) {
    Logger.log('Batch ya completado.');
    resetCloudRunBatchChunks();

    SpreadsheetApp.getActiveSpreadsheet().toast(
      'Batch completado. Actualizando target y nota...',
      'Análisis IA',
      8
    );

    Utilities.sleep(5000);
    updateAnalysisTargetsAndNotes();

    SpreadsheetApp.getActiveSpreadsheet().toast(
      'Batch completado y hoja actualizada.',
      'Análisis IA',
      8
    );

    return;
  }

  const chunk = tickers.slice(cursor, cursor + CLOUD_BATCH_CHUNK_SIZE);

  Logger.log(
    `Procesando bloque cursor=${cursor}, size=${chunk.length}: ${chunk.join(', ')}`
  );

  const payload = {
    tickers: chunk
  };

  const response = UrlFetchApp.fetch(ANALYZE_BATCH_URL, {
    method: 'post',
    contentType: 'application/json',
    payload: JSON.stringify(payload),
    muteHttpExceptions: true
  });

  const code = response.getResponseCode();
  const body = response.getContentText() || '';

  Logger.log(`Cloud batch chunk HTTP ${code}: ${body.substring(0, 3000)}`);

  if (code < 200 || code >= 300) {
    Logger.log(`ERROR bloque ${chunk.join(', ')}: ${body.substring(0, 3000)}`);

    SpreadsheetApp.getActiveSpreadsheet().toast(
      `Error en bloque: ${chunk.join(', ')}`,
      'Análisis IA',
      8
    );

    // No avanzamos cursor si falla.
    // Programamos otro intento.
    _scheduleNextCloudRunBatchChunk_();
    return;
  }

  cursor += chunk.length;
  props.setProperty(CLOUD_BATCH_CURSOR_KEY, String(cursor));

  Logger.log(`Bloque OK. Nuevo cursor=${cursor}/${tickers.length}`);

  SpreadsheetApp.getActiveSpreadsheet().toast(
    `Generados ${cursor}/${tickers.length}`,
    'Análisis IA',
    5
  );

  if (cursor < tickers.length) {
    _scheduleNextCloudRunBatchChunk_();
  } else {
    Logger.log('Batch completado.');
    resetCloudRunBatchChunks();

    SpreadsheetApp.getActiveSpreadsheet().toast(
      'Batch completado. Actualizando target y nota...',
      'Análisis IA',
      8
    );

    Utilities.sleep(5000);
    updateAnalysisTargetsAndNotes();

    SpreadsheetApp.getActiveSpreadsheet().toast(
      'Batch completado y hoja actualizada.',
      'Análisis IA',
      8
    );
  }
}


/**
 * Reset manual del proceso por bloques.
 */
function resetCloudRunBatchChunks() {
  const props = PropertiesService.getScriptProperties();

  props.deleteProperty(CLOUD_BATCH_CURSOR_KEY);
  props.deleteProperty(CLOUD_BATCH_TICKERS_KEY);

  _deleteTriggersForFunction_('continueCloudRunBatchChunks');

  Logger.log('Batch por bloques reseteado.');
}


/**
 * Actualiza columna target y Nota desde latest.json/latest.md del bucket,
 * usando el reader endpoint.
 */
function updateAnalysisTargetsAndNotes() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const sh = ss.getSheetByName(SHEET_NAME);

  if (!sh) {
    throw new Error(`No existe la hoja ${SHEET_NAME}`);
  }

  const tickerCol = _colByHeader(sh, 'Ticker', FALLBACK_TICKER_COL);
  const targetCol = _colByHeader(sh, 'target', FALLBACK_TARGET_COL);
  const notaCol = _colByHeader(sh, 'Nota', FALLBACK_NOTA_COL);

  const lastRow = sh.getLastRow();

  if (lastRow < FIRST_DATA_ROW) {
    return;
  }

  const numRows = lastRow - FIRST_DATA_ROW + 1;

  const tickers = sh
    .getRange(FIRST_DATA_ROW, tickerCol, numRows, 1)
    .getValues()
    .map(r => String(r[0] || '').trim().toUpperCase());

  const validRequests = [];
  const rowMap = [];

  tickers.forEach((ticker, i) => {
    if (!ticker) {
      return;
    }

    validRequests.push({
      url: `${REPORT_READER_URL}?symbol=${encodeURIComponent(ticker)}`,
      method: 'get',
      muteHttpExceptions: true
    });

    rowMap.push(i);
  });

  const targetValues = Array.from({ length: numRows }, () => ['']);
  const notaRichValues = Array.from({ length: numRows }, () => [
    SpreadsheetApp.newRichTextValue().setText('').build()
  ]);

  if (validRequests.length === 0) {
    return;
  }

  const responses = UrlFetchApp.fetchAll(validRequests);

  responses.forEach((resp, idx) => {
    const rowIndex = rowMap[idx];
    const ticker = tickers[rowIndex];

    try {
      const code = resp.getResponseCode();

      if (code !== 200) {
        Logger.log(`ERROR ${ticker}: HTTP ${code} - ${resp.getContentText()}`);
        return;
      }

      const json = JSON.parse(resp.getContentText());
      const md = json.analysis_markdown || '';

      if (!md) {
        Logger.log(`${ticker}: analysis_markdown vacío. Borro target/nota.`);
        return;
      }

      const score = _extractScore(md);
      const entryRange = _extractRange(md, 'Entrada');
      const ambitiousRange = _extractRange(md, 'Entrada ambiciosa');

      // Nota con enlace al MD
      if (score !== null) {
        const scoreText = _formatScore(score);
        const mdUrl = `${REPORT_READER_URL}?symbol=${encodeURIComponent(ticker)}&format=md`;

        notaRichValues[rowIndex][0] = SpreadsheetApp
          .newRichTextValue()
          .setText(scoreText)
          .setLinkUrl(mdUrl)
          .build();
      }

      // Target según nota
      let target = '';

      if (score !== null) {
        if (score >= 7 && entryRange) {
          // Nota alta: upper de Entrada principal
          target = entryRange.upper;

        } else if (score >= 6.5 && score < 7 && ambitiousRange) {
          // Nota media: upper de Entrada ambiciosa
          target = ambitiousRange.upper;

        } else if (score >= 6 && score < 6.5 && ambitiousRange) {
          // Nota justa: lower de Entrada ambiciosa
          target = ambitiousRange.lower;
        }
      }

      targetValues[rowIndex][0] = target;

      Logger.log(
        `${ticker}: nota=${score}, target=${target}, entry=${JSON.stringify(entryRange)}, ambitious=${JSON.stringify(ambitiousRange)}`
      );

    } catch (e) {
      Logger.log(`ERROR parseando ${ticker}: ${e}`);
    }
  });

  sh.getRange(FIRST_DATA_ROW, targetCol, numRows, 1).setValues(targetValues);
  sh.getRange(FIRST_DATA_ROW, notaCol, numRows, 1).setRichTextValues(notaRichValues);

  sh.getRange(FIRST_DATA_ROW, targetCol, numRows, 1).setNumberFormat('0.00');

  SpreadsheetApp.getActiveSpreadsheet().toast(
    `Actualizados target y nota para ${validRequests.length} tickers`,
    'Análisis IA',
    5
  );
}


/**
 * Helpers batch por bloques
 */
function _scheduleNextCloudRunBatchChunk_() {
  _deleteTriggersForFunction_('continueCloudRunBatchChunks');

  ScriptApp.newTrigger('continueCloudRunBatchChunks')
    .timeBased()
    .after(60 * 1000)
    .create();

  Logger.log('Siguiente bloque programado en ~1 minuto.');
}


function _deleteTriggersForFunction_(functionName) {
  const triggers = ScriptApp.getProjectTriggers();

  triggers.forEach(trigger => {
    if (trigger.getHandlerFunction() === functionName) {
      ScriptApp.deleteTrigger(trigger);
    }
  });
}


function _getSheetTickers_() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const sh = ss.getSheetByName(SHEET_NAME);

  if (!sh) {
    throw new Error(`No existe la hoja ${SHEET_NAME}`);
  }

  const tickerCol = _colByHeader(sh, 'Ticker', FALLBACK_TICKER_COL);
  const lastRow = sh.getLastRow();

  if (lastRow < FIRST_DATA_ROW) {
    return [];
  }

  const numRows = lastRow - FIRST_DATA_ROW + 1;

  const tickers = sh
    .getRange(FIRST_DATA_ROW, tickerCol, numRows, 1)
    .getValues()
    .map(r => String(r[0] || '').trim().toUpperCase())
    .filter(t => !!t);

  return [...new Set(tickers)];
}


/**
 * Helpers parseo markdown
 */
function _extractScore(markdown) {
  const lines = String(markdown || '').split(/\r?\n/);

  for (let rawLine of lines) {
    let line = String(rawLine || '').trim();

    line = line.replace(/^[-*•]\s+/, '').trim();
    line = line.replace(/\*\*/g, '').replace(/\*/g, '').trim();

    const re = /Valoraci[oó]n:\s*([0-9]+(?:[.,][0-9]+)?)\s*\/\s*10/i;
    const m = line.match(re);

    if (m) {
      return _toNumber(m[1]);
    }
  }

  return null;
}


function _extractRange(markdown, label) {
  const escapedLabel = label.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');

  const lines = String(markdown || '').split(/\r?\n/);

  for (let rawLine of lines) {
    let line = String(rawLine || '').trim();

    line = line.replace(/^[-*•]\s+/, '').trim();
    line = line.replace(/\*\*/g, '').trim();

    const re = new RegExp(
      `^${escapedLabel}\\s*:\\s*(.+)$`,
      'i'
    );

    const m = line.match(re);

    if (!m) {
      continue;
    }

    let valuePart = m[1] || '';

    // Quitamos porcentajes: "(-6.8% a -10.5% vs precio actual)"
    valuePart = valuePart.split('(')[0];

    const nums = [];
    const numRe = /[$€]?\s*([0-9]+(?:[.,][0-9]+)?)/g;

    let match;

    while ((match = numRe.exec(valuePart)) !== null) {
      const n = _toNumber(match[1]);

      if (n !== null) {
        nums.push(n);
      }
    }

    if (nums.length === 0) {
      return null;
    }

    if (nums.length === 1) {
      return {
        lower: nums[0],
        upper: nums[0]
      };
    }

    return {
      lower: Math.min(nums[0], nums[1]),
      upper: Math.max(nums[0], nums[1])
    };
  }

  return null;
}


function _toNumber(value) {
  if (value === null || value === undefined) {
    return null;
  }

  const normalized = String(value)
    .trim()
    .replace(',', '.');

  const n = Number(normalized);

  return Number.isFinite(n) ? n : null;
}


function _formatScore(score) {
  return Number(score).toFixed(1).replace('.', ',');
}


function _colByHeader(sh, headerName, fallbackCol) {
  const lastCol = sh.getLastColumn();

  const headers = sh
    .getRange(HEADER_ROW, 1, 1, lastCol)
    .getValues()[0]
    .map(h => String(h || '').trim().toLowerCase());

  const target = String(headerName || '').trim().toLowerCase();
  const idx = headers.indexOf(target);

  return idx >= 0 ? idx + 1 : fallbackCol;
}