"""Exact, clock-aware verdict reuse and dated, report-bound research memory.

This is local persistence, not OpenAI's short-lived prompt cache. Cache failure
is a miss, never permission to retain without a valid model verdict.
"""
from __future__ import annotations
import hashlib
import json
import re
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo
from src.local_runner.adaptive_budget import read_json, write_json
from src.local_runner.analysis_state import _exclusive_read_lock
from src.local_runner.adaptive_context import compact_json
from src.local_runner.adaptive_policy import timestamp, daily_decision


def digest(value) -> str:
    return hashlib.sha256(compact_json(value).encode("utf-8")).hexdigest()


def temporal_state(context: dict, now: datetime) -> dict:
    """Invalidate at calendar/session rollover and machine-readable events.

    The stage independently rechecks freshness, coverage, expiry guards and ITV
    before looking up a verdict. Crossing an event timestamp invalidates reuse
    even with unchanged market data. Unparsed prose remains part of exact data.
    """
    boundaries = set()
    def visit(value):
        if isinstance(value, dict):
            for child in value.values():
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)
        elif isinstance(value, str):
            for match in re.finditer(r"\b\d{4}-\d{2}-\d{2}(?:T\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?(?:Z|[+-]\d{2}:\d{2})?)?", value):
                text = match.group()
                at = timestamp(text)
                if at is not None:
                    boundaries.add((text, at <= now))
    visit(context)
    return {"utc_day": now.astimezone(timezone.utc).date().isoformat(),
            "market_day": now.astimezone(ZoneInfo("America/New_York")).date().isoformat(),
            "boundaries": sorted(boundaries)}


def triage_key(context: dict, policy: dict, instructions: str, schema: dict, now: datetime) -> str:
    evidence = deepcopy(context)
    evidence.pop("prepared_at", None)  # Only refetch bookkeeping; all source timestamps stay.
    return digest({"contract": "triage-reuse-v1", "evidence": evidence,
                   "clock": temporal_state(evidence, now),
                   "policy": {k: v for k, v in policy.items() if k not in {"max_model_parallel", "production_enabled"}},
                   "instructions": instructions, "schema": schema})


def _path(root: Path, kind: str, symbol: str, key: str) -> Path:
    # Hash symbol too; never use a caller-controlled filesystem component.
    return root / ".local" / "adaptive-cache" / kind / digest(symbol) / (key + ".json")


def load_triage(root: Path, symbol: str, key: str, context: dict) -> dict | None:
    try:
        saved = read_json(_path(root, "triage", symbol, key))
        if not isinstance(saved, dict) or not isinstance(saved.get("receipt"), dict):
            return None
        if (saved.get("key") != key or saved["receipt"].get("exit_code") != 0
                or (saved["receipt"].get("research_enabled") and saved["receipt"].get("web_search_count") != 0)
                or not isinstance(saved["receipt"].get("usage"), dict)
                or not saved["receipt"]["usage"]
                or saved.get("response_digest") != digest(saved.get("text"))):
            return None
        verdict = json.loads(saved["text"])
        if daily_decision(verdict, context.get("guards", []), context) == "blocked":
            return None
        return saved
    except (OSError, ValueError, KeyError, TypeError):
        return None


def save_triage(root: Path, symbol: str, key: str, result: dict, context: dict) -> None:
    # External news can change without changing frozen feeds. Exact verdict
    # reuse remains valid for web-capable turns that actually made ZERO searches;
    # prompt-prefix caching is independent and stays available in both cases.
    if result.get("research_enabled") and result.get("web_search_count") != 0:
        return
    if result.get("exit_code") != 0 or result.get("cache_reused") or not result.get("usage"):
        return
    if daily_decision(json.loads(result["text"]), context.get("guards", []), context) == "blocked":
        return
    path = _path(root, "triage", symbol, key)
    path.parent.mkdir(parents=True, exist_ok=True)
    with _exclusive_read_lock(path.with_suffix(".lock")):
        write_json(path, {"key": key, "text": result["text"], "response_digest": digest(result["text"]),
                          "receipt": {k: v for k, v in result.items() if k != "text"}})


def reference_key(reference: dict) -> str:
    return digest({"generated_at": reference.get("generated_at"),
                   "model": reference.get("generation_model"),
                   "markdown": reference.get("analysis_markdown")})


def load_research(root: Path, symbol: str, reference: dict) -> dict | None:
    try:
        value = read_json(_path(root, "research", symbol, reference_key(reference)))
        return value if (isinstance(value, dict)
                         and value.get("reference_key") == reference_key(reference)
                         and value.get("as_of_report") == reference.get("generated_at")
                         and isinstance(value.get("cited_evidence"), list)
                         and isinstance(value.get("discovery_sources"), list)) else None
    except (OSError, ValueError, TypeError):
        return None


def save_research(root: Path, work: Path, symbol: str, payload: dict) -> None:
    """Only a successfully validated report can seed reusable research.

    Persist cited report paragraphs with their as-of date and source URLs, not
    independently fact-checked claims. Search results remain explicitly leads.
    The model must reverify current facts and time-sensitive events.
    """
    md = payload.get("analysis_markdown", "")
    cited = []
    for paragraph in re.split(r"\n\s*\n", md):
        urls = list(dict.fromkeys(re.findall(r"https?://[^\s<>\)\]]+", paragraph)))
        if urls:
            cited.append({"report_excerpt": paragraph, "source_urls": urls,
                          "provenance": "previous_sol_report_claim_not_independent_fact_check"})
    leads = {}
    events = work / "report.events.jsonl"
    if events.exists():
        for line in events.read_text(encoding="utf-8").splitlines():
            try:
                event = json.loads(line)
            except ValueError:
                continue
            if not isinstance(event, dict):
                continue
            item = event.get("item") or {}
            if not isinstance(item, dict):
                continue
            if event.get("type") != "item.completed" or item.get("type") != "web_search":
                continue
            for entry in item.get("results") or []:
                if not isinstance(entry, dict):
                    continue
                url = entry.get("url")
                if isinstance(url, str) and url.startswith(("https://", "http://")):
                    leads[url] = {"url": url, "title": entry.get("title"),
                                  "provenance": "search_discovery_not_verified"}
    key = reference_key(payload)
    memory = {"reference_key": key, "as_of_report": payload.get("generated_at"),
              "cited_evidence": cited, "discovery_sources": list(leads.values()),
              "freshness": "historical_only_recheck_current_facts_and_events"}
    path = _path(root, "research", symbol, key)
    path.parent.mkdir(parents=True, exist_ok=True)
    with _exclusive_read_lock(path.with_suffix(".lock")):
        write_json(path, memory)
