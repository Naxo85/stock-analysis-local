from __future__ import annotations

import hashlib
import io
import re
import zipfile
from datetime import date
from pathlib import Path

from google.api_core.exceptions import NotFound
from google.cloud import storage

from stock_analysis.market_worker.providers import QUOTE_CACHE_NAME


SAFE_CACHE_FILE = re.compile(r"^[A-Z0-9.-]+\.json$")


def cache_fingerprint(cache_dir: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(cache_dir.glob("*.json")):
        if SAFE_CACHE_FILE.fullmatch(path.name):
            digest.update(path.name.encode("ascii"))
            digest.update(path.read_bytes())
    return digest.hexdigest()


class GcsHistoryArchive:
    def __init__(
        self,
        bucket_name: str,
        *,
        client: storage.Client | None = None,
        prefix: str = "runtime/market-history",
    ) -> None:
        self._bucket = (client or storage.Client()).bucket(bucket_name)
        self._prefix = prefix.rstrip("/")

    def _blob(self, market_date: date):
        return self._bucket.blob(f"{self._prefix}/{market_date.isoformat()}.zip")

    def restore(self, market_date: date, cache_dir: Path) -> bool:
        try:
            payload = self._blob(market_date).download_as_bytes()
        except NotFound:
            return False

        cache_dir.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(io.BytesIO(payload), "r") as archive:
            for item in archive.infolist():
                if not SAFE_CACHE_FILE.fullmatch(item.filename):
                    raise ValueError(f"Unsafe history cache member: {item.filename!r}")
                (cache_dir / item.filename).write_bytes(archive.read(item))
        return True

    def save(self, market_date: date, cache_dir: Path) -> None:
        output = io.BytesIO()
        with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for path in sorted(cache_dir.glob("*.json")):
                if SAFE_CACHE_FILE.fullmatch(path.name):
                    archive.writestr(path.name, path.read_bytes())
        self._blob(market_date).upload_from_string(
            output.getvalue(), content_type="application/zip"
        )


class GcsQuoteCache:
    """Keep the last valid intraday sample across Cloud Run instances and dates."""

    def __init__(
        self,
        bucket_name: str,
        *,
        client: storage.Client | None = None,
        object_name: str = "runtime/market-quotes/latest.json",
    ) -> None:
        self._blob = (client or storage.Client()).bucket(bucket_name).blob(object_name)

    def restore(self, cache_dir: Path) -> bool:
        try:
            payload = self._blob.download_as_bytes()
        except NotFound:
            return False
        cache_dir.mkdir(parents=True, exist_ok=True)
        (cache_dir / QUOTE_CACHE_NAME).write_bytes(payload)
        return True

    def save(self, cache_dir: Path) -> None:
        self._blob.upload_from_filename(
            str(cache_dir / QUOTE_CACHE_NAME), content_type="application/json"
        )
