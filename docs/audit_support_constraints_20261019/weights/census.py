"""Read-only descriptive audit. No model, acquisition, publication or score edits."""
import hashlib
import json
import statistics
import sys
from collections import Counter
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).parent
COMPONENTS = ("estructura", "volumen", "opciones", "confluencia", "durabilidad")
BATCHES = [
    "2026-10-13/19-30-44", "2026-10-14/16-07-07",
    "2026-10-15/12-01-08", "2026-10-16/15-58-24", "2026-10-18/09-08-40",
]
receipts = []

def read(path):
    payload = path.read_bytes()
    receipts.append({"path": str(path.relative_to(ROOT)), "sha256": hashlib.sha256(payload).hexdigest()})
    return json.loads(payload.decode("utf-8-sig"))

def zones(state, symbol):
    doc = state["semantic_report"]["data"]
    result = []
    for slot in ("entry", "ambitious_entry"):
        block = doc["plan"][slot]
        if not block.get("range"):
            continue
        parts = block["strength"]["components"]
        result.append({
            "symbol": symbol, "slot": slot, "range": block["range"],
            "components": parts, "total": sum(parts.values()),
            "factors": block["strength"]["factors"],
            "generated_at": state["generated_at"],
        })
    return result

def summary(rows):
    return {
        "zones": len(rows), "tickers_with_zones": len({z["symbol"] for z in rows}),
        "threshold_counts": {n: sum(z["total"] >= n for z in rows) for n in (50,55,60,65,70,75,85)},
        "mean_total": statistics.mean(z["total"] for z in rows),
        "mean_components": {c: statistics.mean(z["components"][c] for z in rows) for c in COMPONENTS},
        "zero_components": {c: sum(z["components"][c] == 0 for z in rows) for c in COMPONENTS},
        "histogram_by_five": dict(sorted(Counter(z["total"]//5*5 for z in rows).items())),
    }

snapshots = {}
summaries = []
for name in BATCHES:
    files = sorted((ROOT/"logs/batch"/name/"adaptive").glob("*/publish/current_state.json"))
    rows = [z for p in files for z in zones(read(p), p.parents[1].name)]
    snapshots[name] = rows
    summaries.append({"batch": name, "published_reports": len(files), **summary(rows)})

def identity(z):
    return (z["symbol"], z["range"]["lower"], z["range"]["upper"])

def compare(a, b):
    left = {identity(z): z for z in a}; right = {identity(z): z for z in b}
    same = []
    for key in sorted(set(left)&set(right)):
        x, y = left[key], right[key]
        same.append({
            "symbol": y["symbol"], "range": y["range"], "slot_before": x["slot"], "slot_after": y["slot"],
            "before": x["components"], "after": y["components"],
            "delta": {c: y["components"][c]-x["components"][c] for c in COMPONENTS},
            "total_before": x["total"], "total_after": y["total"],
        })
    removed = [left[k] for k in sorted(set(left)-set(right))]
    added = [right[k] for k in sorted(set(right)-set(left))]
    return {
        "identity": "exact ticker and numeric range, independent of slot; changed geometry is unmatched, not automatically different economic support",
        "matched": same, "matched_count": len(same),
        "matched_components_unchanged": sum(x["before"] == x["after"] for x in same),
        "matched_sum_deltas": {c: sum(x["delta"][c] for x in same) for c in COMPONENTS},
        "removed": removed, "added": added,
        "visible_decomposition": {
            "matched_before": sum(x["total_before"]>=65 for x in same),
            "matched_after": sum(x["total_after"]>=65 for x in same),
            "removed": sum(x["total"]>=65 for x in removed),
            "added": sum(x["total"]>=65 for x in added),
        },
    }

current = snapshots[BATCHES[-1]]
before18 = []
for p in sorted((ROOT/"logs/batch"/BATCHES[-1]/"adaptive").glob("*/input.json")):
    before18.extend(zones(read(p)["reference"], p.parent.name))

groups = {}
for label, fn in [
    ("zero_options", lambda z: z["components"]["opciones"]==0),
    ("positive_options", lambda z: z["components"]["opciones"]>0),
    ("zero_volume", lambda z: z["components"]["volumen"]==0),
    ("zero_options_and_volume", lambda z: z["components"]["opciones"]==0 and z["components"]["volumen"]==0),
]:
    rows = [z for z in current if fn(z)]
    groups[label] = {**summary(rows), "symbols_slots": [f"{z['symbol']}/{z['slot']}" for z in rows], "max_score": max(z["total"] for z in rows)}

result = {
    "scope": "Historical published artifacts only. No claims about live state, profitability, calibrated scores or optimal weights. Observations are dependent and include dated inherited components.",
    "batches": summaries,
    "same_range_14_to_18": compare(snapshots[BATCHES[1]], current),
    "exact_reference_to_18": compare(before18, current),
    "current_groups": groups,
    "current_zones": current,
    "mechanical_sensitivity_only": {
        "warning": "These are arithmetic diagnostics, not model counterfactuals. Renormalizing changes scale and invalidates the old threshold semantics; no variant is evaluated by outcomes.",
        "published_ge65": sum(z["total"]>=65 for z in current),
        "subtract_options_keep65": sum(z["total"]-z["components"]["opciones"]>=65 for z in current),
        "non_options_rescaled_100_over75_ge65": sum((z["total"]-z["components"]["opciones"])*100/75>=65 for z in current),
    },
    "files": receipts,
}
(OUT/"census.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps({
    "batches": summaries,
    "matched14": {k:v for k,v in result["same_range_14_to_18"].items() if k not in ("matched","removed","added")},
    "matched18": {k:v for k,v in result["exact_reference_to_18"].items() if k not in ("matched","removed","added")},
    "groups": groups,
    "sensitivity": result["mechanical_sensitivity_only"],
},ensure_ascii=False,indent=2))
