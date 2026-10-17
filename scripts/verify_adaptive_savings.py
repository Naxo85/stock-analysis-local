"""Offline verification of real saved v3 responses and lossless input savings."""
import argparse
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.local_runner.adaptive_context import model_context, serialize_model_input, unpack_model_context
from src.local_runner.adaptive_policy import triage_decision
from src.local_runner.adaptive_budget import read_json, write_json


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--evaluation-dir", type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    results, measurements = [], []
    for scenario in ("unchanged", "broken_support"):
        work = args.evaluation_dir / scenario
        data = unpack_model_context(read_json(work / "triage.input.json"))
        verdict = read_json(work / "triage.response")
        receipt = read_json(work / "triage.receipt.json")
        decision = triage_decision(verdict, data["guards"], data)
        expected = "retain" if scenario == "unchanged" else "escalate"
        assert decision == expected and receipt["exit_code"] == 0
        results.append({"scenario": scenario, "decision": decision, "passed": True,
                        "usage": receipt["usage"], "reason": verdict["reason"]})
    for ticker in ("CAT", "NVDA"):
        original = read_json(root / "logs/adaptive_smoke/20261001T111917974635" / ticker / "triage.input.json")
        context = model_context(original)
        serialized = serialize_model_input(context)
        assert unpack_model_context(json.loads(serialized)) == context
        before = len(json.dumps(context, ensure_ascii=False))
        measurements.append({"ticker": ticker, "before_chars": before, "after_chars": len(serialized),
                             "reduction_percent": round(100 * (1 - len(serialized) / before), 2),
                             "lossless_roundtrip": True})
    audit = {"evaluation_only": True, "no_publication": True, "results": results,
             "input_measurements": measurements,
             "note": "Character savings are not measured token or subscription quota discounts."}
    write_json(args.evaluation_dir / "summary.json", audit)
    print(json.dumps(audit, ensure_ascii=True))


if __name__ == "__main__":
    main()
