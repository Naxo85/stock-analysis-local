"""Read-only Codex authentication/model availability checks (no model turn)."""
from __future__ import annotations
import json
import os
import queue
import subprocess
import tempfile
import threading
import time
from pathlib import Path
from src.local_runner.codex_generator import require_codex
from src.local_runner.codex_rate_limits import _send_message, _read_until_response, _stop_app_server


def rpc(method: str, params: dict, root: Path) -> dict:
    # These requests do not start a turn or mutate an account. Reconnect once
    # on a transport failure instead of failing a ticker before model admission.
    attempts = 2 if method in {'account/read', 'account/rateLimits/read', 'model/list'} else 1
    for attempt in range(attempts):
        try:
            return _rpc_once(method, params, root)
        except (TimeoutError, RuntimeError) as exc:
            transient = isinstance(exc, TimeoutError) or str(exc).startswith('codex_app_server_closed_before_response:')
            if not transient or attempt + 1 == attempts:
                raise
            time.sleep(1)


def _rpc_once(method: str, params: dict, root: Path) -> dict:
    with tempfile.TemporaryFile(mode="w+", encoding="utf-8") as errors:
        process = subprocess.Popen([require_codex(), "app-server", "--stdio"], cwd=str(root),
                                   stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=errors,
                                   text=True, encoding="utf-8",
                                   creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        messages = queue.Queue()
        def collect():
            for line in process.stdout:
                messages.put(line)
            messages.put(None)
        threading.Thread(target=collect, daemon=True).start()
        lines = []
        try:
            _send_message(process, {"method": "initialize", "id": 1,
                                   "params": {"clientInfo": {"name": "stock_analysis_preflight", "version": "1.0"}}})
            _read_until_response(messages, lines, response_id=1, timeout=30)
            _send_message(process, {"method": "initialized", "params": {}})
            _send_message(process, {"method": method, "id": 2, "params": params})
            _read_until_response(messages, lines, response_id=2, timeout=30)
            return next(json.loads(line)["result"] for line in reversed(lines) if json.loads(line).get("id") == 2)
        finally:
            _stop_app_server(process)


def check(root: Path, policy: dict) -> dict:
    account = rpc("account/read", {"refreshToken": False}, root).get("account") or {}
    if account.get("type") != "chatgpt":
        raise RuntimeError("chatgpt_subscription_login_required_no_api")
    models, cursor = [], None
    for _ in range(10):
        page = rpc("model/list", {"limit": 100, "includeHidden": True, **({"cursor": cursor} if cursor else {})}, root)
        models.extend(page.get("data", []))
        cursor = page.get("nextCursor")
        if not cursor:
            break
    available = {m.get("model", m.get("id")): m for m in models}
    for role in ("triage", "report"):
        target = policy[f"{role}_model"]
        if target not in available:
            raise RuntimeError(f"configured_model_not_available_no_substitution: {target}")
        supported = available[target].get("supportedReasoningEfforts", [])
        if supported and policy[f"{role}_effort"] not in [s.get("reasoningEffort") for s in supported]:
            raise RuntimeError(f"configured_effort_not_available: {target}")
    return {"auth_type": account["type"], "models": [policy["triage_model"], policy["report_model"]]}


if __name__ == "__main__":
    import argparse
    from src.local_runner.adaptive_policy import load_policy
    root = Path.cwd()
    parser = argparse.ArgumentParser()
    parser.add_argument("--catalog", action="store_true")
    parser.add_argument("--local-data", action="store_true")
    args = parser.parse_args()
    if args.catalog:
        models = rpc("model/list", {"limit": 100, "includeHidden": True}, root).get("data", [])
        print(json.dumps([{k: m.get(k) for k in ("id", "model", "supportedReasoningEfforts", "serviceTiers")} for m in models]))
    elif args.local_data:
        from src.local_runner import run_one as one
        for ticker in ("CAT", "NVDA"):
            refpath = root / "output" / ticker / "latest.json"
            ref = json.loads(refpath.read_text(encoding="utf-8"))
            slim = one._load_latest_slim(root, ticker)
            news = one.load_recent_news(root, ticker)
            actions = one.load_recent_analyst_actions(root, ticker, since=ref.get("generated_at"), limit=1000)
            print(json.dumps({"ticker": ticker, "model": ref.get("generation_model"), "effort": ref.get("reasoning_effort"),
                              "report_at": ref.get("generated_at"), "slim_at": slim.get("as_of"),
                              "plan": ref.get("plan"), "reference_chars": len(json.dumps(ref)),
                              "slim_chars": len(json.dumps(slim)),
                              "news_metadata": {k:v for k,v in news.items() if k != "items"},
                              "analyst_metadata": {k:v for k,v in actions.items() if k != "actions"},
                              "prompt_chars": len(one._load_system_prompt(root))}, ensure_ascii=False))
    else:
        print(json.dumps(check(root, load_policy(root)), ensure_ascii=False))
