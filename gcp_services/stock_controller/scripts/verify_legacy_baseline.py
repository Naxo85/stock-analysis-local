"""Verify that the observed legacy source files still match the baseline."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LEGACY_ROOT = REPOSITORY_ROOT.parent / "stock-analysis-local"
MANIFEST_PATH = REPOSITORY_ROOT / "baseline" / "legacy_source_manifest.json"


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify(legacy_root: Path) -> list[str]:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    failures: list[str] = []

    for item in manifest["files"]:
        relative_path = Path(item["path"])
        source_path = legacy_root / relative_path
        if not source_path.is_file():
            failures.append(f"MISSING {relative_path.as_posix()}")
            continue

        actual = file_sha256(source_path)
        if actual != item["sha256"]:
            failures.append(
                f"CHANGED {relative_path.as_posix()} expected={item['sha256']} actual={actual}"
            )

    return failures


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--legacy-root",
        type=Path,
        default=DEFAULT_LEGACY_ROOT,
        help="Path to the stock-analysis-local checkout",
    )
    args = parser.parse_args()

    failures = verify(args.legacy_root.resolve())
    if failures:
        print("Legacy baseline differs:")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print("Legacy baseline source hashes: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

