const MKT_MAJOR_MACRO_SHEET_NAME = 'Bolsa_2026';
const MKT_MAJOR_MACRO_RANGE_A1 = 'AD27:AD40';

const MKT_MAJOR_MACRO_EVENTS = [
  {
    date: '2026-07-02',
    timeUtc: '12:30',
    title: 'Empleo US: NFP, paro y salarios',
    tier: 'alto',
  },
  {
    date: '2026-07-14',
    timeUtc: '12:30',
    title: 'Inflación US: CPI y Core CPI',
    tier: 'alto',
  },
  {
    date: '2026-07-29',
    timeUtc: '18:00',
    title: 'Fed: decisión FOMC',
    tier: 'alto',
  },
  {
    date: '2026-07-29',
    timeUtc: '18:30',
    title: 'Fed: rueda de prensa',
    tier: 'alto',
  },
  {
    date: '2026-07-31',
    timeUtc: '12:30',
    title: 'Inflación Fed: PCE/Core PCE',
    tier: 'alto',
  },
  {
    date: '2026-08-07',
    timeUtc: '12:30',
    title: 'Empleo US: NFP, paro y salarios',
    tier: 'alto',
  },
  {
    date: '2026-08-28',
    timeUtc: '12:30',
    title: 'Inflación Fed: PCE/Core PCE',
    tier: 'alto',
  },
  {
    date: '2026-09-04',
    timeUtc: '12:30',
    title: 'Empleo US: NFP, paro y salarios',
    tier: 'alto',
  },
  {
    date: '2026-09-16',
    timeUtc: '18:00',
    title: 'Fed: decisión FOMC',
    tier: 'alto',
  },
  {
    date: '2026-09-16',
    timeUtc: '18:30',
    title: 'Fed: rueda de prensa',
    tier: 'alto',
  },
  {
    date: '2026-09-25',
    timeUtc: '12:30',
    title: 'Inflación Fed: PCE/Core PCE',
    tier: 'alto',
  },
  {
    date: '2026-10-02',
    timeUtc: '12:30',
    title: 'Empleo US: NFP, paro y salarios',
    tier: 'alto',
  },
  {
    date: '2026-10-28',
    timeUtc: '18:00',
    title: 'Fed: decisión FOMC',
    tier: 'alto',
  },
  {
    date: '2026-10-28',
    timeUtc: '18:30',
    title: 'Fed: rueda de prensa',
    tier: 'alto',
  },
  {
    date: '2026-10-30',
    timeUtc: '12:30',
    title: 'Inflación Fed: PCE/Core PCE',
    tier: 'alto',
  },
  {
    date: '2026-11-06',
    timeUtc: '13:30',
    title: 'Empleo US: NFP, paro y salarios',
    tier: 'alto',
  },
  {
    date: '2026-11-25',
    timeUtc: '13:30',
    title: 'Inflación Fed: PCE/Core PCE',
    tier: 'alto',
  },
  {
    date: '2026-12-04',
    timeUtc: '13:30',
    title: 'Empleo US: NFP, paro y salarios',
    tier: 'alto',
  },
  {
    date: '2026-12-09',
    timeUtc: '19:00',
    title: 'Fed: decisión FOMC',
    tier: 'alto',
  },
  {
    date: '2026-12-09',
    timeUtc: '19:30',
    title: 'Fed: rueda de prensa',
    tier: 'alto',
  },
  {
    date: '2026-12-23',
    timeUtc: '13:30',
    title: 'Inflación Fed: PCE/Core PCE',
    tier: 'alto',
  },
];

function MKT_UPDATE_MAJOR_MACRO_EVENTS() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const sheet = ss.getSheetByName(MKT_MAJOR_MACRO_SHEET_NAME);

  if (!sheet) {
    throw new Error(`No existe la hoja: ${MKT_MAJOR_MACRO_SHEET_NAME}`);
  }

  const tz = Session.getScriptTimeZone();
  const today = MKT_macroStartOfDay_(new Date(), tz);
  const end = new Date(today.getTime() + 7 * 24 * 60 * 60 * 1000);
  const events = MKT_MAJOR_MACRO_EVENTS
    .map((event) => MKT_macroNormalizeEvent_(event, tz))
    .filter((event) => event.when >= today && event.when <= end)
    .sort((a, b) => a.when.getTime() - b.when.getTime());

  const values = Array.from({ length: 14 }, () => ['']);
  values[0][0] = 'Macro 7d';

  if (events.length === 0) {
    values[1][0] = 'Sin macro grande';
  } else {
    events.slice(0, 12).forEach((event, index) => {
      values[index + 1][0] = MKT_macroFormatEvent_(event, tz);
    });
  }

  sheet.getRange(MKT_MAJOR_MACRO_RANGE_A1)
    .clearContent()
    .setValues(values)
    .setNumberFormat('@');

  sheet.getRange('AD27')
    .setFontWeight('bold')
    .setNote('Solo eventos macro US nivel 1: FOMC/Fed, CPI, PCE y empleo/NFP. Lista curada; no incluye ruido de calendario.');
}

function MKT_macroNormalizeEvent_(event, tz) {
  const when = new Date(`${event.date}T${event.timeUtc}:00Z`);
  return {
    date: event.date,
    title: event.title,
    tier: event.tier,
    when,
    localDate: Utilities.formatDate(when, tz, 'yyyy-MM-dd'),
    localTime: Utilities.formatDate(when, tz, 'HH:mm'),
  };
}

function MKT_macroFormatEvent_(event, tz) {
  const day = Utilities.formatDate(event.when, tz, 'EEE dd/MM');
  return `${day} ${event.localTime} · ${event.title}`;
}

function MKT_macroStartOfDay_(date, tz) {
  const ymd = Utilities.formatDate(date, tz, 'yyyy-MM-dd');
  return new Date(`${ymd}T00:00:00`);
}
