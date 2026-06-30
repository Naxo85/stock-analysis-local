"""Find likely duplicate analyst firm names across local rating states.

This command is read-only. It intentionally produces candidates for manual
review instead of auto-merging firms, because aggressive firm-name normalization
can accidentally merge distinct desks.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any


GENERIC_SUFFIXES = {
    "advisors",
    "bank",
    "capital",
    "capital markets",
    "company",
    "co",
    "inc",
    "llc",
    "markets",
    "research",
    "securities",
}
TOKEN_ALIASES = {
    "bofa": "bank of america",
    "jpmorgan": "jp morgan",
    "keybanc": "keybanc",
}


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    repo_root = _find_repo_root(Path.cwd())
    states_dir = repo_root / "data" / "analyst_ratings"
    firms = _load_firms(states_dir)
    candidates = _find_candidates(firms, min_similarity=args.min_similarity)
    output = {
        "status": "ok",
        "firm_count": len(firms),
        "candidate_group_count": len(candidates),
        "candidates": candidates,
    }

    if args.output:
        output_path = (repo_root / args.output).resolve()
        _assert_inside(repo_root, output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(output, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"Wrote {output_path}")

    _print_candidates(candidates, limit=args.limit)
    return 0


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audit local analyst firm names for likely aliases."
    )
    parser.add_argument(
        "--min-similarity",
        type=float,
        default=0.86,
        help="Minimum fuzzy similarity for candidate pairs. Default: 0.86.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=80,
        help="Max candidate groups to print. Default: 80.",
    )
    parser.add_argument(
        "--output",
        default="logs/analyst_firm_alias_candidates.json",
        help="JSON output path relative to repo root.",
    )

    args = parser.parse_args(argv)

    if not 0 <= args.min_similarity <= 1:
        parser.error("--min-similarity must be between 0 and 1")
    if args.limit < 1:
        parser.error("--limit must be >= 1")

    return args


def _load_firms(states_dir: Path) -> dict[str, dict[str, Any]]:
    firms: dict[str, dict[str, Any]] = {}

    if not states_dir.exists():
        return firms

    for current_path in states_dir.glob("*/current.json"):
        ticker = current_path.parent.name.upper()
        try:
            payload = json.loads(current_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue

        state_firms = payload.get("firms")
        if not isinstance(state_firms, dict):
            continue

        for firm in state_firms.values():
            if not isinstance(firm, dict):
                continue

            name = _clean_name(firm.get("firm"))
            if not name:
                continue

            item = firms.setdefault(
                name,
                {
                    "firm": name,
                    "tickers": set(),
                    "ratings": set(),
                    "targets": [],
                    "last_updated": None,
                    "examples": [],
                },
            )
            item["tickers"].add(ticker)
            if firm.get("rating"):
                item["ratings"].add(str(firm.get("rating")))
            if isinstance(firm.get("target"), (int, float)):
                item["targets"].append(float(firm["target"]))
            item["last_updated"] = max(
                str(item.get("last_updated") or ""),
                str(firm.get("last_updated") or ""),
            ) or None
            if len(item["examples"]) < 3:
                item["examples"].append(
                    {
                        "ticker": ticker,
                        "rating": firm.get("rating"),
                        "target": firm.get("target"),
                        "headline": firm.get("last_headline"),
                    }
                )

    for item in firms.values():
        item["tickers"] = sorted(item["tickers"])
        item["ratings"] = sorted(item["ratings"])
        targets = item.pop("targets")
        item["target_count"] = len(targets)
        item["target_min"] = min(targets) if targets else None
        item["target_max"] = max(targets) if targets else None

    return firms


def _find_candidates(
    firms: dict[str, dict[str, Any]],
    *,
    min_similarity: float,
) -> list[dict[str, Any]]:
    by_key: dict[str, list[str]] = defaultdict(list)
    names = sorted(firms)

    for name in names:
        by_key[_loose_key(name)].append(name)

    pairs: list[tuple[str, str, float, str]] = []

    for key, group in by_key.items():
        if len(group) > 1:
            for left_index, left in enumerate(group):
                for right in group[left_index + 1 :]:
                    pairs.append((left, right, 1.0, f"same_loose_key:{key}"))

    for left_index, left in enumerate(names):
        left_key = _loose_key(left)
        for right in names[left_index + 1 :]:
            right_key = _loose_key(right)
            if left_key == right_key:
                continue
            if not _may_be_related(left_key, right_key):
                continue

            similarity = SequenceMatcher(None, left_key, right_key).ratio()
            if similarity >= min_similarity:
                pairs.append((left, right, round(similarity, 3), "fuzzy"))

    groups = _connected_groups(pairs)
    candidates = []

    for group in groups:
        candidates.append(
            {
                "firms": [
                    _candidate_firm_payload(name, firms[name])
                    for name in sorted(group)
                ],
                "reasons": sorted(
                    {
                        reason
                        for left, right, _score, reason in pairs
                        if left in group and right in group
                    }
                ),
                "max_similarity": max(
                    _score
                    for left, right, _score, _reason in pairs
                    if left in group and right in group
                ),
                "suggestion": "manual_review",
            }
        )

    candidates.sort(
        key=lambda item: (
            -item["max_similarity"],
            -sum(len(firm["tickers"]) for firm in item["firms"]),
            item["firms"][0]["firm"],
        )
    )
    return candidates


def _connected_groups(pairs: list[tuple[str, str, float, str]]) -> list[set[str]]:
    parent: dict[str, str] = {}

    def find(value: str) -> str:
        parent.setdefault(value, value)
        if parent[value] != value:
            parent[value] = find(parent[value])
        return parent[value]

    def union(left: str, right: str) -> None:
        left_root = find(left)
        right_root = find(right)
        if left_root != right_root:
            parent[right_root] = left_root

    for left, right, _score, _reason in pairs:
        union(left, right)

    groups: dict[str, set[str]] = defaultdict(set)
    for value in list(parent):
        groups[find(value)].add(value)

    return [group for group in groups.values() if len(group) > 1]


def _candidate_firm_payload(name: str, firm: dict[str, Any]) -> dict[str, Any]:
    return {
        "firm": name,
        "loose_key": _loose_key(name),
        "tickers": firm["tickers"],
        "ratings": firm["ratings"],
        "target_count": firm["target_count"],
        "target_min": firm["target_min"],
        "target_max": firm["target_max"],
        "last_updated": firm["last_updated"],
        "examples": firm["examples"],
    }


def _loose_key(value: str) -> str:
    text = _clean_name(value).lower()
    text = text.replace("&", " and ")
    text = re.sub(r"[^a-z0-9 ]+", " ", text)
    tokens = [TOKEN_ALIASES.get(token, token) for token in text.split()]
    text = " ".join(tokens)

    changed = True
    while changed:
        changed = False
        for suffix in sorted(GENERIC_SUFFIXES, key=len, reverse=True):
            if text == suffix:
                continue
            if text.endswith(f" {suffix}"):
                text = text[: -(len(suffix) + 1)].strip()
                changed = True

    return " ".join(text.split())


def _may_be_related(left: str, right: str) -> bool:
    if not left or not right:
        return False
    if left in right or right in left:
        return True
    left_tokens = set(left.split())
    right_tokens = set(right.split())
    return bool(left_tokens & right_tokens)


def _print_candidates(candidates: list[dict[str, Any]], *, limit: int) -> None:
    if not candidates:
        print("No candidate aliases found.")
        return

    for index, candidate in enumerate(candidates[:limit], start=1):
        firms = ", ".join(firm["firm"] for firm in candidate["firms"])
        print(
            f"{index}. score={candidate['max_similarity']} "
            f"reasons={','.join(candidate['reasons'])}: {firms}"
        )
        for firm in candidate["firms"]:
            print(
                f"   - {firm['firm']} | tickers={len(firm['tickers'])} "
                f"ratings={firm['ratings']} targets={firm['target_count']}"
            )


def _clean_name(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _find_repo_root(start: Path) -> Path:
    current = start.resolve()

    for candidate in (current, *current.parents):
        if (candidate / "AGENTS.md").exists() and (candidate / "src").exists():
            return candidate

    return current


def _assert_inside(root: Path, target: Path) -> None:
    root = root.resolve()
    target = target.resolve()

    try:
        target.relative_to(root)
    except ValueError as exc:
        raise RuntimeError(f"path_outside_repo: {target}") from exc


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001
        print(f"FAILED audit_analyst_firm_aliases: {exc}", file=sys.stderr)
        raise SystemExit(1)
