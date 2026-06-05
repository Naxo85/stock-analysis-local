const TARGET_UPDATE_SHEET_NAME = 'Bolsa_2026';
const TARGET_UPDATE_READER_URL =
  'https://reports-714254943648.europe-southwest1.run.app';

const TARGET_UPDATE_HEADER_ROW = 1;
const TARGET_UPDATE_FIRST_DATA_ROW = 2;

const TARGET_UPDATE_FALLBACK_TICKER_COL = 4; // D
const TARGET_UPDATE_FALLBACK_TARGET_COL = 26; // Z
const TARGET_UPDATE_FALLBACK_NOTA_COL = 27; // AA

/**
 * Actualiza columna target y Nota desde latest.json/latest.md del bucket,
 * usando el reader endpoint.
 */
function updateAnalysisTargetsAndNotes() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const sh = ss.getSheetByName(TARGET_UPDATE_SHEET_NAME);

  if (!sh) {
    throw new Error(`No existe la hoja ${TARGET_UPDATE_SHEET_NAME}`);
  }

  const tickerCol = targetUpdateColByHeader_(
    sh,
    'Ticker',
    TARGET_UPDATE_FALLBACK_TICKER_COL
  );
  const targetCol = targetUpdateColByHeader_(
    sh,
    'target',
    TARGET_UPDATE_FALLBACK_TARGET_COL
  );
  const notaCol = targetUpdateColByHeader_(
    sh,
    'Nota',
    TARGET_UPDATE_FALLBACK_NOTA_COL
  );

  const lastRow = sh.getLastRow();

  if (lastRow < TARGET_UPDATE_FIRST_DATA_ROW) {
    return;
  }

  const numRows = lastRow - TARGET_UPDATE_FIRST_DATA_ROW + 1;
  const tickers = sh
    .getRange(TARGET_UPDATE_FIRST_DATA_ROW, tickerCol, numRows, 1)
    .getValues()
    .map((row) => String(row[0] || '').trim().toUpperCase());

  const validRequests = [];
  const rowMap = [];

  tickers.forEach((ticker, index) => {
    if (!ticker) {
      return;
    }

    validRequests.push({
      url: `${TARGET_UPDATE_READER_URL}?symbol=${encodeURIComponent(ticker)}`,
      method: 'get',
      muteHttpExceptions: true,
    });
    rowMap.push(index);
  });

  const targetValues = Array.from({ length: numRows }, () => ['']);
  const notaRichValues = Array.from({ length: numRows }, () => [
    SpreadsheetApp.newRichTextValue().setText('').build(),
  ]);

  if (validRequests.length === 0) {
    return;
  }

  const responses = UrlFetchApp.fetchAll(validRequests);

  responses.forEach((response, index) => {
    const rowIndex = rowMap[index];
    const ticker = tickers[rowIndex];

    try {
      const code = response.getResponseCode();

      if (code !== 200) {
        Logger.log(`ERROR ${ticker}: HTTP ${code} - ${response.getContentText()}`);
        return;
      }

      const json = JSON.parse(response.getContentText());
      const markdown = json.analysis_markdown || '';

      if (!markdown) {
        Logger.log(`${ticker}: analysis_markdown vacío. Borro target/nota.`);
        return;
      }

      const score = targetUpdateExtractScore_(markdown);
      const entryRange = targetUpdateExtractRange_(markdown, 'Entrada');
      const ambitiousRange = targetUpdateExtractRange_(
        markdown,
        'Entrada ambiciosa'
      );

      if (score !== null) {
        const scoreText = targetUpdateFormatScore_(score);
        const markdownUrl =
          `${TARGET_UPDATE_READER_URL}?symbol=${encodeURIComponent(ticker)}` +
          '&format=md';

        notaRichValues[rowIndex][0] = SpreadsheetApp.newRichTextValue()
          .setText(scoreText)
          .setLinkUrl(markdownUrl)
          .build();
      }

      let target = '';

      if (score !== null) {
        if (score >= 7 && entryRange) {
          target = entryRange.upper;
        } else if (score >= 6.5 && score < 7 && ambitiousRange) {
          target = ambitiousRange.upper;
        } else if (score >= 6 && score < 6.5 && ambitiousRange) {
          target = ambitiousRange.lower;
        }
      }

      targetValues[rowIndex][0] = target;

      Logger.log(
        `${ticker}: nota=${score}, target=${target}, ` +
          `entry=${JSON.stringify(entryRange)}, ` +
          `ambitious=${JSON.stringify(ambitiousRange)}`
      );
    } catch (error) {
      Logger.log(`ERROR parseando ${ticker}: ${error}`);
    }
  });

  sh.getRange(
    TARGET_UPDATE_FIRST_DATA_ROW,
    targetCol,
    numRows,
    1
  ).setValues(targetValues);
  sh.getRange(
    TARGET_UPDATE_FIRST_DATA_ROW,
    notaCol,
    numRows,
    1
  ).setRichTextValues(notaRichValues);
  sh.getRange(
    TARGET_UPDATE_FIRST_DATA_ROW,
    targetCol,
    numRows,
    1
  ).setNumberFormat('0.00');

  SpreadsheetApp.getActiveSpreadsheet().toast(
    `Actualizados target y nota para ${validRequests.length} tickers`,
    'Análisis IA',
    5
  );
}

