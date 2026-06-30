const TARGET_UPDATE_READER_URL =
  'https://reports-714254943648.europe-southwest1.run.app';

const TARGET_UPDATE_ANALYST_UPSIDE_EXCEPTIONAL = 0.35;
const TARGET_UPDATE_ANALYST_UPSIDE_STRONG = 0.25;
const TARGET_UPDATE_ANALYST_UPSIDE_POSITIVE = 0.12;
const TARGET_UPDATE_ANALYST_DOWNSIDE_CAUTION = -0.10;
const TARGET_UPDATE_ANALYST_DOWNSIDE_BAD = -0.20;
const TARGET_UPDATE_ANALYST_BUY_SHARE_EXCEPTIONAL = 0.75;
const TARGET_UPDATE_ANALYST_BUY_SHARE_STRONG = 0.65;
const TARGET_UPDATE_ANALYST_BUY_SHARE_POSITIVE = 0.50;
const TARGET_UPDATE_ANALYST_SELL_SHARE_LOW = 0.08;
const TARGET_UPDATE_ANALYST_SELL_SHARE_OK = 0.12;
const TARGET_UPDATE_ANALYST_SELL_SHARE_MIXED = 0.20;
const TARGET_UPDATE_ANALYST_SELL_SHARE_BAD = 0.35;
const TARGET_UPDATE_ANALYST_HOLD_SHARE_NEUTRAL = 0.45;
const TARGET_UPDATE_ANALYST_NEAR_TARGET = 0.02;
const TARGET_UPDATE_ANALYST_FORMAT_MARKER = 'TARGET_UPDATE_ANALYST_AB_V1';

