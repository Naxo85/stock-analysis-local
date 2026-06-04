import os
import time
import logging
import requests
import functions_framework

from concurrent.futures import ThreadPoolExecutor, as_completed
from flask import jsonify


logging.basicConfig(level=logging.INFO)

ANALYZE_URL = os.environ.get(
    "ANALYZE_URL",
    "https://gemini-stock-analyze-714254943648.europe-southwest1.run.app"
)

MAX_WORKERS = int(os.environ.get("MAX_WORKERS", "8"))
REQUEST_TIMEOUT = int(os.environ.get("REQUEST_TIMEOUT", "240"))


@functions_framework.http
def analyze_batch(request):
    try:
        tickers = _get_tickers(request)

        if not tickers:
            return jsonify(
                error="Missing tickers. Use JSON {'tickers':['RKLB']} or ?tickers=RKLB,APP"
            ), 400

        started = time.time()

        logging.info("batch_started tickers=%s count=%s", tickers, len(tickers))

        results = []

        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            future_map = {
                executor.submit(_call_analyze, ticker): ticker
                for ticker in tickers
            }

            for future in as_completed(future_map):
                ticker = future_map[future]

                try:
                    result = future.result()
                    results.append(result)

                    logging.info(
                        "ticker_done ticker=%s ok=%s status=%s elapsed=%.2fs",
                        ticker,
                        result.get("ok"),
                        result.get("status_code"),
                        result.get("elapsed_seconds"),
                    )

                except Exception as e:
                    logging.exception("ticker_failed ticker=%s", ticker)

                    results.append({
                        "ticker": ticker,
                        "ok": False,
                        "error": str(e)
                    })

        elapsed = round(time.time() - started, 2)

        ok = sum(1 for r in results if r.get("ok"))
        bad = len(results) - ok

        return jsonify({
            "ok": bad == 0,
            "count": len(results),
            "success": ok,
            "failed": bad,
            "elapsed_seconds": elapsed,
            "results": sorted(results, key=lambda x: x.get("ticker", ""))
        }), 200

    except Exception as e:
        logging.exception("batch_internal_error")

        return jsonify(
            error="batch_internal_error",
            details=str(e)
        ), 500


def _get_tickers(request):
    tickers_param = request.args.get("tickers")

    if tickers_param:
        raw = tickers_param.split(",")
    else:
        payload = request.get_json(silent=True) or {}
        raw = payload.get("tickers") or []

    tickers = []

    for t in raw:
        t = str(t or "").strip().upper()

        if t:
            tickers.append(t)

    # Deduplicar preservando orden
    seen = set()
    out = []

    for t in tickers:
        if t not in seen:
            seen.add(t)
            out.append(t)

    return out


def _call_analyze(ticker):
    started = time.time()

    url = ANALYZE_URL.rstrip("/")

    response = requests.get(
        url,
        params={
            "symbol": ticker,
            "save": "true"
        },
        timeout=REQUEST_TIMEOUT
    )

    body = response.text or ""

    ok = 200 <= response.status_code < 300

    result = {
        "ticker": ticker,
        "ok": ok,
        "status_code": response.status_code,
        "elapsed_seconds": round(time.time() - started, 2),
    }

    if ok:
        try:
            data = response.json()
            result["saved"] = data.get("saved")
            result["saved_paths"] = data.get("saved_paths")
            result["model"] = data.get("model")
            result["slim_as_of"] = data.get("slim_as_of")
        except Exception:
            result["warning"] = "Could not parse JSON response"
    else:
        result["body_preview"] = body[:1000]

    return result