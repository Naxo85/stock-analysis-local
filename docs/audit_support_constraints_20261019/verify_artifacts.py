"""Validate local audit links/JSON and the original corpus hashes; no network."""
import hashlib
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

result = {"json_files": 0, "local_links_checked": 0, "original_hashes_checked": 0, "errors": []}
for p in HERE.rglob("*.json"):
    if p.name in ("verification.json", "INDEX.sha256.json"):
        continue
    json.loads(p.read_text(encoding="utf-8"))
    result["json_files"] += 1
for p in HERE.rglob("*.md"):
    for target in re.findall(r"\[[^\]]+\]\(([^\s)]+)\)", p.read_text(encoding="utf-8")):
        if target.startswith(("https://", "http://", "codex://")):
            continue
        target = re.sub(r":\d+$", "", target.split("#", 1)[0])
        dest = (p.parent/target).resolve()
        result["local_links_checked"] += 1
        if not dest.exists():
            result["errors"].append({"file": str(p.relative_to(ROOT)), "missing_link": target})
census = json.loads((HERE/"weights/census.json").read_text(encoding="utf-8"))
for item in census["files"]:
    path = ROOT/item["path"]
    result["original_hashes_checked"] += 1
    if sha(path) != item["sha256"]:
        result["errors"].append({"original_changed": item["path"]})
result["ok"] = not result["errors"]
(HERE/"verification.json").write_text(json.dumps(result, indent=2)+"\n", encoding="utf-8")
manifest = {str(p.relative_to(HERE)): sha(p) for p in sorted(HERE.rglob("*")) if p.is_file() and p.name != "INDEX.sha256.json" and "__pycache__" not in p.parts}
(HERE/"INDEX.sha256.json").write_text(json.dumps(manifest, indent=2)+"\n", encoding="utf-8")
print(json.dumps(result, indent=2))
raise SystemExit(0 if result["ok"] else 1)