function targetUpdateExtractScore_(markdown) {
  const lines = String(markdown || '').split(/\r?\n/);

  for (const rawLine of lines) {
    let line = String(rawLine || '').trim();
    line = line.replace(/^[-*•]\s+/, '').trim();
    line = line.replace(/\*\*/g, '').replace(/\*/g, '').trim();

    const match = line.match(
      /Valoraci[oó]n:\s*([0-9]+(?:[.,][0-9]+)?)\s*\/\s*10/i
    );

    if (match) {
      return targetUpdateToNumber_(match[1]);
    }
  }

  return null;
}

function targetUpdateExtractRange_(markdown, label) {
  const escapedLabel = label.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const lines = String(markdown || '').split(/\r?\n/);

  for (const rawLine of lines) {
    let line = String(rawLine || '').trim();
    line = line.replace(/^[-*•]\s+/, '').trim();
    line = line.replace(/\*\*/g, '').trim();

    const match = line.match(new RegExp(`^${escapedLabel}\\s*:\\s*(.+)$`, 'i'));

    if (!match) {
      continue;
    }

    const valuePart = String(match[1] || '').split('(')[0];
    const nums = [];
    const numRe = /[$€]?\s*([0-9]+(?:[.,][0-9]+)?)/g;
    let numMatch;

    while ((numMatch = numRe.exec(valuePart)) !== null) {
      const value = targetUpdateToNumber_(numMatch[1]);

      if (value !== null) {
        nums.push(value);
      }
    }

    if (nums.length === 0) {
      return null;
    }

    if (nums.length === 1) {
      return {
        lower: nums[0],
        upper: nums[0],
      };
    }

    return {
      lower: Math.min(nums[0], nums[1]),
      upper: Math.max(nums[0], nums[1]),
    };
  }

  return null;
}

function targetUpdateToNumber_(value) {
  if (value === null || value === undefined) {
    return null;
  }

  const normalized = String(value).trim().replace(',', '.');
  const numberValue = Number(normalized);

  return Number.isFinite(numberValue) ? numberValue : null;
}

function targetUpdateFormatScore_(score) {
  return Number(score).toFixed(1).replace('.', ',');
}

function targetUpdateColByHeader_(sheet, headerName, fallbackCol) {
  const lastColumn = sheet.getLastColumn();
  const headers = sheet
    .getRange(TARGET_UPDATE_HEADER_ROW, 1, 1, lastColumn)
    .getValues()[0]
    .map((header) => String(header || '').trim().toLowerCase());
  const target = String(headerName || '').trim().toLowerCase();
  const index = headers.indexOf(target);

  return index >= 0 ? index + 1 : fallbackCol;
}
