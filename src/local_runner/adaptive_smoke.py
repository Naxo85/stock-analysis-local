"""Explicit bounded, frozen-input evaluation. NEVER uploads or refreshes sources."""
from __future__ import annotations
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from src.local_runner import run_one as one
from src.local_runner.adaptive_policy import load_policy, triage_schema, triage_decision
from src.local_runner.adaptive_codex import call_codex, TRIAGE_INSTRUCTIONS, report_instructions
from src.local_runner.adaptive_budget import write_json, check_quota, read_codex_rate_limits
from src.local_runner.adaptive_preflight import rpc
from src.local_runner.adaptive_context import model_context, validation_context, unpack_model_context


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--execute-luna", action="store_true")
    mode.add_argument("--execute-sol", action="store_true")
    mode.add_argument("--audit-only", type=Path, help="Inspect saved smoke inputs locally, with zero model calls")
    parser.add_argument("--from-smoke", type=Path, help="Reuse exact frozen inputs, not current output files")
    parser.add_argument("--ticker", choices=("CAT", "NVDA"), help="Limit evaluation to one ticker")
    parser.add_argument("--allow-research", action="store_true", help="Allow Sol read-only public web research")
    args = parser.parse_args()
    if args.audit_only:
        for symbol in ("CAT", "NVDA"):
            path = args.audit_only / symbol / "triage.input.json"
            original = unpack_model_context(json.loads(path.read_text(encoding="utf-8")))
            compact = model_context(original)
            before, after = (len(json.dumps(value, ensure_ascii=False)) for value in (original, compact))
            print(json.dumps({"symbol": symbol, "input_chars_before": before, "input_chars_after": after,
                              "reduction_percent": round(100 * (1 - after / before), 1),
                              "same_market_snapshot": compact["comparison"]["same_market_snapshot"]}))
        return
    root = Path.cwd()
    policy = load_policy(root)
    account = rpc("account/read", {"refreshToken": False}, root).get("account") or {}
    if account.get("type") != "chatgpt":
        raise RuntimeError("chatgpt_login_required")
    work = root / "logs" / "adaptive_smoke" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")
    kind = "report" if args.execute_sol else "triage"
    if args.allow_research and not args.execute_sol:
        parser.error("--allow-research requires --execute-sol")
    instructions = report_instructions(one._load_system_prompt(root), research=args.allow_research) if args.execute_sol else TRIAGE_INSTRUCTIONS
    outcomes = []
    for symbol in ((args.ticker,) if args.ticker else ("CAT", "NVDA")):
        check_quota(read_codex_rate_limits(cwd=root))
        ref = json.loads((root / "output" / symbol / "latest.json").read_text(encoding="utf-8"))
        slim = one._load_latest_slim(root, symbol)
        data = {"evaluation_only": True, "symbol": symbol, "prepared_at": slim.get("as_of"),
                "reference": ref, "slim": slim, "guards": [],
                "news": one.load_recent_news(root, symbol),
                "analyst_actions": one.load_recent_analyst_actions(root, symbol, since=ref.get("generated_at"), limit=None)}
        if args.from_smoke:
            data = unpack_model_context(json.loads((args.from_smoke / symbol / "triage.input.json").read_text(encoding="utf-8")))
        data = model_context(data)
        if args.allow_research:
            data["prepared_at"] = datetime.now(timezone.utc).isoformat()
        print(f"Starting {kind} {symbol}; evaluation only", flush=True)
        result = call_codex(workspace=root / ".local" / "codex-analysis-workspace", artifacts=work / symbol,
                            kind=kind, instructions=instructions, data=data,
                            model=policy[f"{kind}_model"], effort=policy[f"{kind}_effort"],
                            timeout=policy[f"{kind}_timeout_seconds"], schema=None if args.execute_sol else triage_schema(data),
                            research=args.allow_research)
        if args.execute_sol:
            markdown = one.normalize_report_dates(result["text"])
            validation = one.validate_markdown(markdown, authoritative_context=validation_context(data),
                require_support_strengths=True, require_resistance=True, require_separate_scores=True)
            write_json(work / symbol / "validation.json", validation.to_dict())
            decision = "valid_report" if validation.ok else "invalid_report"
        else:
            decision = triage_decision(json.loads(result["text"]), [], data)
        outcomes.append({"symbol": symbol, "decision": decision, **{k:v for k,v in result.items() if k != "text"}})
        print(json.dumps(outcomes[-1]), flush=True)
    write_json(work / "summary.json", {"evaluation_only": True, "results": outcomes})
    print(f"Saved {work / 'summary.json'}; no publication", flush=True)


if __name__ == "__main__":
    main()
