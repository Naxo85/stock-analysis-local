"""Audit last batch's exact differences; optional isolated Luna-high checks.

No source refresh, Sol call, batch, publication or production report mutation.
Historical chronology is explicitly evaluation_only; critical fixture synthetic.
"""
from __future__ import annotations
import argparse
import hashlib
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.local_runner.adaptive_budget import read_json, write_json, check_quota, read_codex_rate_limits
from src.local_runner.adaptive_context import model_context, validation_context
from src.local_runner.adaptive_policy import load_policy, maintenance_precheck, itv_state
from src.local_runner.adaptive_maintenance import maintenance_schema, maintenance_decision, apply_update
from src.local_runner.adaptive_codex import call_codex
from src.local_runner.adaptive_preflight import check
from src.local_runner import run_one as one
from scripts.verify_adaptive_maintenance import instructions


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch-dir", type=Path, default=Path("logs/batch/2026-10-03/18-29-23"))
    parser.add_argument("--execute-luna", action="store_true")
    parser.add_argument("--scenario", choices=("MP", "NVDA", "critical_news"))
    parser.add_argument("--replay-case", type=Path, help="Validate a saved candidate without any model call")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    policy = load_policy(root)
    if policy.get("routing_revision") != 4 or policy.get("triage_effort") != "high":
        raise RuntimeError("evaluation_requires_revision4_luna_high")
    source = args.batch_dir.resolve() / "adaptive"
    work = root / "logs/adaptive_delta_evaluation" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")
    if args.replay_case:
        if args.execute_luna:
            raise RuntimeError("replay_cannot_call_model")
        saved = args.replay_case.resolve()
        context_path = saved / "context.json"
        if not context_path.is_file():
            context_path = saved / "input.json"
        raw = read_json(context_path)
        value = json.loads((saved / "triage.response").read_text(encoding="utf-8"))
        context = model_context(raw)
        audit = []
        candidate = apply_update(value, context, audit=audit)
        validation = one.validate_markdown(candidate, authoritative_context=validation_context(context),
            require_support_strengths=True, require_resistance=True, require_separate_scores=True)
        result = {"replayed_from": str(saved), "model_called": False, "published": False,
                  "context_sha256": hashlib.sha256(context_path.read_bytes()).hexdigest(),
                  "response_sha256": hashlib.sha256((saved / "triage.response").read_bytes()).hexdigest(),
                  "validation": validation.to_dict(), "normalizations": audit}
        write_json(work / "replay.json", result)
        print(json.dumps(result, ensure_ascii=True), flush=True)
        if not validation.ok:
            raise SystemExit(1)
        return
    rows, contexts = [], {}
    for directory in sorted(source.iterdir()):
        raw = read_json(directory / "input.json")
        if not raw:
            continue
        raw["routing_revision"] = 4
        view = model_context(raw)
        delta = view["comparison"]["deterministic"]
        rows.append({"symbol": directory.name, "old_decision": read_json(directory / "triage.json").get("decision"),
            "same_current_and_sol_markdown": delta["same_current_and_sol_markdown"],
            "market_changed_groups": delta["since_full_sol"]["changed_groups"],
            "same_market_values": delta["since_full_sol"]["same_market_values"],
            "geometry": delta["current_plan_geometry"],
            "news_identical": delta["news_since_full_sol"]["identical_count"],
            "news_current": delta["news_since_full_sol"]["current_count"],
            "news_after_full_sol": delta["news_since_full_sol"]["after_report_count"]})
        if directory.name in {"MP", "NVDA"}:
            contexts[directory.name] = raw
    write_json(work / "offline_audit.json", {"evaluation_only": True, "model_called": False, "published": False, "rows": rows})
    print(json.dumps({"offline_tickers": len(rows), "output": str(work)}), flush=True)
    if not args.execute_luna:
        return
    if set(contexts) != {"MP", "NVDA"}:
        raise RuntimeError("missing_incident_inputs")
    critical = deepcopy(contexts["NVDA"])
    at = datetime.fromisoformat(critical["prepared_at"]) - timedelta(seconds=1)
    critical["news"]["items"].append({"articleId": "synthetic-delta-critical-guidance",
        "providerCode": "EVAL", "published_at": at.isoformat(),
        "headline": "NVDA: la compañía recorta previsión anual de ingresos un 35% y comunica riesgo material de liquidez.",
        "source": "SYNTHETIC EVALUATION ONLY, NOT REAL NEWS"})
    critical["news"]["count"] = len(critical["news"]["items"])
    contexts["critical_news"] = critical
    if args.scenario:
        contexts = {args.scenario: contexts[args.scenario]}
    check(root, policy)
    check_quota(read_codex_rate_limits(cwd=root))
    prefix = instructions(root)
    def run(name):
        raw = deepcopy(contexts[name])
        raw.update(evaluation_only=True, evaluation_scenario=name)
        raw.update(maintenance_precheck(raw["reference"], raw["slim"], raw["sol_reference"], owned=raw["owned"]))
        raw["itv"] = itv_state(raw["sol_reference"], owned=raw["owned"], priority=raw["tier"] == "priority",
            now=datetime.fromisoformat(raw["prepared_at"]), policy=policy)
        context = model_context(raw)
        context.pop("research_memory", None)
        artifact = work / name
        write_json(artifact / "context.json", raw)
        receipt = call_codex(workspace=root / ".local/codex-analysis-workspace", artifacts=artifact,
            kind="triage", instructions=prefix + ("\n\nEVALUATION HARNESS: For this evaluation_only counterfactual, treat supplied synthetic news as hypothetical facts under the SAME maintenance policy. Synthetic labels disclose fixture provenance, not a reason to deny the hypothetical premise. This does not claim real-world truth or authorize publication.\n" if name == "critical_news" else ""), data=context, model=policy["triage_model"],
            effort=policy["triage_effort"], timeout=policy["triage_timeout_seconds"],
            schema=maintenance_schema(context), max_parallel=policy["max_model_parallel"])
        value = json.loads(receipt["text"])
        decision = maintenance_decision(value, raw["guards"], context)
        valid = True
        if decision == "update":
            try:
                audit = []
                candidate = apply_update(value, context, audit=audit)
                validation = one.validate_markdown(candidate, authoritative_context=validation_context(context),
                    require_support_strengths=True, require_resistance=True, require_separate_scores=True)
                write_json(artifact / "validation.json", validation.to_dict())
                valid = validation.ok
            except ValueError as exc:
                write_json(artifact / "validation.json", {"ok": False, "error": str(exc)})
                valid = False
        result = {"scenario": name, "decision": decision, "reason": value["reason"], "usage": receipt["usage"],
            "model": receipt["model"], "effort": receipt["reasoning_effort"], "published": False,
            "passed": decision == "escalate" if name == "critical_news" else decision in {"retain", "update"} and valid}
        write_json(artifact / "outcome.json", result)
        print(json.dumps(result, ensure_ascii=True), flush=True)
        return result
    with ThreadPoolExecutor(max_workers=3) as pool:
        results = list(pool.map(run, contexts))
    write_json(work / "summary.json", {"evaluation_only": True, "published": False,
        "passed": all(v["passed"] for v in results), "results": results})
    if not all(v["passed"] for v in results):
        raise SystemExit(1)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
