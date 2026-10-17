from __future__ import annotations

import logging
import os
import shutil
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

from flask import Flask, jsonify

from stock_analysis.analysis_worker.run_sync import run as run_analysis_sync
from stock_analysis.controller.refresh_coordinator import FirestoreRefreshCoordinator
from stock_analysis.market_worker.cloud_cache import (
    GcsHistoryArchive,
    GcsQuoteCache,
    cache_fingerprint,
)
from stock_analysis.market_worker.providers import QUOTE_CACHE_NAME
from stock_analysis.market_worker.run_refresh import run


app = Flask(__name__)
LOGGER = logging.getLogger(__name__)


@app.get("/health")
def health():
    return jsonify(status="ok")


@app.post("/market/refresh")
def refresh_market():
    now = datetime.now(timezone.utc)
    coordinator = FirestoreRefreshCoordinator()
    claim = coordinator.claim(now)
    if claim is None:
        return jsonify(status="skipped", reason="bucket_already_handled_or_claimed")

    started = time.monotonic()
    try:
        bucket_name = os.environ["MARKET_HISTORY_BUCKET"]
        archive = GcsHistoryArchive(bucket_name)
        quote_archive = GcsQuoteCache(bucket_name)
        market_date = claim.bucket.session.now_et.date()
        cache_root = Path(tempfile.gettempdir()) / "stock-analysis-market-history"
        cache_dir = cache_root / market_date.isoformat()
        for stale_dir in cache_root.glob("*"):
            if stale_dir.is_dir() and stale_dir != cache_dir:
                shutil.rmtree(stale_dir, ignore_errors=True)
        if not any(cache_dir.glob("*.json")):
            archive.restore(claim.bucket.session.now_et.date(), cache_dir)
        quote_path = cache_dir / QUOTE_CACHE_NAME
        if not quote_path.exists():
            quote_archive.restore(cache_dir)
        quotes_before = quote_path.read_bytes() if quote_path.exists() else None
        before = cache_fingerprint(cache_dir)
        snapshot = run(
            publish=True,
            force=True,
            now=now,
            history_cache_dir=cache_dir,
        )
        if snapshot is None:
            raise RuntimeError("Market refresh returned no snapshot")
        if cache_fingerprint(cache_dir) != before:
            archive.save(market_date, cache_dir)
        if quote_path.exists() and quote_path.read_bytes() != quotes_before:
            quote_archive.save(cache_dir)

        duration = time.monotonic() - started
        coordinator.complete(
            claim,
            completed_at=datetime.now(timezone.utc),
            duration_seconds=duration,
            ticker_count=len(snapshot.metrics),
        )
        return jsonify(
            status="published",
            session=claim.bucket.session.name,
            interval_minutes=claim.bucket.session.target_interval_minutes,
            bucket=claim.bucket.key,
            tickers=len(snapshot.metrics),
            duration_seconds=round(duration, 3),
        )
    except BaseException as error:
        LOGGER.exception("Market refresh failed for bucket %s", claim.bucket.key)
        coordinator.fail(
            claim,
            failed_at=datetime.now(timezone.utc),
            error=error,
        )
        raise


@app.post("/analysis/refresh")
def refresh_analysis():
    started = time.monotonic()
    result = run_analysis_sync(
        publish=True,
        force=False,
        bucket_name=os.environ["MARKET_HISTORY_BUCKET"],
    )
    result["duration_seconds"] = round(time.monotonic() - started, 3)
    return jsonify(result)
