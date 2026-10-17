const assert = require('assert');
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const testToday = new Date().toISOString().slice(0, 10);
const testCandidateDate = (() => {
  const start = new Date(`${testToday}T00:00:00Z`);
  for (let offset = 1; offset <= 30; offset++) {
    const candidate = new Date(start.getTime() + offset * 24 * 60 * 60 * 1000);
    if (candidate.getUTCDay() >= 1 && candidate.getUTCDay() <= 5) {
      return candidate.toISOString().slice(0, 10);
    }
  }
  throw new Error('No weekday candidate found');
})();
const cacheValues = new Map();
const fetchedUrls = [];
let failedNasdaqDate = null;
let lockAvailable = true;
let lastLockWaitMs = null;
let publishedReportDate = null;
const context = {
  CacheService: {
    getScriptCache() {
      return {
        get(key) {
          return cacheValues.has(key) ? cacheValues.get(key) : null;
        },
        getAll(keys) {
          return Object.fromEntries(
            keys
              .filter(key => cacheValues.has(key))
              .map(key => [key, cacheValues.get(key)])
          );
        },
        put(key, value) {
          cacheValues.set(key, String(value));
        },
        putAll(values) {
          Object.entries(values).forEach(([key, value]) => {
            cacheValues.set(key, String(value));
          });
        }
      };
    }
  },
  LockService: {
    getScriptLock() {
      return {
        tryLock(waitMs) {
          lastLockWaitMs = waitMs;
          return lockAvailable;
        },
        releaseLock() {}
      };
    }
  },
  PropertiesService: {
    getScriptProperties() {
      return { getProperty() { return 'test-finnhub-key'; } };
    }
  },
  Session: { getScriptTimeZone() { return 'Europe/Madrid'; } },
  Utilities: {
    formatDate(value) {
      return new Date(value).toISOString().slice(0, 10);
    }
  },
  UrlFetchApp: {
    fetch(url) {
      const parsed = new URL(url);
      const symbol = parsed.searchParams.get('symbol');
      const isReportRequest = parsed.hostname.startsWith('reports-');

      if (isReportRequest) {
        const nextDate = symbol === 'MRVL' ? publishedReportDate : null;
        return {
          getResponseCode() { return nextDate ? 200 : 404; },
          getContentText() {
            return JSON.stringify({
              analyst_ratings_summary: { next_earnings_date: nextDate }
            });
          }
        };
      }

      throw new Error(`Unexpected fetch in test: ${url}`);
    },
    fetchAll(requests) {
      return requests.map(request => {
        fetchedUrls.push(request.url);
        const requestedDate = new URL(request.url).searchParams.get('date');
        const rows = requestedDate === testCandidateDate
          ? [{ symbol: 'USAR' }, { symbol: 'USAR' }]
          : null;
        return {
          getResponseCode() {
            return requestedDate === failedNasdaqDate ? 503 : 200;
          },
          getContentText() {
            return JSON.stringify({ data: { rows } });
          }
        };
      });
    }
  }
};

vm.createContext(context);
const source = fs.readFileSync(
  path.join(__dirname, '..', 'apps_script', 'fuerza.gs'),
  'utf8'
);
vm.runInContext(source, context);

const directFallback = context._nextEarnNasdaqOne('USAR', testToday);
assert.strictEqual(directFallback.toISOString().slice(0, 10), testCandidateDate);
assert.strictEqual(lastLockWaitMs, 10 * 1000);
const candidateCount = context._nasdaqCandidateDates(testToday).length;
assert.ok(candidateCount >= 21 && candidateCount <= 23);
assert.strictEqual(fetchedUrls.length, candidateCount);

publishedReportDate = testCandidateDate;
const publishedReport = context._nextEarnFinnhubOne('MRVL');
assert.strictEqual(publishedReport.toISOString().slice(0, 10), testCandidateDate);

cacheValues.set(`NEXT_EARN_FH_v2_USAR_${testToday}`, '?');
const cachedFinnhubMiss = context._nextEarnFinnhubOne('USAR');
assert.strictEqual(cachedFinnhubMiss.toISOString().slice(0, 10), testCandidateDate);
assert.strictEqual(fetchedUrls.length, candidateCount, 'Nasdaq window should be reused from cache');

assert.strictEqual(context._addDaysYmd('2026-12-31', 1), '2027-01-01');
assert.strictEqual(context._nextEarnNasdaqOne('MISSING', testToday), '?');
assert.strictEqual(fetchedUrls.length, candidateCount, 'Missing tickers should not trigger more requests');

// Una fecha fallida no debe impedir encontrar un ticker en otra fecha de la ventana.
cacheValues.clear();
failedNasdaqDate = context._nasdaqCandidateDates(testToday)[0];
assert.notStrictEqual(failedNasdaqDate, testCandidateDate);
const partialFallback = context._nextEarnNasdaqOne('USAR', testToday);
assert.strictEqual(partialFallback.toISOString().slice(0, 10), testCandidateDate);
assert.strictEqual(
  cacheValues.has(`NEXT_EARN_NQ_v4_${failedNasdaqDate}`),
  false,
  'Failed Nasdaq dates must remain uncached so a later call can retry them'
);

// Si otra ejecución tiene el lock, se aprovechan las fechas ya cacheadas.
lockAvailable = false;
const cachedPartialFallback = context._nextEarnNasdaqOne('USAR', testToday);
assert.strictEqual(cachedPartialFallback.toISOString().slice(0, 10), testCandidateDate);

console.log('NEXT_EARN fallback tests passed.');