const TARGET_UPDATE_PROFILES = {
  trading: {
    label: 'trading',
    sheetName: 'Bolsa_2026',
    firstDataRow: 2,
    tickerColumn: 4, // D
    ambitiousColumn: 25, // Y
    targetColumn: 26, // Z
    notaColumn: 27, // AA
    analystColumn: 28, // AB
    analystHeader: 'Analistas',
    currentPriceColumn: 6, // F
    momentumColumn: 29, // AC
  },
  core: {
    label: 'core',
    sheetName: 'Bolsa_2026',
    firstDataRow: 2,
    tickerColumn: 33, // AG
    ambitiousColumn: 54, // BB
    targetColumn: 55, // BC
    notaColumn: 56, // BD
    analystColumn: 57, // BE
    analystHeader: 'Analistas',
    currentPriceColumn: 35, // AI
    momentumColumn: 58, // BF
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

function applyAnalysisSheetLayout() {
  targetUpdateApplyProfileLayout_('trading');
  targetUpdateApplyProfileLayout_('core');

  SpreadsheetApp.getActiveSpreadsheet().toast(
    'Layout de análisis aplicado',
    'Análisis IA',
    5
  );
}

function applyTradingAnalysisSheetLayout() {
  targetUpdateApplyProfileLayout_('trading');
}

function applyCoreAnalysisSheetLayout() {
  targetUpdateApplyProfileLayout_('core');
}

function updateTargetsAndNotesForProfile_(profileName) {
  const profile = targetUpdateProfile_(profileName);
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const sh = ss.getSheetByName(profile.sheetName);

  if (!sh) {
    throw new Error(`No existe la hoja ${profile.sheetName}`);
  }

  targetUpdateApplyProfileLayout_(profileName);

  const lastRow = targetUpdateLastTickerRow_(sh, profile);

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
  const analystValues = Array.from({ length: numRows }, () => ['']);
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
      const stopRange = targetUpdateExtractRange_(markdown, 'Stop de gestión');

      if (score !== null) {
        const scoreText = targetUpdateFormatScore_(score);
        const markdownUrl = targetUpdateHtmlUrl_(ticker);

        notaRichValues[rowIndex][0] = SpreadsheetApp.newRichTextValue()
          .setText(scoreText)
          .setLinkUrl(markdownUrl)
          .build();
      }

      let ambitiousTarget = '';
      let target = '';
      let stopLoss = '';
      let analystText = '';

      const momentum = targetUpdateExtractMomentumFromRow_(sh, rowIndex, profile);
      const currentPrice = targetUpdateExtractCurrentPriceFromRow_(
        sh,
        rowIndex,
        profile
      );

      if (ambitiousRange) {
        ambitiousTarget = targetUpdateFormatRange_(ambitiousRange);
      }

      if (stopRange) {
        stopLoss = targetUpdateFormatStop_(stopRange, currentPrice);
      }

      analystText = targetUpdateFormatAnalystSummary_(
        json.analyst_ratings_summary
      );

      if (targetUpdateShouldShowNormalEntry_(score, momentum) && entryRange) {
        target = targetUpdateFormatRange_(entryRange);
      }

      ambitiousValues[rowIndex][0] = ambitiousTarget;
      targetValues[rowIndex][0] = target;
      if (profile.analystColumn) {
        analystValues[rowIndex][0] = analystText;
      }

      Logger.log(
        `${profile.label} ${ticker}: nota=${score}, momentum=${momentum}, ` +
          `ambitious=${ambitiousTarget}, target=${target}, stop=${stopLoss}, ` +
          `analysts=${analystText}, ` +
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
  if (profile.analystColumn) {
    sh.getRange(profile.firstDataRow, profile.analystColumn, numRows, 1).setValues(
      analystValues
    );
  }
  sh.getRange(profile.firstDataRow, profile.notaColumn, numRows, 1)
    .setRichTextValues(notaRichValues);
  sh.getRange(profile.firstDataRow, profile.ambitiousColumn, numRows, 1)
    .setNumberFormat('@');
  sh.getRange(profile.firstDataRow, profile.targetColumn, numRows, 1)
    .setNumberFormat('@');
  if (profile.analystColumn) {
    sh.getRange(profile.firstDataRow, profile.analystColumn, numRows, 1)
      .setNumberFormat('@');
  }

  const updateDate = Utilities.formatDate(
    new Date(),
    Session.getScriptTimeZone(),
    'dd/MM/yyyy'
  );

  const updateCell = profileName === 'trading' ? 'AD5' : 'AD6';
  const updateLabel = profileName === 'trading' ? 'Trading' : 'Core';

  sh.getRange(updateCell)
    .setValue(`${updateLabel}: ${updateDate}`)
    .setNumberFormat('@')
    .setNote(`Última actualización completa de ${updateLabel}`);

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

function targetUpdateApplyProfileLayout_(profileName) {
  const profile = targetUpdateProfile_(profileName);
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const sh = ss.getSheetByName(profile.sheetName);

  if (!sh) {
    throw new Error(`No existe la hoja ${profile.sheetName}`);
  }

  if (profile.analystColumn && profile.analystHeader) {
    sh.getRange(1, profile.analystColumn)
      .setValue(profile.analystHeader)
      .setFontWeight('bold')
      .setHorizontalAlignment('center')
      .setNote(
        'Resumen de consenso de analistas desde latest.json. Formato: PT mediano | Buy-Hold-Sell.'
      );
  }

  targetUpdateApplyAnalystConditionalFormats_(sh, profile);
}

function targetUpdateApplyAnalystConditionalFormats_(sh, profile) {
  if (!profile.analystColumn) {
    return;
  }

  const lastDataRow = targetUpdateLastTickerRow_(sh, profile);

  if (lastDataRow < profile.firstDataRow) {
    return;
  }

  const rowCount = lastDataRow - profile.firstDataRow + 1;
  const analystRange = sh.getRange(
    profile.firstDataRow,
    profile.analystColumn,
    rowCount,
    1
  );
  const rulesToAdd = targetUpdateBuildAnalystRules_(
    analystRange,
    profile,
    profile.firstDataRow
  );
  const ownedFormulas = rulesToAdd.map((rule) =>
    rule.getBooleanCondition().getCriteriaValues()[0]
  );
  const existingRules = sh.getConditionalFormatRules();
  const keptRules = existingRules.filter(
    (rule) =>
      !targetUpdateIsOwnedConditionalRule_(
        rule,
        ownedFormulas,
        targetUpdateColumnLetter_(profile.analystColumn),
        profile.analystColumn,
        profile.firstDataRow
      )
  );

  sh.setConditionalFormatRules(keptRules.concat(rulesToAdd));
}

function targetUpdateBuildAnalystRules_(range, profile, firstRow) {
  const analystCol = targetUpdateColumnLetter_(profile.analystColumn);
  const analystRef = `$${analystCol}${firstRow}`;
  const priceCol = targetUpdateColumnLetter_(profile.currentPriceColumn);
  const priceRef = `$${priceCol}${firstRow}`;
  const hasSummaryExpr = `REGEXMATCH(${analystRef};"^[-0-9.,]+ \\| [0-9]+-[0-9]+-[0-9]+$")`;
  const targetExpr = `VALUE(LEFT(${analystRef};FIND("|";${analystRef})-2))`;
  const upsideExpr = `(${targetExpr}/VALUE(${priceRef})-1)`;
  const buyExpr = `VALUE(REGEXEXTRACT(${analystRef};"\\| ([0-9]+)-"))`;
  const holdExpr = `VALUE(REGEXEXTRACT(${analystRef};"\\| [0-9]+-([0-9]+)-"))`;
  const sellExpr = `VALUE(REGEXEXTRACT(${analystRef};"-([0-9]+)$"))`;
  const totalExpr = `(${buyExpr}+${holdExpr}+${sellExpr})`;
  const buyShareExpr = `(${buyExpr}/${totalExpr})`;
  const holdShareExpr = `(${holdExpr}/${totalExpr})`;
  const sellShareExpr = `(${sellExpr}/${totalExpr})`;
  const markerExpr = `N("${TARGET_UPDATE_ANALYST_FORMAT_MARKER}")=0`;
  const lowSellExpr = `${sellShareExpr}<=${targetUpdateFormatFormulaNumber_(TARGET_UPDATE_ANALYST_SELL_SHARE_LOW)}`;
  const okSellExpr = `${sellShareExpr}<=${targetUpdateFormatFormulaNumber_(TARGET_UPDATE_ANALYST_SELL_SHARE_OK)}`;
  const notMixedSellExpr = `${sellShareExpr}<${targetUpdateFormatFormulaNumber_(TARGET_UPDATE_ANALYST_SELL_SHARE_MIXED)}`;
  const baseExpr = `${markerExpr};${analystRef}<>"";${priceRef}<>"";${hasSummaryExpr};${totalExpr}>0`;
  const nearTargetExpr = `VALUE(${priceRef})>=${targetExpr}*(1-${targetUpdateFormatFormulaNumber_(TARGET_UPDATE_ANALYST_NEAR_TARGET)})`;
  const notNearTargetExpr = `NOT(${nearTargetExpr})`;
  const redExpr = `OR(${upsideExpr}<=${targetUpdateFormatFormulaNumber_(TARGET_UPDATE_ANALYST_DOWNSIDE_BAD)};${sellShareExpr}>=${targetUpdateFormatFormulaNumber_(TARGET_UPDATE_ANALYST_SELL_SHARE_BAD)})`;
  const orangeExpr = `OR(AND(${upsideExpr}>${targetUpdateFormatFormulaNumber_(TARGET_UPDATE_ANALYST_DOWNSIDE_BAD)};${upsideExpr}<=${targetUpdateFormatFormulaNumber_(TARGET_UPDATE_ANALYST_DOWNSIDE_CAUTION)});AND(${sellShareExpr}>=${targetUpdateFormatFormulaNumber_(TARGET_UPDATE_ANALYST_SELL_SHARE_MIXED)};${sellShareExpr}<${targetUpdateFormatFormulaNumber_(TARGET_UPDATE_ANALYST_SELL_SHARE_BAD)}))`;
  const yellowExpr = `${upsideExpr}>${targetUpdateFormatFormulaNumber_(TARGET_UPDATE_ANALYST_DOWNSIDE_CAUTION)};${sellShareExpr}<${targetUpdateFormatFormulaNumber_(TARGET_UPDATE_ANALYST_SELL_SHARE_MIXED)};OR(${holdShareExpr}>=${targetUpdateFormatFormulaNumber_(TARGET_UPDATE_ANALYST_HOLD_SHARE_NEUTRAL)};ABS(${upsideExpr})<${targetUpdateFormatFormulaNumber_(TARGET_UPDATE_ANALYST_UPSIDE_POSITIVE)})`;

  const buildRule = (formula, background, bold) => {
    const builder = SpreadsheetApp.newConditionalFormatRule()
      .whenFormulaSatisfied(formula)
      .setBackground(background)
      .setRanges([range]);

    if (bold) {
      builder.setBold(true);
    }

    return builder.build();
  };

  return [
    buildRule(`=AND(${baseExpr};${nearTargetExpr};${redExpr})`, '#e06666', true),
    buildRule(`=AND(${baseExpr};${notNearTargetExpr};${redExpr})`, '#e06666', false),
    buildRule(`=AND(${baseExpr};${nearTargetExpr};${orangeExpr})`, '#f9cb9c', true),
    buildRule(`=AND(${baseExpr};${notNearTargetExpr};${orangeExpr})`, '#f9cb9c', false),
    buildRule(
      `=AND(${baseExpr};${buyShareExpr}>=${targetUpdateFormatFormulaNumber_(TARGET_UPDATE_ANALYST_BUY_SHARE_EXCEPTIONAL)};${lowSellExpr};${upsideExpr}>=${targetUpdateFormatFormulaNumber_(TARGET_UPDATE_ANALYST_UPSIDE_EXCEPTIONAL)})`,
      '#39ff14',
      false
    ),
    buildRule(
      `=AND(${baseExpr};${buyShareExpr}>=${targetUpdateFormatFormulaNumber_(TARGET_UPDATE_ANALYST_BUY_SHARE_STRONG)};${okSellExpr};${upsideExpr}>=${targetUpdateFormatFormulaNumber_(TARGET_UPDATE_ANALYST_UPSIDE_STRONG)};${upsideExpr}<${targetUpdateFormatFormulaNumber_(TARGET_UPDATE_ANALYST_UPSIDE_EXCEPTIONAL)})`,
      '#93c47d',
      false
    ),
    buildRule(
      `=AND(${baseExpr};${buyShareExpr}>=${targetUpdateFormatFormulaNumber_(TARGET_UPDATE_ANALYST_BUY_SHARE_POSITIVE)};${notMixedSellExpr};${upsideExpr}>=${targetUpdateFormatFormulaNumber_(TARGET_UPDATE_ANALYST_UPSIDE_POSITIVE)};${upsideExpr}<${targetUpdateFormatFormulaNumber_(TARGET_UPDATE_ANALYST_UPSIDE_STRONG)})`,
      '#d9ead3',
      false
    ),
    buildRule(
      `=AND(${baseExpr};${upsideExpr}>=${targetUpdateFormatFormulaNumber_(TARGET_UPDATE_ANALYST_UPSIDE_STRONG)};${sellShareExpr}<${targetUpdateFormatFormulaNumber_(TARGET_UPDATE_ANALYST_SELL_SHARE_MIXED)};OR(${buyShareExpr}<${targetUpdateFormatFormulaNumber_(TARGET_UPDATE_ANALYST_BUY_SHARE_STRONG)};${sellShareExpr}>${targetUpdateFormatFormulaNumber_(TARGET_UPDATE_ANALYST_SELL_SHARE_OK)}))`,
      '#cfe2f3',
      false
    ),
    buildRule(`=AND(${baseExpr};${nearTargetExpr};${yellowExpr})`, '#fff2cc', true),
    buildRule(`=AND(${baseExpr};${notNearTargetExpr};${yellowExpr})`, '#fff2cc', false),
  ];
}

function targetUpdateIsOwnedConditionalRule_(
  rule,
  ownedFormulas,
  analystColumnLetter,
  analystColumn,
  firstRow
) {
  const condition = rule.getBooleanCondition();

  if (!condition) {
    return false;
  }

  if (
    condition.getCriteriaType() !==
    SpreadsheetApp.BooleanCriteria.CUSTOM_FORMULA
  ) {
    return false;
  }

  const formula = condition.getCriteriaValues()[0];
  if (ownedFormulas.indexOf(formula) !== -1) {
    return true;
  }

  if (String(formula || '').indexOf(TARGET_UPDATE_ANALYST_FORMAT_MARKER) !== -1) {
    return targetUpdateRuleTouchesColumn_(rule, analystColumn);
  }

  return targetUpdateLooksLikeLegacyAnalystRule_(
    formula,
    analystColumnLetter,
    firstRow
  );
}

function targetUpdateRuleTouchesColumn_(rule, column) {
  const ranges = rule.getRanges();

  return ranges.some((range) => {
    const startColumn = range.getColumn();
    const endColumn = startColumn + range.getNumColumns() - 1;

    return column >= startColumn && column <= endColumn;
  });
}

function targetUpdateLooksLikeLegacyAnalystRule_(
  formula,
  analystColumnLetter,
  firstRow
) {
  const text = String(formula || '');
  const analystRef = `$${analystColumnLetter}${firstRow}`;

  if (text.indexOf(`REGEXMATCH(${analystRef};`) === -1) {
    return false;
  }

  return (
    text.indexOf('[1-9][0-9]*S') !== -1 ||
    text.indexOf('\\| [1-9][0-9]*B') !== -1 ||
    text.indexOf('\\| 0B') !== -1
  );
}

function targetUpdateLastTickerRow_(sh, profile) {
  const lastSheetRow = sh.getLastRow();

  if (lastSheetRow < profile.firstDataRow) {
    return profile.firstDataRow - 1;
  }

  const values = sh
    .getRange(
      profile.firstDataRow,
      profile.tickerColumn,
      lastSheetRow - profile.firstDataRow + 1,
      1
    )
    .getValues();

  for (let i = values.length - 1; i >= 0; i--) {
    if (String(values[i][0] || '').trim()) {
      return profile.firstDataRow + i;
    }
  }

  return profile.firstDataRow - 1;
}

function targetUpdateColumnLetter_(column) {
  let value = Number(column);
  let letter = '';

  while (value > 0) {
    const remainder = (value - 1) % 26;
    letter = String.fromCharCode(65 + remainder) + letter;
    value = Math.floor((value - 1) / 26);
  }

  return letter;
}

function targetUpdateFormatFormulaNumber_(value) {
  return String(value).replace('.', ',');
}

function targetUpdateShouldShowNormalEntry_(score, momentum) {
  if (score >= 7.5) return true;
  if (momentum === null) return false;
  if (score !== null && score >= 7.0 && momentum >= 4.5) return true;
  if (score !== null && score >= 6.5 && momentum >= 6.0) return true;
  if (score !== null && score >= 6.0 && momentum >= 7.5) return true;
  return momentum >= 8.5;
}

function targetUpdateExtractMomentumFromRow_(sh, rowIndex, profile) {
  if (!profile.momentumColumn) {
    return null;
  }

  const row = profile.firstDataRow + rowIndex;
  const value = sh.getRange(row, profile.momentumColumn).getValue();

  return targetUpdateExtractMomentumScore_(value);
}

function targetUpdateExtractCurrentPriceFromRow_(sh, rowIndex, profile) {
  if (!profile.currentPriceColumn) {
    return null;
  }

  const row = profile.firstDataRow + rowIndex;
  const value = sh.getRange(row, profile.currentPriceColumn).getValue();

  return targetUpdateToNumber_(value);
}

function targetUpdateExtractMomentumScore_(value) {
  if (value === null || value === undefined || value === '') {
    return null;
  }

  const text = String(value).trim();
  const match = text.match(/([0-9]+(?:[.,][0-9]+)?)/);

  if (!match) {
    return null;
  }

  return targetUpdateToNumber_(match[1]);
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

function targetUpdateFormatRangeOrPrice_(range) {
  if (Number(range.lower) === Number(range.upper)) {
    return targetUpdateFormatPrice_(range.lower);
  }

  return targetUpdateFormatRange_(range);
}

function targetUpdateFormatStop_(range, currentPrice) {
  const stopText = targetUpdateFormatRangeOrPrice_(range);

  if (currentPrice === null || !isFinite(currentPrice) || currentPrice <= 0) {
    return stopText;
  }

  if (Number(range.lower) === Number(range.upper)) {
    return `${stopText} (${targetUpdateFormatDistancePct_(range.lower, currentPrice)})`;
  }

  const lowerPct = targetUpdateFormatDistancePct_(range.lower, currentPrice);
  const upperPct = targetUpdateFormatDistancePct_(range.upper, currentPrice);

  return `${stopText} (${lowerPct} a ${upperPct})`;
}

function targetUpdateFormatAnalystSummary_(summary) {
  if (!summary || summary.status !== 'ok') {
    return '';
  }

  const quality = String(summary.quality || '');
  if (!quality || quality === 'none') {
    return '';
  }

  const ratingCounts = summary.rating_counts || {};
  const buy = targetUpdateIntegerOrZero_(ratingCounts.buy);
  const hold = targetUpdateIntegerOrZero_(ratingCounts.hold);
  const sell = targetUpdateIntegerOrZero_(ratingCounts.sell);
  const targetMedian = targetUpdateToNumber_(summary.target_median);
  const parts = [];

  if (targetMedian !== null) {
    parts.push(targetUpdateFormatPrice_(targetMedian));
  }

  parts.push(`${buy}-${hold}-${sell}`);

  return parts.join(' | ');
}

function targetUpdateIntegerOrZero_(value) {
  const parsed = targetUpdateIntegerOrNull_(value);
  return parsed === null ? 0 : parsed;
}

function targetUpdateIntegerOrNull_(value) {
  const numberValue = targetUpdateToNumber_(value);

  if (numberValue === null || !Number.isFinite(numberValue)) {
    return null;
  }

  return Math.round(numberValue);
}

function targetUpdateFormatDistancePct_(level, currentPrice) {
  const pct = (Number(level) / Number(currentPrice) - 1) * 100;
  const sign = pct > 0 ? '+' : '';

  return `${sign}${pct.toFixed(1).replace('.', ',')}%`;
}

function targetUpdateFormatPrice_(value) {
  return Number(value).toFixed(1).replace('.', ',');
}

function updateTradingTargetAndNoteForRow(row) {
  updateTargetAndNoteForRow_('trading', row);
}

function updateCoreTargetAndNoteForRow(row) {
  updateTargetAndNoteForRow_('core', row);
}

function updateTargetAndNoteForRow_(profileName, row) {
  const profile = targetUpdateProfile_(profileName);
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const sh = ss.getSheetByName(profile.sheetName);

  if (!sh) {
    throw new Error(`No existe la hoja ${profile.sheetName}`);
  }

  if (row < profile.firstDataRow) {
    return;
  }

  const ticker = String(sh.getRange(row, profile.tickerColumn).getValue() || '')
    .trim()
    .toUpperCase();

  if (!ticker) {
    sh.getRange(row, profile.ambitiousColumn).clearContent();
    sh.getRange(row, profile.targetColumn).clearContent();
    if (profile.analystColumn) {
      sh.getRange(row, profile.analystColumn).clearContent();
    }
    sh.getRange(row, profile.notaColumn).clearContent();
    return;
  }

  const response = UrlFetchApp.fetch(
    `${TARGET_UPDATE_READER_URL}?symbol=${encodeURIComponent(ticker)}`,
    {
      method: 'get',
      muteHttpExceptions: true,
    }
  );

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
  const stopRange = targetUpdateExtractRange_(markdown, 'Stop de gestión');
  const rowIndex = row - profile.firstDataRow;
  const momentum = targetUpdateExtractMomentumFromRow_(sh, rowIndex, profile);
  const currentPrice = targetUpdateExtractCurrentPriceFromRow_(
    sh,
    rowIndex,
    profile
  );

  let ambitiousTarget = '';
  let target = '';
  let stopLoss = '';
  let analystText = '';

  if (ambitiousRange) {
    ambitiousTarget = targetUpdateFormatRange_(ambitiousRange);
  }

  if (stopRange) {
    stopLoss = targetUpdateFormatStop_(stopRange, currentPrice);
  }

  analystText = targetUpdateFormatAnalystSummary_(
    json.analyst_ratings_summary
  );

  if (targetUpdateShouldShowNormalEntry_(score, momentum) && entryRange) {
    target = targetUpdateFormatRange_(entryRange);
  }

  sh.getRange(row, profile.ambitiousColumn)
    .setNumberFormat('@')
    .setValue(ambitiousTarget);

  sh.getRange(row, profile.targetColumn)
    .setNumberFormat('@')
    .setValue(target);

  if (profile.analystColumn) {
    sh.getRange(row, profile.analystColumn)
      .setNumberFormat('@')
      .setValue(analystText);
  }

  if (score !== null) {
    const scoreText = targetUpdateFormatScore_(score);
    const markdownUrl = targetUpdateHtmlUrl_(ticker);

    const richValue = SpreadsheetApp.newRichTextValue()
      .setText(scoreText)
      .setLinkUrl(markdownUrl)
      .build();

    sh.getRange(row, profile.notaColumn).setRichTextValue(richValue);
  } else {
    sh.getRange(row, profile.notaColumn).clearContent();
  }

  Logger.log(
    `${profile.label} row=${row} ${ticker}: nota=${score}, momentum=${momentum}, ` +
      `ambitious=${ambitiousTarget}, target=${target}, stop=${stopLoss}, ` +
      `analysts=${analystText}`
  );
}

function _momentumDecisionBucket_(momentum) {
  if (momentum === null || momentum === '' || !isFinite(momentum)) return 'none';
  if (momentum < 3.5) return 'lt_3_5';
  if (momentum < 4.0) return 'gte_3_5_lt_4_0';
  if (momentum < 6.5) return 'gte_4_0_lt_6_5';
  return 'gte_6_5';
}

function targetUpdateHtmlUrl_(ticker) {
  return (
    'https://storage.cloud.google.com/' +
    'stock-analysis-reports-naxo85/' +
    `${encodeURIComponent(ticker)}/latest.html`
  );
}
