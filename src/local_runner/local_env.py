"""Small helpers for local, git-ignored environment configuration."""

from __future__ import annotations

import os
from pathlib import Path


def get_local_env_value(
    key: str,
    *,
    repo_root: Path,
    default: str | None = None,
) -> str | None:
    """Return an environment value from process env or .env.local."""

    value = os.environ.get(key)
    if value:
        return value

    return _read_env_file(repo_root / ".env.local").get(key, default)


def _read_env_file(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}

    values: dict[str, str] = {}

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()

        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        values[key.strip()] = _clean_value(value)

    return values


def _clean_value(value: str) -> str:
    cleaned = value.strip()

    if len(cleaned) >= 2 and cleaned[0] == cleaned[-1] and cleaned[0] in {"'", '"'}:
        return cleaned[1:-1]

    return cleaned
