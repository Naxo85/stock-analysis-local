const TARGET_UPDATE_READER_URL =
  'https://reports-714254943648.europe-southwest1.run.app';

const TARGET_UPDATE_PROFILES = {
  trading: {
    label: 'trading',
    sheetName: 'Bolsa_2026',
    firstDataRow: 2,
    tickerColumn: 4, // D
    ambitiousColumn: 25, // Y
    targetColumn: 26, // Z
    notaColumn: 27, // AA
  },
  core: {
    label: 'core',
    sheetName: 'Bolsa_2026',
    firstDataRow: 2,
    tickerColumn: 33, // AG
    ambitiousColumn: 54, // BB
    targetColumn: 55, // BC
    notaColumn: 56, // BD
  },
};

function updateAnalysisTargetsAndNotes() {
  updateTradingTargetsAndNotes();
}

function updateTradingTargetsAndNotes() {
  updateTargetsAndNotesForProfile_('trading');
}

function updateCoreTargetsAndNotes() {
  updateTargetsAndNotesForProfile_('core');
}

function updateTargetsAndNotesForProfile_(profileName) {
  const profile = targetUpdateProfile_(profileName);
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const sh = ss.getSheetByName(profile.sheetName);

  if (!sh) {
    throw new Error(`No existe la hoja ${profile.sheetName}`);
  }

  const lastRow = sh.getLastRow();

  if (lastRow < profile.firstDataRow) {
    return;
  }

  const numRows = lastRow - profile.firstDataRow + 1;
  const tickers = sh
    .getRange(profile.firstDataRow, profile.tickerColumn, numRows, 1)
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

  const ambitiousValues = Array.from({ length: numRows }, () => ['']);
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
        Logger.log(`ERROR ${profile.label} ${ticker}: HTTP ${code}`);
        return;
      }

      const json = JSON.parse(response.getContentText());
      const markdown = json.analysis_markdown || '';

      if (!markdown) {
        Logger.log(`${profile.label} ${ticker}: analysis_markdown vacío.`);
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

      let ambitiousTarget = '';
      let target = '';

      if (score !== null) {
        if (score >= 6 && ambitiousRange) {
          ambitiousTarget = targetUpdateFormatRange_(ambitiousRange);
        }

        if (score >= 7 && entryRange) {
          target = targetUpdateFormatRange_(entryRange);
        }
      }

      ambitiousValues[rowIndex][0] = ambitiousTarget;
      targetValues[rowIndex][0] = target;

      Logger.log(
        `${profile.label} ${ticker}: nota=${score}, ` +
          `ambitious=${ambitiousTarget}, target=${target}, ` +
          `entry=${JSON.stringify(entryRange)}, ` +
          `ambitious=${JSON.stringify(ambitiousRange)}`
      );
    } catch (error) {
      Logger.log(`ERROR parseando ${profile.label} ${ticker}: ${error}`);
    }
  });

  sh.getRange(profile.firstDataRow, profile.ambitiousColumn, numRows, 1).setValues(
    ambitiousValues
  );
  sh.getRange(profile.firstDataRow, profile.targetColumn, numRows, 1).setValues(
    targetValues
  );
  sh.getRange(profile.firstDataRow, profile.notaColumn, numRows, 1)
    .setRichTextValues(notaRichValues);
  sh.getRange(profile.firstDataRow, profile.ambitiousColumn, numRows, 1)
    .setNumberFormat('@');
  sh.getRange(profile.firstDataRow, profile.targetColumn, numRows, 1)
    .setNumberFormat('@');

  SpreadsheetApp.getActiveSpreadsheet().toast(
    `Actualizados target y nota ${profile.label} para ${validRequests.length} tickers`,
    'Análisis IA',
    5
  );
}

function targetUpdateProfile_(profileName) {
  const profile = TARGET_UPDATE_PROFILES[profileName];

  if (!profile) {
    throw new Error(`Unknown target update profile: ${profileName}`);
  }

  return profile;
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
    const numRe = /[$€]?\s*([0-9][0-9.,]*)/g;
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

  const text = String(value).trim();
  let normalized = text;

  if (text.includes(',') && text.includes('.')) {
    const lastComma = text.lastIndexOf(',');
    const lastDot = text.lastIndexOf('.');

    if (lastComma > lastDot) {
      normalized = text.replace(/\./g, '').replace(',', '.');
    } else {
      normalized = text.replace(/,/g, '');
    }
  } else if (/^\d{1,3}(,\d{3})+$/.test(text)) {
    normalized = text.replace(/,/g, '');
  } else if (/^\d{1,3}(\.\d{3})+$/.test(text)) {
    normalized = text.replace(/\./g, '');
  } else {
    normalized = text.replace(',', '.');
  }

  const numberValue = Number(normalized);

  return Number.isFinite(numberValue) ? numberValue : null;
}

function targetUpdateFormatScore_(score) {
  return Number(score).toFixed(1).replace('.', ',');
}

function targetUpdateFormatRange_(range) {
  const lower = targetUpdateFormatPrice_(range.lower);
  const upper = targetUpdateFormatPrice_(range.upper);

  return `${lower}-${upper}`;
}

function targetUpdateFormatPrice_(value) {
  return Number(value).toFixed(1).replace('.', ',');
}
