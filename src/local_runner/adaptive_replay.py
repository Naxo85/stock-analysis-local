"""Offline staging integration check using an already completed Sol response.

No model, data refresh or publication; old evaluation timestamps are intentional.
"""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from src.local_runner import adaptive_stage as stage
from src.local_runner.adaptive_budget import read_json, write_json
from src.local_runner.adaptive_policy import load_policy
from src.local_runner.adaptive_context import unpack_model_context


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report-dir", type=Path, required=True)
    args = parser.parse_args()
    root = Path.cwd()
    context = unpack_model_context(read_json(args.report_dir / "report.input.json"))
    symbol = context["symbol"]
    context.update(owned=False, tier="tracking", analyst_quality={}, analyst_summary={})
    work = root / "logs/adaptive_replay" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")
    write_json(work / "input.json", context)
    write_json(work / "policy.json", load_policy(root))
    result = {**read_json(args.report_dir / "report.receipt.json"),
              "completed_at": datetime.fromtimestamp((args.report_dir / "report.response").stat().st_mtime, timezone.utc).isoformat(),
              "text": (args.report_dir / "report.response").read_text(encoding="utf-8")}
    with patch.object(stage, "data_ready"), patch.object(stage, "model_call", return_value=result) as model:
        review = stage.analyze(root, work, symbol, work / "budget.json", True)
    payload = read_json(work / "publish/output" / symbol / "latest.json")
    assert model.call_count == 1
    assert review["status"] == "regenerated" and payload["analysis_status"] == "ok"
    assert payload["generation_model"] == result["model"]
    assert payload["slim_snapshot"] == context["slim"]
    assert (work / "publish/output" / symbol / "latest.html").exists()
    events = [json.loads(line) for line in (args.report_dir / "report.events.jsonl").read_text(encoding="utf-8").splitlines() if line.startswith("{")]
    searches = [event["item"] for event in events if event.get("type") == "item.completed"
                and event.get("item", {}).get("type") == "web_search"]
    audit = {"staging_validated": True, "source_report": str(args.report_dir), "no_publication": True,
             "model": result["model"], "usage": result["usage"], "web_tool_rounds": len(searches),
             "search_queries": [q for item in searches for q in item.get("action", {}).get("queries", [])]}
    write_json(work / "audit.json", audit)
    print(json.dumps(audit, ensure_ascii=False))
    print(f"PASS offline replay: validated JSON/Markdown/HTML staged at {work}; no publication")


if __name__ == "__main__":
    main()
