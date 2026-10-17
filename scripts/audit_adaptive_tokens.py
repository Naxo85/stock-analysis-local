"""Read-only audit of saved adaptive inputs/usage; no model or network calls."""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path


def measure(value):
    regular = json.dumps(value, ensure_ascii=False)
    compact = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    result = {"chars": len(regular), "compact_chars": len(compact)}
    if importlib.util.find_spec("tiktoken"):
        import tiktoken
        enc = tiktoken.get_encoding("o200k_base")
        result.update(estimated_o200k_tokens=len(enc.encode(regular)),
                      compact_estimated_o200k_tokens=len(enc.encode(compact)))
    return result


def main():
    root = Path(__file__).resolve().parents[1]
    receipts = []
    for directory in ("logs/adaptive_smoke", "logs/adaptive_evaluation"):
        for path in sorted((root / directory).rglob("*.receipt.json")):
            value = json.loads(path.read_text(encoding="utf-8"))
            receipts.append({"path": str(path.relative_to(root)), **value})
    grouped = {}
    for value in receipts:
        role = "report" if "report.receipt" in value["path"] else "triage"
        key = (role, value.get("model"), value.get("instructions_sha256"), value.get("schema_sha256"))
        group = grouped.setdefault(key, {"role": role, "model": value.get("model"),
            "prefix_hash": value.get("instructions_sha256"), "schema_hash": value.get("schema_sha256"),
            "calls": 0, "input": 0, "cached": 0, "output": 0, "paths": []})
        usage = value.get("usage") or {}
        group["calls"] += 1
        group["input"] += usage.get("input_tokens", 0)
        group["cached"] += usage.get("cached_input_tokens", 0)
        group["output"] += usage.get("output_tokens", 0)
        group["paths"].append(value["path"])
    print(json.dumps({"receipt_groups": list(grouped.values())}, ensure_ascii=False))

    for path in sorted((root / "logs/adaptive_smoke/20261001T111917974635").glob("*/triage.input.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        candidate = json.loads(json.dumps(data))
        for key in ("plan", "decision", "catalysts", "next_event", "latest_price"):
            candidate.get("reference", {}).pop(key, None)
        identical = data.get("reference", {}).get("slim_snapshot") == data.get("slim")
        baseline_at = data.get("reference", {}).get("generated_at", "")
        news = data.get("news", {}).get("items", [])
        dedup = {json.dumps(item, sort_keys=True, ensure_ascii=False) for item in news}
        print(json.dumps({"input": str(path.relative_to(root)), "measure": measure(data),
            "field_measures": {key: measure(value) for key, value in data.items()},
            "reference_measures": {key: measure(value) for key, value in data.get("reference", {}).items()},
            "candidate_drop_reference_structured_duplicates": measure(candidate),
            "identical_market_snapshots": identical,
            "news_count": len(news), "exact_duplicate_news_count": len(news)-len(dedup),
            "news_not_after_baseline": sum(item.get("published_at", "") <= baseline_at for item in news),
            "news_item_keys": list((data.get("news", {}).get("items") or [{}])[0]),
            "source_schema_hash": hashlib.sha256((path.parent / "triage.schema.json").read_bytes()).hexdigest()
        }, ensure_ascii=False))

    schemas = [(path, json.loads(path.read_text(encoding="utf-8"))) for path in
               sorted((root / "logs/adaptive_smoke/20261001T111917974635").glob("*/triage.schema.json"))]
    if len(schemas) == 2:
        enums = [set(value["$defs"]["evidence_pointer"]["enum"]) for _, value in schemas]
        print(json.dumps({"schema_pointer_differences": {str(path.relative_to(root)): sorted(enums[index]-enums[1-index])
                         for index, (path, _) in enumerate(schemas)}}))

    for name in ("prompts/daily_triage.md", "prompts/stock_analysis_system_prompt.md"):
        value = (root / name).read_text(encoding="utf-8")
        print(json.dumps({"instructions": name, "measure": measure(value)}))

    event_path = root / "logs/adaptive_smoke/20261001T113503724136/CAT/report.events.jsonl"
    rounds = []
    for line in event_path.read_text(encoding="utf-8").splitlines():
        event = json.loads(line)
        item = event.get("item") or {}
        if event.get("type") == "item.completed" and item.get("type") == "web_search":
            rounds.append({"action": item.get("action", {}).get("type"),
                           "queries": item.get("action", {}).get("queries", []),
                           "result_count": len(item.get("results", []))})
    print(json.dumps({"researched_report_web_rounds": rounds}, ensure_ascii=False))


if __name__ == "__main__":
    main()
