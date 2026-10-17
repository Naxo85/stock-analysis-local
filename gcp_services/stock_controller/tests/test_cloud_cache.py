from __future__ import annotations

import tempfile
import unittest
from datetime import date
from pathlib import Path

from google.api_core.exceptions import NotFound

from stock_analysis.market_worker.cloud_cache import (
    GcsHistoryArchive,
    cache_fingerprint,
)


class FakeBlob:
    def __init__(self, store: dict[str, bytes], name: str) -> None:
        self.store = store
        self.name = name

    def download_as_bytes(self) -> bytes:
        if self.name not in self.store:
            raise NotFound("missing fixture")
        return self.store[self.name]

    def upload_from_string(self, value: bytes, **_kwargs) -> None:
        self.store[self.name] = value


class FakeBucket:
    def __init__(self) -> None:
        self.store: dict[str, bytes] = {}

    def blob(self, name: str) -> FakeBlob:
        return FakeBlob(self.store, name)


class FakeStorageClient:
    def __init__(self, bucket: FakeBucket) -> None:
        self._bucket = bucket

    def bucket(self, _name: str) -> FakeBucket:
        return self._bucket


class GcsHistoryArchiveTest(unittest.TestCase):
    def test_daily_cache_round_trip_uses_one_archive(self) -> None:
        bucket = FakeBucket()
        archive = GcsHistoryArchive(
            "fixture", client=FakeStorageClient(bucket)
        )
        market_date = date(2026, 9, 8)

        with tempfile.TemporaryDirectory() as source_directory:
            source = Path(source_directory)
            (source / "AMD.json").write_text('{"cache_date":"2026-09-08"}')
            (source / "MU.json").write_text('{"cache_date":"2026-09-08"}')
            archive.save(market_date, source)

        self.assertEqual(len(bucket.store), 1)
        with tempfile.TemporaryDirectory() as target_directory:
            target = Path(target_directory)
            self.assertTrue(archive.restore(market_date, target))
            self.assertEqual(
                {path.name for path in target.iterdir()}, {"AMD.json", "MU.json"}
            )

    def test_missing_daily_archive_is_not_an_error(self) -> None:
        archive = GcsHistoryArchive(
            "fixture", client=FakeStorageClient(FakeBucket())
        )
        with tempfile.TemporaryDirectory() as directory:
            restored = archive.restore(date(2026, 9, 8), Path(directory))
        self.assertFalse(restored)

    def test_fingerprint_changes_only_when_cache_content_changes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            cache = Path(directory)
            empty = cache_fingerprint(cache)
            (cache / "AMD.json").write_text("first")
            first = cache_fingerprint(cache)
            self.assertEqual(first, cache_fingerprint(cache))
            (cache / "AMD.json").write_text("second")
            second = cache_fingerprint(cache)

        self.assertNotEqual(empty, first)
        self.assertNotEqual(first, second)


if __name__ == "__main__":
    unittest.main()
