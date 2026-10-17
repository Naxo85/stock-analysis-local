"""Read-only descriptive check for the 2026-10-17 methodology audit.
No network, application imports, models, financial rescoring, or publication.
Run from repository root: .venv/Scripts/python.exe -B docs/audit_work_20261017/methodology_descriptive_check.py
"""
import hashlib
import json
from pathlib import Path

ROOT = Path.cwd()
BATCH = ROOT / "logs/batch/2026-10-16/15-58-24/adaptive"
SAVED = ROOT / "docs/audit_work_20261017/methodology_descriptive_cases.json"
record = json.loads(SAVED.read_text(encoding="utf-8"))
rows = []
missing = []
for ticker_dir in sorted(p for p in BATCH.iterdir() if p.is_dir()):
    inp = json.loads((ticker_dir / "input.json").read_text(encoding="utf-8"))
    published = ticker_dir / "publish/output" / ticker_dir.name / "latest.json"
    if not published.exists():
        missing.append(ticker_dir.name)
        continue
    payload = json.loads(published.read_text(encoding="utf-8"))
    for slot in ("entry", "ambitious_entry"):
        zone = payload["semantic_report"]["data"]["plan"][slot]
        if not zone.get("range") or not zone.get("strength", {}).get("components"):
            continue
        lower, upper = (zone["range"][k] for k in ("lower", "upper"))
        atr = inp["slim"]["technicals"]["atr10"]
        rows.append({
            "ticker": ticker_dir.name, "slot": slot,
            "width_pct": 100 * (upper-lower) / ((upper+lower)/2),
            "width_atr_current_review": (upper-lower)/atr,
            "components": zone["strength"]["components"],
        })

def describe(values):
    values = sorted(values)
    return dict(n=len(values), min=values[0],
                q25=values[int((len(values)-1)*.25)],
                median=values[int((len(values)-1)*.5)],
                q75=values[int((len(values)-1)*.75)], max=values[-1])

assert missing == record["summary"]["omitted"]
assert len(rows) == record["summary"]["active_zones"]
for key in ("width_pct", "width_atr_current_review"):
    actual = describe([r[key] for r in rows])
    expected = record["summary"][key]
    for k, v in actual.items():
        assert abs(v-expected[k]) < 1e-12, (key, k, v, expected[k])
for file, expected in record["original_sha256"].items():
    assert hashlib.sha256((ROOT/file).read_bytes()).hexdigest() == expected, file

print(json.dumps({
    "active_zones": len(rows),
    "entry": sum(r["slot"] == "entry" for r in rows),
    "washout": sum(r["slot"] == "ambitious_entry" for r in rows),
    "options_zero": sum(r["components"]["opciones"] == 0 for r in rows),
    "width_pct": describe([r["width_pct"] for r in rows]),
    "width_atr_current_review": describe([r["width_atr_current_review"] for r in rows]),
    "original_hashes_verified": len(record["original_sha256"]),
    "scope": "Descriptive only; no outcomes or financial policy changed"
}, ensure_ascii=False, indent=2))
