"""Two bounded Luna checks against a generated baseline; NEVER publish."""
import argparse
import json
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

from src.local_runner.adaptive_budget import check_quota, read_codex_rate_limits, write_json
from src.local_runner.adaptive_codex import TRIAGE_INSTRUCTIONS, call_codex
from src.local_runner.adaptive_context import model_context, unpack_model_context
from src.local_runner.adaptive_policy import load_policy, triage_schema, triage_decision, safeguards
from src.local_runner.report_schema import parse_report
from src.local_runner.adaptive_preflight import check


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline-dir", type=Path, required=True)
    parser.add_argument("--scenario", choices=("unchanged", "broken_support"))
    args = parser.parse_args()
    root = Path.cwd()
    policy = load_policy(root)
    check(root, policy)
    base = unpack_model_context(json.loads((args.baseline_dir / "report.input.json").read_text(encoding="utf-8")))
    markdown = (args.baseline_dir / "report.response").read_text(encoding="utf-8")
    parsed = parse_report(markdown, latest_price=base["slim"]["latest_price"])
    base["reference"] = {**parsed, "analysis_markdown": markdown, "analysis_status": "ok",
        "generated_at": base["prepared_at"], "slim_snapshot": deepcopy(base["slim"]),
        "latest_price": base["slim"]["latest_price"], "generation_model": policy["report_model"],
        "reasoning_effort": "high"}
    work = root / "logs/adaptive_evaluation" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")
    results = []
    for scenario in ((args.scenario,) if args.scenario else ("unchanged", "broken_support")):
        data = deepcopy(base)
        if scenario == "broken_support":
            data["slim"]["latest_price"] *= 0.85
            data["slim"]["levels"]["supports"] = [{"level": data["slim"]["latest_price"] * 0.95,
                                                     "type": "synthetic_new_support"}]
            data["slim"]["levels"]["put_walls_top"] = []
        guards = safeguards(data["reference"], data["slim"])
        data["guards"] = guards
        data = model_context(data)
        check_quota(read_codex_rate_limits(cwd=root))
        print(f"Evaluating {scenario}", flush=True)
        result = call_codex(workspace=root / ".local/codex-analysis-workspace", artifacts=work / scenario,
            kind="triage", instructions=TRIAGE_INSTRUCTIONS, data=data, model=policy["triage_model"],
            effort=policy["triage_effort"], timeout=policy["triage_timeout_seconds"], schema=triage_schema(data))
        payload = json.loads(result["text"])
        decision = triage_decision(payload, guards, data)
        results.append({"scenario": scenario, "guards": guards, "decision": decision,
                        "passed": decision == ("retain" if scenario == "unchanged" else "escalate"),
                        "usage": result["usage"], "reason": payload["reason"]})
        write_json(work / "summary.json", {"evaluation_only": True, "results": results})
        print(json.dumps(results[-1], ensure_ascii=True), flush=True)
    print(str(work), flush=True)


if __name__ == "__main__":
    main()
