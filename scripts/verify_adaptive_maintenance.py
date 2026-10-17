"""Representative frozen-input maintenance checks; never uploads or runs a batch.

Default is an offline routing audit. --execute-luna explicitly consumes model
usage for unchanged, routine-options-maintenance and critical-news scenarios.
Synthetic changes are marked evaluation_only and never become production data.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.local_runner import run_one as one
from src.local_runner.adaptive_budget import read_json, write_json, check_quota, read_codex_rate_limits
from src.local_runner.adaptive_policy import maintenance_precheck, load_policy, itv_state
from src.local_runner.adaptive_context import model_context, validation_context, MAINTENANCE_OVERRIDE
from src.local_runner.adaptive_maintenance import maintenance_schema, maintenance_decision, apply_update
from src.local_runner.adaptive_codex import call_codex
from src.local_runner.adaptive_preflight import check


def instructions(root: Path) -> str:
    return ((root / "prompts/daily_maintenance.md").read_text(encoding="utf-8") +
        "\n\nAUTHORITATIVE REPORT FORMAT AND RUBRIC (no tools for Luna):\n" + one._load_system_prompt(root) +
        MAINTENANCE_OVERRIDE)


def _put_wall_nodes(value, path="/slim"):
    """All current copies only; baseline snapshots deliberately remain historical."""
    if isinstance(value, dict):
        if str(value.get("type", "")).startswith("put_wall") and isinstance(value.get("level"), (int, float)):
            yield path, value
        for key, child in value.items():
            yield from _put_wall_nodes(child, path + "/" + key)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _put_wall_nodes(child, path + "/" + str(index))


def scenario_context(frozen: dict, scenario: str) -> dict:
    """Build explicitly synthetic evidence; do not dictate Luna's chosen scores."""
    context = deepcopy(frozen)
    context["evaluation_scenario"] = scenario
    if scenario == "routine_update":
        if context["symbol"] != "ORCL":
            raise RuntimeError("routine_options_fixture_requires_ORCL")
        slim = context["slim"]
        walls = slim["levels"]["put_walls_top"]
        selected = [wall for wall in walls if wall["level"] == 140 and wall["expiration"] == "2026-10-16"]
        if len(selected) != 1:
            raise RuntimeError("routine_options_fixture_requires_unique_140_monthly_put")
        old = deepcopy(selected[0])
        # A meaningful, bounded change: the defining put remains live, but its
        # concentration/neighbor dominance is no longer what Sol reported.
        # Price, expirations, independent OHLCV defenses, nodes, thesis/news,
        # entries, stops and targets are all untouched. This is NOT a rule that
        # every small price tick should produce a paid maintenance report.
        oi_delta = round(old["oi"] * 0.45)
        gamma_delta = round(old["gamma_usd_millions"] * 0.45, 3)
        # Published shares are rounded and their wall-selection denominator is
        # distinct from the full expiration OI totals. Infer that denominator
        # from the whole wall list, not from only the altered strike.
        gamma_total = sum(w["gamma_usd_millions"] for w in walls) / (sum(w["gamma_share_pct"] for w in walls) / 100)
        oi_total = sum(w["oi"] for w in walls) / (sum(w["oi_share_pct"] for w in walls) / 100)
        changed_paths = []
        for path, wall in _put_wall_nodes(slim):
            if wall.get("level") == 140 and wall.get("expiration") == old["expiration"]:
                if wall.get("oi") != old["oi"] or wall.get("gamma_usd_millions") != old["gamma_usd_millions"]:
                    raise RuntimeError("inconsistent_current_140_put_copies")
                wall["oi"] = old["oi"] - oi_delta
                wall["gamma_usd_millions"] = round(old["gamma_usd_millions"] - gamma_delta, 3)
                changed_paths.append(path)
            if "gamma_share_pct" in wall:
                wall["gamma_share_pct"] = round(100 * wall["gamma_usd_millions"] / (gamma_total - gamma_delta), 1)
            if "oi_share_pct" in wall:
                wall["oi_share_pct"] = round(100 * wall["oi"] / (oi_total - oi_delta), 1)
            if "cluster_gamma_usd" in wall:
                if wall["cluster_low"] <= 140 <= wall["cluster_high"]:
                    wall["cluster_gamma_usd"] = round(wall["cluster_gamma_usd"] - gamma_delta, 3)
                wall["cluster_share_pct"] = round(100 * wall["cluster_gamma_usd"] / (gamma_total - gamma_delta), 1)
        options = slim["options"]
        expiry = next(expiry for expiry in options["expirations"] if expiry["date"] == old["expiration"])
        expiry["put_oi"] -= oi_delta
        expiry["put_call_oi_ratio"] = round(expiry["put_oi"] / expiry["call_oi"], 3)
        options["near_term_total_put_oi"] -= oi_delta
        options["near_term_put_call_oi_ratio"] = round(options["near_term_total_put_oi"] / options["near_term_total_call_oi"], 3)
        options["gex_total_usd_millions"] = round(options["gex_total_usd_millions"] + gamma_delta, 3)
        context["evaluation_fixture"] = {
            "synthetic": True, "not_a_real_market_claim": True,
            "change": "45% reduction of ORCL monthly $140 put OI/absolute gamma; live same-strike wall and independent historical defenses preserved",
            "changed_current_wall_copies": changed_paths,
            "before_wall": old, "after_wall": deepcopy(selected[0]),
            "wall_share_denominators": "estimated from rounded wall-list shares; not full expiration totals",
            "independent_evidence_unchanged": old["evidence"],
            "expected_report_work": "Reassess factual option factors and Options component/Setup if warranted; do not alter thesis/catalysts or invent a predetermined score",
        }
        if context["reference"] != frozen["reference"] or context["sol_reference"] != frozen["sol_reference"]:
            raise RuntimeError("fixture_mutated_historical_baseline")
        if selected[0]["evidence"] != old["evidence"] or slim["latest_price"] != frozen["slim"]["latest_price"]:
            raise RuntimeError("fixture_mutated_independent_technical_support")
    elif scenario == "critical_news":
        at = datetime.fromisoformat(frozen["reference"]["generated_at"]) + timedelta(minutes=1)
        context["news"]["items"] = [{"id": "synthetic-critical-guidance",
            "published_at": at.isoformat(), "headline": context["symbol"] +
            ": la compañía recorta su previsión anual de ingresos un 35% y comunica riesgo material de liquidez.",
            "source": "synthetic evaluation fixture, not a real news claim"}]
        context["prepared_at"] = (at + timedelta(minutes=1)).isoformat()
    return context


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch-dir", type=Path, default=Path("logs/batch/2026-10-03/07-48-11"))
    parser.add_argument("--execute-luna", action="store_true")
    parser.add_argument("--symbol", default="ORCL")
    parser.add_argument("--scenario", choices=("unchanged", "routine_update", "critical_news"))
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    source = args.batch_dir.resolve() / "adaptive"
    work = root / "logs/adaptive_maintenance_evaluation" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")
    policy = {**load_policy(root), "routing_revision": 3}
    rows = []
    for directory in sorted(source.iterdir()):
        context = read_json(directory / "input.json")
        if not context:
            continue
        result = maintenance_precheck(context["reference"], context["slim"], context["reference"], owned=context["owned"])
        rows.append({"symbol": directory.name, **result,
            "itv": itv_state(context["reference"], owned=context["owned"], priority=context["tier"] == "priority",
                             now=datetime.fromisoformat(context["prepared_at"]), policy=policy)})
    route_summary = {"tickers": len(rows), "luna_first": sum(not row["guards"] and not row["itv"]["due"] for row in rows),
                     "direct_sol": sum(bool(row["guards"]) or row["itv"]["due"] for row in rows)}
    write_json(work / "routing_audit.json", {"summary": route_summary, "rows": rows})
    print(json.dumps(route_summary), flush=True)
    frozen = read_json(source / args.symbol / "input.json")
    baseline = read_json(source / args.symbol / "publish/output" / args.symbol / "latest.json")
    if not baseline or baseline.get("analysis_status") != "ok" or "sol" not in baseline.get("generation_model", ""):
        raise RuntimeError("valid_full_sol_fixture_required")
    frozen.update(reference=baseline, sol_reference=deepcopy(baseline), routing_revision=3,
                  evaluation_only=True, prepared_at=baseline["generated_at"])
    scenarios = (args.scenario,) if args.scenario else ("unchanged", "routine_update", "critical_news")
    contexts = {scenario: scenario_context(frozen, scenario) for scenario in scenarios}
    for scenario, context in contexts.items():
        precheck = maintenance_precheck(context["reference"], context["slim"], context["sol_reference"], owned=context["owned"])
        context.update(**precheck)
        context["itv"] = itv_state(context["sol_reference"], owned=context["owned"],
            priority=context["tier"] == "priority", now=datetime.fromisoformat(context["prepared_at"]), policy=policy)
        write_json(work / scenario / "context.json", context)
        write_json(work / scenario / "fixture_audit.json", {
            "evaluation_only": True, "published": False, "model_called": False,
            "scenario": scenario, "guards": precheck["guards"], "review_flags": precheck["review_flags"],
            "fixture": context.get("evaluation_fixture"),
            "reference_unchanged": context["reference"] == frozen["reference"],
            "sol_anchor_unchanged": context["sol_reference"] == frozen["sol_reference"],
        })
        if scenario == "routine_update" and precheck["guards"]:
            raise RuntimeError("routine_fixture_unexpected_hard_guard")
    if not args.execute_luna:
        print(str(work), flush=True)
        return
    check(root, policy)
    check_quota(read_codex_rate_limits(cwd=root))
    prefix = instructions(root)
    results = []
    def run(scenario):
        context = deepcopy(contexts[scenario])
        precheck = {key: context[key] for key in ("guards", "review_flags")}
        context = model_context(context)
        context.pop("research_memory", None)  # Match production Luna, not Sol's historical research bag.
        artifact = work / scenario
        receipt = call_codex(workspace=root / ".local/codex-analysis-workspace", artifacts=artifact, kind="triage",
            instructions=prefix, data=context, model=policy["triage_model"], effort=policy["triage_effort"],
            timeout=policy["triage_timeout_seconds"], schema=maintenance_schema(context), max_parallel=policy["max_model_parallel"])
        value = json.loads(receipt["text"])
        decision = maintenance_decision(value, precheck["guards"], context)
        result = {"scenario": scenario, "decision": decision, "reason": value["reason"], "usage": receipt["usage"],
                  "edits": len(value["edits"]), "model": receipt["model"], "risk": value["risk"]}
        result["passed"] = decision == {"unchanged":"retain", "routine_update":"update", "critical_news":"escalate"}[scenario]
        if decision == "update":
            try:
                normalization_audit = []
                candidate = apply_update(value, context, audit=normalization_audit)
                result["normalizations"] = normalization_audit
                validation = one.validate_markdown(candidate, authoritative_context=validation_context(context),
                    require_support_strengths=True, require_resistance=True, require_separate_scores=True)
                write_json(artifact / "validation.json", validation.to_dict())
                (artifact / "candidate.md").write_text(candidate, encoding="utf-8")
                result["candidate_valid"] = validation.ok
                result["candidate_sha256"] = hashlib.sha256(candidate.encode()).hexdigest()
                result["passed"] = result["passed"] and validation.ok
            except ValueError as exc:
                result.update(candidate_valid=False, error=str(exc), passed=False)
        write_json(artifact / "outcome.json", result)
        print(json.dumps(result, ensure_ascii=True), flush=True)
        return result
    with ThreadPoolExecutor(max_workers=min(3, policy["max_model_parallel"])) as pool:
        results = list(pool.map(run, scenarios))
    write_json(work / "summary.json", {"evaluation_only": True, "published": False, "results": results,
        "passed": all(result["passed"] for result in results)})
    print(str(work), flush=True)
    if not all(result["passed"] for result in results):
        raise SystemExit(1)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
