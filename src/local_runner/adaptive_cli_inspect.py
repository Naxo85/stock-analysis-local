"""Read-only CLI help inspection; never starts a model turn."""
import subprocess
import argparse
import json
from pathlib import Path
from src.local_runner.codex_generator import require_codex

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--prompt-summary", action="store_true")
    args = parser.parse_args()
    executable = require_codex()
    print(executable, flush=True)
    if args.prompt_summary:
        root = Path.cwd()
        result = subprocess.run([executable, "debug", "prompt-input",
            "-c", 'project_doc_max_bytes=0', "-c", 'skills.max_context_tokens=1',
            "-c", 'apps._default.enabled=false', "-c", 'features.remote_plugin=false',
            "-c", 'features.memories=false', "-c", 'features.shell_tool=false',
            "-c", 'features.multi_agent=false', "-c", 'web_search="disabled"',
            "-c", 'model="gpt-6-luna"',
            "-c", "model_instructions_file=" + json.dumps(str(root / "prompts/daily_triage.md")),
            "Audit only; no model call"], cwd=root / ".local/codex-analysis-workspace",
            capture_output=True, text=True, encoding="utf-8", timeout=60)
        if result.returncode:
            raise RuntimeError(result.stderr[-2000:])
        parsed = json.loads(result.stdout)
        print(json.dumps({"type": type(parsed).__name__, "chars": len(result.stdout),
                          "keys": list(parsed) if isinstance(parsed, dict) else None}))
        for item in parsed if isinstance(parsed, list) else parsed.get("input", []):
            print(json.dumps({"role": item.get("role"), "type": item.get("type"),
                              "chars": len(json.dumps(item)), "keys": list(item)}))
        raise SystemExit(0)
    for args in (("--version",), ("exec", "--help"), ("debug", "prompt-input", "--help")):
        subprocess.run([executable, *args], check=True)
