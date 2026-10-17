"""Adaptive pipeline stages; frozen inputs, staged reports, no browser fallback."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import os
from copy import deepcopy
from datetime import datetime, timezone, timedelta
from pathlib import Path

from src.local_runner import run_one as one
from src.local_runner.adaptive_budget import read_json, write_json, reserve, finish
from src.local_runner.adaptive_codex import call_codex, TRIAGE_INSTRUCTIONS, report_instructions, retryable_failure
from src.local_runner.adaptive_context import model_context, validation_context, serialize_model_input
from src.local_runner.adaptive_cache import triage_key, load_triage, save_triage, load_research, save_research
from src.local_runner.adaptive_policy import load_policy, itv_state, safeguards, legacy_safeguards, routing_precheck, timestamp, triage_decision, triage_schema, number, require_activation
from src.local_runner.adaptive_policy import maintenance_precheck, daily_decision
from src.local_runner.adaptive_current import load_current_report, current_uri
from src.local_runner.adaptive_cache import reference_key
from src.local_runner.adaptive_news_research import (
    news_research_enabled, news_research_instructions, attach_news_research,
)
from src.local_runner.analysis_state import load_reference_payload, save_reference_payload, _exclusive_read_lock, _read_json_gcs
from src.local_runner.gcs_uploader import require_gcloud, TEST_BUCKET, SHEET_REPORT_MIRROR_BUCKET, SHEET_REPORT_MIRROR_PREFIX
from src.local_runner.process_control import run_bounded


def prepare(root: Path, work: Path, symbol: str, owned: bool, tier: str, *, ownership=None) -> None:
    previous = read_json(work / "input.json")
    if previous:
        failure = read_json(work / "failure.json")
        message = str(failure.get("error_message") or "")
        refreshable = message.startswith(("news_coverage_gap_since_full_report", "missing_support_data",
            "stale_or_missing_", "stale_source_no_model_call", "incomplete_source_no_model_call"))
        # Once ANY model admission exists, its input is immutable even if a
        # crash left no response/receipt. Refresh only pre-model data failures.
        batch = work.parent.parent if work.parent.name == "adaptive" else work.parent
        ledger = read_json(batch / "codex_budget.json")
        reserved = any(key.startswith(symbol + ":") for key in ledger.get("calls", {}))
        if (not refreshable or reserved or any(work.glob("*.receipt.json"))
                or any(work.glob("*.response")) or (work / "review.json").exists()):
            return
    now = datetime.now(timezone.utc)
    policy = load_policy(root)
    ref = load_reference_payload(symbol) or {}
    anchor = ref
    if policy.get("routing_revision", 1) >= 3 and ref:
        ref = load_current_report(root, symbol, anchor)
    if policy.get('routing_revision', 1) >= 23:
        from src.local_runner.technical_preparation import avwap_anchors, require_capture
        anchors = avwap_anchors(ref, anchor)
        directed = {}
        if policy.get('routing_revision', 1) >= 39:
            from src.local_runner.technical_preparation import option_origins, require_option_origins
            directed['option_origins'] = option_origins(ref)
        slim = one._fetch_slim(symbol, avwap_anchors=anchors, **directed)
        require_capture(slim, anchors)
        if directed:
            require_option_origins(slim, directed['option_origins'])
    else:
        slim = one._fetch_slim(symbol)
    context = {
        "symbol": symbol, "prepared_at": now.isoformat(), "owned": owned, "tier": tier,
        "reference": ref, "slim": slim,
        "analyst_quality": one._load_analyst_quality(root, symbol, slim, now=now),
        "analyst_summary": one.load_compact_analyst_summary(root, symbol),
        "analyst_actions": one.load_recent_analyst_actions(root, symbol,
            since=anchor.get("generated_at") or (now-timedelta(days=30)).isoformat(), limit=None),
        "news": one.load_recent_news(root, symbol),
    }
    if policy.get("routing_revision", 1) >= 3:
        context.update(sol_reference=anchor, routing_revision=policy["routing_revision"])
    if ownership is not None:
        context['ownership'] = deepcopy(ownership)
    if _news_gap(context):
        # The source pipeline used canonical latest, which can be newer than
        # the full reference. Backfill the real missing interval, never simply
        # relabel the source's window or allow Luna to retain with a gap.
        start = timestamp(anchor["generated_at"]) - timedelta(hours=24)
        completed = run_bounded([sys.executable, "-m", "src.local_runner.update_ibkr_news_batch",
            "--tickers", symbol, "--since", start.isoformat(), "--client-id-base",
            str(19000 + os.getpid() % 10000)], cwd=str(root), stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace", timeout=240,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        write_json(work / "news_backfill.json", {"since": start.isoformat(), "exit_code": completed.returncode,
            "stdout": completed.stdout, "stderr": completed.stderr})
        if completed.returncode:
            raise RuntimeError("news_coverage_gap_since_full_report: backfill_failed")
        context["news"] = one.load_recent_news(root, symbol)
        if _news_gap(context):
            raise RuntimeError("news_coverage_gap_since_full_report: backfill_incomplete")
    # Do not freeze a partial slim/source result as a successful preparation.
    data_ready(context, policy, now)
    memory = load_research(root, symbol, anchor)
    if memory:
        context["research_memory"] = memory
    if previous:
        write_json(work / "input_history" / (now.strftime("%Y%m%dT%H%M%S%f") + ".json"), previous)
    write_json(work / "input.json", context)
    (work / "instructions.md").write_text(one._load_system_prompt(root), encoding="utf-8")
    if policy.get('routing_revision', 1) >= 9:
        suffix = '_v6' if policy.get('routing_revision', 1) >= 14 else '_v5' if policy.get('routing_revision', 1) >= 13 else '_v4' if policy.get('routing_revision', 1) >= 12 else '_v3' if policy.get('routing_revision', 1) >= 11 else '_v2' if policy.get('routing_revision', 1) >= 10 else ''
        daily_path = ('prompts/daily_maintenance_semantic_v23.md' if policy.get('routing_revision', 1) >= 23
                      else 'prompts/daily_maintenance_semantic_v22.md' if policy.get('routing_revision', 1) >= 22
                      else 'prompts/daily_maintenance_semantic_v21.md' if policy.get('routing_revision', 1) >= 21
                      else 'prompts/daily_maintenance_semantic_v20.md' if policy.get('routing_revision', 1) >= 20
                      else 'prompts/daily_maintenance_semantic' + suffix + '.md')
        daily = (root / daily_path).read_text(encoding='utf-8')
        financial = (root / ('prompts/stock_analysis_semantic' + suffix + '.md')).read_text(encoding='utf-8')
        contract = (root / ('prompts/semantic_report_contract' + suffix + '.md')).read_text(encoding='utf-8')
        if policy.get('routing_revision', 1) >= 15:
            contract += '\n\n' + (root / 'prompts/adaptive_revision15.md').read_text(encoding='utf-8')
        if policy.get('routing_revision', 1) >= 16:
            contract += '\n\n' + (root / 'prompts/adaptive_revision16.md').read_text(encoding='utf-8')
        if policy.get('routing_revision', 1) >= 17:
            contract += '\n\n' + (root / 'prompts/report_reader_style.md').read_text(encoding='utf-8')
        if policy.get('routing_revision', 1) >= 18:
            revision_prompt = ('adaptive_revision20.md' if policy.get('routing_revision', 1) >= 20 else
                               'adaptive_revision19.md' if policy.get('routing_revision', 1) >= 19 else 'adaptive_revision18.md')
            contract += '\n\n' + (root / 'prompts' / revision_prompt).read_text(encoding='utf-8')
        if policy.get('routing_revision', 1) >= 20:
            # One complete current contract, not conflicting historical overlays.
            # Frozen preparations <=19 still follow the exact construction above.
            contract = (root / 'prompts/report_reader_style.md').read_text(encoding='utf-8')
            contract += '\n\n' + (root / 'prompts/adaptive_revision20.md').read_text(encoding='utf-8')
        if policy.get('routing_revision', 1) >= 21:
            contract = (root / 'prompts/report_reader_style.md').read_text(encoding='utf-8')
            contract += '\n\n' + (root / 'prompts/adaptive_revision21.md').read_text(encoding='utf-8')
        if policy.get('routing_revision', 1) >= 22:
            contract = (root / 'prompts/report_reader_style.md').read_text(encoding='utf-8')
            contract += '\n\n' + (root / 'prompts/adaptive_revision22.md').read_text(encoding='utf-8')
        if policy.get('routing_revision', 1) >= 23:
            contract = (root / 'prompts/report_reader_style.md').read_text(encoding='utf-8')
            contract += '\n\n' + (root / 'prompts/adaptive_revision23.md').read_text(encoding='utf-8')
        if policy.get('routing_revision', 1) >= 24:
            contract += '\n\n' + (root / 'prompts/no_trade_stop_v24.md').read_text(encoding='utf-8')
        if policy.get('routing_revision', 1) >= 25:
            contract += '\n\n' + (root / 'prompts/volume_arithmetic_v25.md').read_text(encoding='utf-8')
        if policy.get('routing_revision', 1) >= 26:
            contract += '\n\n' + (root / 'prompts/stable_evidence_v26.md').read_text(encoding='utf-8')
        if policy.get('routing_revision', 1) >= 27:
            contract += '\n\n' + (root / 'prompts/evidence_direction_v27.md').read_text(encoding='utf-8')
        if policy.get('routing_revision', 1) >= 28:
            contract += '\n\n' + (root / 'prompts/support_viability_v28.md').read_text(encoding='utf-8')
            contract += '\n\n' + (root / 'prompts/executive_brief_v28.md').read_text(encoding='utf-8')
        if policy.get('routing_revision', 1) >= 29:
            # Replace obsolete instructions; do not append contradictory stop
            # and dual-resistance obligations to the new three-field contract.
            daily = (root / 'prompts/daily_maintenance_semantic_v29.md').read_text(encoding='utf-8')
            financial = (root / 'prompts/stock_analysis_semantic_v7.md').read_text(encoding='utf-8')
            contract = '\n\n'.join((root / 'prompts' / name).read_text(encoding='utf-8')
                for name in ('report_reader_style_v29.md', 'adaptive_revision29.md',
                             'volume_arithmetic_v25.md', 'evidence_direction_v27.md'))
        if policy.get('routing_revision', 1) >= 30:
            # Reader/audit separation is versioned: never rewrite frozen 29 inputs.
            daily = (root / 'prompts/daily_maintenance_semantic_v30.md').read_text(encoding='utf-8')
            financial = (root / 'prompts/stock_analysis_semantic_v8.md').read_text(encoding='utf-8')
            contract = '\n\n'.join((root / 'prompts' / name).read_text(encoding='utf-8')
                for name in ('adaptive_revision30.md', 'volume_arithmetic_v25.md',
                             'evidence_direction_v27.md', 'report_reader_style_v30.md'))
        if policy.get('routing_revision', 1) >= 31:
            contract += '\n\n' + (root / 'prompts/strength_evidence_v31.md').read_text(encoding='utf-8')
        if policy.get('routing_revision', 1) >= 32:
            reader_name = 'reader_report_v33.md' if policy.get('routing_revision', 1) >= 33 else 'reader_report_v32.md'
            contract += '\n\n' + (root / 'prompts' / reader_name).read_text(encoding='utf-8')
        if policy.get('routing_revision', 1) >= 33:
            financial = (root / 'prompts/stock_analysis_semantic_v9.md').read_text(encoding='utf-8')
            contract += '\n\n' + (root / 'prompts/catalyst_editorial_v33.md').read_text(encoding='utf-8')
        if policy.get('routing_revision', 1) >= 34:
            financial = (root / 'prompts/stock_analysis_semantic_v10.md').read_text(encoding='utf-8')
            contract += '\n\n' + (root / 'prompts/volume_rubric_v34.md').read_text(encoding='utf-8')
        if policy.get('routing_revision', 1) >= 35:
            daily = (root / 'prompts/daily_maintenance_semantic_v35.md').read_text(encoding='utf-8')
            financial = (root / 'prompts/stock_analysis_semantic_v11.md').read_text(encoding='utf-8')
            contract = '\n\n'.join((root / 'prompts' / name).read_text(encoding='utf-8')
                for name in ('adaptive_revision35.md', 'volume_arithmetic_v25.md',
                             'evidence_direction_v27.md', 'report_reader_style_v35.md',
                             'strength_evidence_v31.md', 'reader_report_v35.md',
                             'catalyst_editorial_v33.md', 'volume_rubric_v34.md'))
        if policy.get('routing_revision', 1) >= 38:
            financial = (root / 'prompts/stock_analysis_semantic_v12.md').read_text(encoding='utf-8')
        if policy.get('routing_revision', 1) >= 36:
            validity_name = 'support_validity_v37.md' if policy['routing_revision'] >= 37 else 'support_validity_v36.md'
            contract += '\n\n' + (root / 'prompts' / validity_name).read_text(encoding='utf-8')
        if policy.get('routing_revision', 1) >= 39:
            contract += '\n\n' + (root / 'prompts/option_origins_v39.md').read_text(encoding='utf-8')
        daily += '\n\nFINANCIAL POLICY AND RUBRIC:\n' + financial
        daily += '\n\n' + contract
        # Freeze the semantic Sol policy just like legacy instructions.
        (work / 'instructions.md').write_text(financial + '\n\n' + contract, encoding='utf-8')
    elif policy.get("routing_revision", 1) >= 3:
        daily = (root / "prompts/daily_maintenance.md").read_text(encoding="utf-8")
        daily += "\n\nAUTHORITATIVE REPORT FORMAT AND RUBRIC (news web access requires explicit enabled footer):\n" + one._load_system_prompt(root)
        from src.local_runner.adaptive_context import MAINTENANCE_OVERRIDE
        daily += MAINTENANCE_OVERRIDE
    else:
        daily = TRIAGE_INSTRUCTIONS
    (work / "triage_instructions.md").write_text(daily, encoding="utf-8")
    write_json(work / "policy.json", policy)


def _news_gap(context: dict) -> bool:
    reference_at = timestamp((context.get("sol_reference") or context.get("reference") or {}).get("generated_at"))
    news_start = timestamp(((context.get("news") or {}).get("window") or {}).get("start"))
    return bool(reference_at and (news_start is None or news_start > reference_at + timedelta(minutes=1)))


def data_ready(context: dict, policy: dict, now: datetime) -> None:
    if context.get('routing_revision', 1) >= 28:
        from src.local_runner.technical_preparation import require_price_history
        require_price_history(context.get('slim') or {})
    if context.get('routing_revision', 1) >= 23:
        from src.local_runner.technical_preparation import avwap_anchors, require_capture
        require_capture(context.get('slim') or {}, avwap_anchors(context.get('reference'), context.get('sol_reference')))
    if context.get('routing_revision', 1) >= 39:
        from src.local_runner.technical_preparation import option_origins, require_option_origins
        require_option_origins(context.get('slim') or {}, option_origins(context.get('reference')))
    if context.get("routing_revision", 1) >= 3:
        for name in ("slim", "news", "analyst_actions"):
            if not isinstance(context.get(name), dict):
                raise RuntimeError(f"incomplete_source_no_model_call: {name}_object")
        if not isinstance(context["slim"].get("levels"), dict):
            raise RuntimeError("invalid_current_support_data")
        supports = context["slim"]["levels"].get("supports")
        if not isinstance(supports, list) or not supports or any(
                not isinstance(item, dict) or isinstance(item.get("level"), bool)
                or not isinstance(item.get("level"), (int, float))
                or number(item["level"]) is None or item["level"] <= 0 for item in supports):
            raise RuntimeError("invalid_current_support_data")
        for name, field in (("news", "items"), ("analyst_actions", "actions")):
            items = context[name].get(field)
            if not isinstance(items, list) or any(not isinstance(item, dict) for item in items):
                raise RuntimeError(f"incomplete_source_no_model_call: {name}_{field}")
    prepared = timestamp(context.get("prepared_at"))
    slim_at = timestamp(context["slim"].get("as_of"))
    for name, at in (("prepared", prepared), ("slim", slim_at)):
        if at is None or not -300 <= (now-at).total_seconds() <= policy["max_snapshot_age_hours"]*3600:
            raise RuntimeError(f"stale_or_missing_{name}_timestamp")
    if number(context["slim"].get("latest_price")) is None:
        raise RuntimeError("missing_latest_price")
    if not context["slim"].get("levels", {}).get("supports"):
        raise RuntimeError("missing_support_data")
    for name in ("news", "analyst_actions"):
        source = context[name]
        if source.get("status") != "ok" or source.get("truncated"):
            raise RuntimeError(f"incomplete_source_no_model_call: {name}")
        source_at = timestamp(source.get("generated_at") or source.get("as_of"))
        if source_at is None or not -300 <= (now-source_at).total_seconds() <= policy["max_snapshot_age_hours"]*3600:
            raise RuntimeError(f"stale_source_no_model_call: {name}")
    if _news_gap(context):
        raise RuntimeError("news_coverage_gap_since_full_report")
    if context.get("routing_revision", 1) >= 3:
        if number(context["slim"].get("latest_price")) <= 0:
            raise RuntimeError("invalid_positive_latest_price")
        supports = context["slim"]["levels"]["supports"]
        if not isinstance(supports, list) or not any(isinstance(v, dict) and
                number(v.get("level")) is not None and v["level"] > 0 for v in supports):
            raise RuntimeError("invalid_current_support_data")
        for name, field in (("news", "items"), ("analyst_actions", "actions")):
            if not isinstance(context[name].get(field), list):
                raise RuntimeError(f"incomplete_source_no_model_call: {name}_{field}")
        for name in ("reference", "sol_reference"):
            reference = context.get(name) or {}
            if reference and reference.get("symbol", context["symbol"]) != context["symbol"]:
                raise RuntimeError("reference_symbol_mismatch")
            at = timestamp(reference.get("generated_at"))
            if at and (at-now).total_seconds() > 300:
                raise RuntimeError("reference_timestamp_in_future")


def model_call(root: Path, work: Path, symbol: str, budget: Path, policy: dict,
               kind: str, context: dict, *, itv: bool = False, reuse_only: bool = False) -> dict:
    if kind not in {"triage", "triage_repair", "report"}:
        raise ValueError("unsupported_model_call_kind")
    model_kind = "triage" if kind == "triage_repair" else kind
    context = model_context(context)
    if model_kind == "triage":
        context.pop("research_memory", None)  # Sol's research history is not relevance input.
    research = ((kind == "report" and policy.get("report_web_research_enabled", False))
                or (model_kind == "triage" and news_research_enabled(policy)))
    instructions = (work / "triage_instructions.md").read_text(encoding="utf-8") if model_kind == "triage" else report_instructions(
        (work / "instructions.md").read_text(encoding="utf-8"), research=research,
        semantic=policy.get('routing_revision', 1) >= 9)
    if model_kind == "triage":
        instructions = news_research_instructions(instructions, enabled=research, revision=policy.get('routing_revision', 1))
    if model_kind == "triage" and policy.get("routing_revision", 1) >= 3:
        from src.local_runner.adaptive_maintenance import maintenance_schema
        schema = maintenance_schema(context)
    else:
        schema = triage_schema(context) if model_kind == "triage" else None
    if model_kind == 'report' and policy.get('routing_revision', 1) >= 9:
        from src.local_runner.semantic_report import report_schema
        schema = report_schema(policy.get('routing_revision', 9))
        instructions += '\n\nOUTPUT AUTHORITY: return ONLY the full semantic report JSON schema, never Markdown. '
        instructions += 'All narrative/rubric instructions above refer to financial content, not output syntax.'
    response_path = work / f"{kind}.response"
    receipt_path = work / f"{kind}.receipt.json"
    receipt = read_json(receipt_path)
    if response_path.exists() and receipt.get("exit_code") == 0 and receipt.get("usage"):
        if receipt.get("cache_reused") and receipt.get("cache_key") != triage_key(
                context, policy, instructions, schema, datetime.now(timezone.utc)):
            raise RuntimeError("cached_verdict_expired_refresh_input")
        expected_input = hashlib.sha256(serialize_model_input(context).encode("utf-8")).hexdigest()
        if receipt.get("input_sha256") != expected_input:
            raise RuntimeError("model_receipt_context_mismatch_no_automatic_retry")
        expected_prefix = hashlib.sha256(instructions.encode()).hexdigest()
        expected_schema = hashlib.sha256(json.dumps(schema, sort_keys=True).encode()).hexdigest()
        if (receipt.get("instructions_sha256") != expected_prefix or receipt.get("schema_sha256") != expected_schema
                or receipt.get("research_enabled", False) != research
                or receipt.get("model") != policy[f"{model_kind}_model"]
                or receipt.get("reasoning_effort") != policy[f"{model_kind}_effort"]):
            raise RuntimeError("model_receipt_contract_mismatch_no_automatic_retry")
        # Recovery after a crash between model completion and checkpoint write.
        ledger = read_json(budget)
        key = f"{symbol}:{kind}"
        if key in ledger.get("calls", {}) and ledger["calls"][key]["status"] == "reserved":
            finish(budget, key, receipt=receipt)
        return {**receipt, "text": response_path.read_text(encoding="utf-8")}
    if reuse_only:
        raise RuntimeError('recovery_requires_existing_successful_receipt_no_model_call')
    cache_key = triage_key(context, policy, instructions, schema, datetime.now(timezone.utc)) if kind == "triage" else None
    # An ambiguous existing reservation must be diagnosed, never hidden by cache.
    reserved = f"{symbol}:{kind}" in read_json(budget).get("calls", {})
    cached = load_triage(root, symbol, cache_key, context) if cache_key and not reserved else None
    if cached:
        origin = cached["receipt"]
        if (origin.get("model") != policy["triage_model"]
                or origin.get("reasoning_effort") != policy["triage_effort"]
                or origin.get("instructions_sha256") != hashlib.sha256(instructions.encode()).hexdigest()
                or origin.get("schema_sha256") != hashlib.sha256(json.dumps(schema, sort_keys=True).encode()).hexdigest()
                or origin.get("research_enabled", False) != research
                or (research and origin.get("web_search_count") != 0)):
            cached = None
    if cached:
        result = {**cached["receipt"], "text": cached["text"], "cache_reused": True,
                  "cache_key": cache_key, "origin_receipt": cached["receipt"],
                  "usage": {"input_tokens": 0, "cached_input_tokens": 0, "uncached_input_tokens": 0,
                            "output_tokens": 0, "total_tokens": 0},
                  "input_sha256": hashlib.sha256(serialize_model_input(context).encode("utf-8")).hexdigest()}
        response_path.write_text(result["text"], encoding="utf-8")
        write_json(receipt_path, {k: v for k, v in result.items() if k != "text"})
        return result
    events_path = work / f"{kind}.events.jsonl"
    events = events_path.read_text(encoding="utf-8") if events_path.exists() else ""
    response = response_path.read_text(encoding="utf-8") if response_path.exists() else ""
    not_started = (receipt.get("no_model_started") is True
        and receipt.get("retryable_failure") is True
        and receipt.get("failure_type") == "capacity_admission_timeout"
        and receipt.get("exit_code") == 124 and not events.strip() and not response.strip()
        and receipt.get("model") == policy[f"{model_kind}_model"]
        and receipt.get("reasoning_effort") == policy[f"{model_kind}_effort"]
        and receipt.get("research_enabled", False) == research
        and receipt.get("input_sha256") == hashlib.sha256(serialize_model_input(context).encode("utf-8")).hexdigest()
        and receipt.get("instructions_sha256") == hashlib.sha256(instructions.encode()).hexdigest()
        and receipt.get("schema_sha256") == hashlib.sha256(json.dumps(schema, sort_keys=True).encode()).hexdigest())
    same_contract = (receipt.get('model') == policy[f'{model_kind}_model']
        and receipt.get('reasoning_effort') == policy[f'{model_kind}_effort']
        and receipt.get('research_enabled', False) == research
        and receipt.get('input_sha256') == hashlib.sha256(serialize_model_input(context).encode()).hexdigest()
        and receipt.get('instructions_sha256') == hashlib.sha256(instructions.encode()).hexdigest()
        and receipt.get('schema_sha256') == hashlib.sha256(json.dumps(schema, sort_keys=True).encode()).hexdigest())
    from src.local_runner.codex_call_evidence import inspect as inspect_call
    timeout_confirmed = (receipt.get('failure_type') != 'process_timeout' or
        ((receipt.get('timeout_reconciliation') or {}).get('state') == 'failed'
         and inspect_call(events, response)['state'] == 'failed'))
    confirmed_retry = not_started or (same_contract and timeout_confirmed
        and retryable_failure(receipt.get("exit_code"), events, response))
    key = reserve(budget, ticker=symbol, kind=kind, itv=itv, policy=policy, root=root,
                  retry_failed=confirmed_retry)
    if confirmed_retry:
        archive = work / "failed_calls" / (kind + "-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f"))
        archive.mkdir(parents=True, exist_ok=False)
        for path in work.glob(kind + ".*"):
            if path.is_file():
                path.rename(archive / path.name)
    try:
        result = call_codex(workspace=root / ".local" / "codex-analysis-workspace",
                            artifacts=work, kind=kind, instructions=instructions, data=context,
                            model=policy[f"{model_kind}_model"], effort=policy[f"{model_kind}_effort"],
                            timeout=policy[f"{model_kind}_timeout_seconds"],
                            schema=schema, research=research, max_parallel=policy["max_model_parallel"])
    except Exception as exc:
        finish(budget, key, receipt=read_json(receipt_path), error=str(exc))
        raise
    finish(budget, key, receipt=result)
    if cache_key:
        try:
            save_triage(root, symbol, cache_key, result, context)
        except (OSError, RuntimeError) as exc:
            write_json(work / "cache_warning.json", {"error": str(exc), "effect": "no_reuse"})
    return result


def receipt_itv(work: Path) -> dict:
    """Replay the original routing age, never today's age, with exact input binding.

    Freshness still uses today and publication still checks current ownership/base.
    Revalidating a receipt tomorrow is not a new model review or an ITV reset.
    """
    from src.local_runner.adaptive_context import unpack_model_context
    for kind in ('triage', 'report'):
        path = work / f'{kind}.input.json'
        if not path.exists():
            continue
        receipt = read_json(work / f'{kind}.receipt.json')
        if (receipt.get('exit_code') != 0 or not receipt.get('usage') or
                receipt.get('input_sha256') != hashlib.sha256(path.read_bytes()).hexdigest()):
            raise RuntimeError('recovery_routing_input_not_authenticated')
        frozen = unpack_model_context(read_json(path)).get('itv')
        if not isinstance(frozen, dict) or type(frozen.get('due')) is not bool:
            raise RuntimeError('recovery_routing_itv_missing')
        return frozen
    raise RuntimeError('recovery_routing_input_missing')


def analyze(root: Path, work: Path, symbol: str, budget: Path, force_full: bool, *, reuse_only: bool = False) -> dict:
    existing = read_json(work / "review.json")
    if existing.get("analysis_status") == "ok":
        return existing
    context = read_json(work / "input.json")
    policy = read_json(work / "policy.json")
    now = datetime.now(timezone.utc)
    data_ready(context, policy, now)
    ref = context["reference"]
    anchor = context.get("sol_reference", ref)
    # Freeze routing semantics with each input. Saved receipts from revision 1
    # must still reconstruct their exact original context on recovery.
    if policy.get("routing_revision", 1) >= 3:
        context["routing_revision"] = policy["routing_revision"]
        check = maintenance_precheck(ref, context["slim"], anchor, owned=context["owned"],
                                     revision=policy.get('routing_revision', 1))
        guards, context["review_flags"] = check["guards"], check["review_flags"]
    elif policy.get("routing_revision", 1) >= 2:
        guards = safeguards(ref, context["slim"])
        context["review_flags"] = routing_precheck(ref, context["slim"])["review_flags"]
    else:
        guards = legacy_safeguards(ref, context["slim"])
    itv = (receipt_itv(work) if reuse_only else
           itv_state(anchor, owned=context["owned"], priority=context["tier"] == "priority", now=now, policy=policy))
    context["guards"], context["itv"] = guards, itv
    decision = "escalate"
    receipts = []
    response_binding = None
    # Mandatory Sol decisions require no paid relevance review first.
    if not (force_full or guards or itv["due"]):
        result = model_call(root, work, symbol, budget, policy, "triage", context, reuse_only=reuse_only)
        if policy.get('routing_revision', 1) >= 11:
            from src.local_runner.semantic_binding import bind_response
            response_binding = bind_response(context, result, 'triage')
        receipts.append({k: v for k, v in result.items() if k != "text"})
        triage = json.loads(result["text"])
        attach_news_research(context, work, "triage", result, triage)
        decision = daily_decision(triage, guards, model_context(context))
        write_json(work / "triage.json", triage)
        context["triage"] = triage
    if decision == "blocked":
        raise RuntimeError("triage_blocked_insufficient_evidence")
    scheduled_itv = itv["due"] and not guards and not force_full
    if itv["due"]:
        decision = "escalate"
    updated_md = None
    update_validation = None
    update_rejection = None
    maintenance_normalizations = []
    repair_history = []
    semantic_doc = None
    semantic_fields = None
    review_contract = policy.get('routing_revision', 1) >= 18
    if decision == "update" or (review_contract and decision == 'retain' and triage is not None):
        from src.local_runner.adaptive_maintenance import apply_update
        from src.local_runner.adaptive_repair import repairable_update_error, repair_context
        repair_enabled = (policy.get("routing_revision", 1) >= 4
                          and policy.get("luna_repair_version", 0) == 1)
        for attempt in range(2 if repair_enabled else 1):
            maintenance_normalizations = []
            updated_md = None
            try:
                if review_contract:
                    from src.local_runner.review_contract import coverage_issues
                    from src.local_runner.semantic_sources import raise_issues
                    review_issues = coverage_issues(triage, model_context(context))
                    if decision == 'retain':
                        raise_issues(review_issues)
                        break
                if policy.get('routing_revision', 1) >= 9:
                    from src.local_runner.semantic_report import maintenance_document, render_document, validation_result
                    try:
                        semantic_doc = maintenance_document(triage, model_context(context), binding=response_binding)
                    except ValueError as exc:
                        if review_contract and review_issues and str(exc).startswith('update_not_allowed_'):
                            details = getattr(exc, 'maintenance_details', {}).get('issues') or [{'field': '/update', 'error': str(exc)}]
                            raise_issues([*details, *review_issues])
                        raise
                    if review_contract:
                        raise_issues(review_issues)
                    updated_md = render_document(semantic_doc)
                    update_validation = validation_result(semantic_doc)
                else:
                    updated_md = apply_update(triage, model_context(context), audit=maintenance_normalizations)
                    update_validation = one.validate_markdown(updated_md, authoritative_context=validation_context(context),
                        require_support_strengths=True, require_resistance=True, require_separate_scores=True)
                if not update_validation.ok:
                    write_json(work / ("update_validation_initial.json" if attempt == 0 else "update_validation_repair.json"), update_validation.to_dict())
                    write_json(work / "update_validation.json", update_validation.to_dict())
                    raise ValueError("update_not_allowed_validation: " + "; ".join(update_validation.errors))
                break
            except ValueError as exc:
                reason = str(exc)
                if policy.get('routing_revision', 1) >= 15:
                    handoff = context.setdefault('maintenance_handoff', {
                        'status': 'rejected_unpublished_proposals', 'attempts': [],
                        'instruction': 'These Luna proposals did NOT pass validation and were NOT published. '
                        'Use frozen reference/slim as authority. Independently reassess every unresolved '
                        'issue and financial claim; do not inherit a rejected proposal as verified evidence.'})
                    handoff['attempts'].append({'attempt': attempt + 1, 'reason': reason,
                        'validation_details': deepcopy(getattr(exc, 'maintenance_details', None)),
                        'rejected_response': deepcopy(triage)})
                if repair_enabled and repairable_update_error(reason):
                    repair_history.append({"attempt": attempt + 1, "reason": reason})
                    if attempt == 0:
                        feedback = repair_context(context, triage, reason,
                            validation_details=getattr(exc, "maintenance_details", None),
                            candidate_markdown=updated_md)
                        write_json(work / "luna_repair_request.json", feedback["maintenance_repair"])
                        result = model_call(root, work, symbol, budget, policy, "triage_repair", feedback, reuse_only=reuse_only)
                        if policy.get('routing_revision', 1) >= 11:
                            response_binding = bind_response(feedback, result, 'triage_repair')
                        receipts.append({k: v for k, v in result.items() if k != "text"})
                        triage = json.loads(result["text"])
                        attach_news_research(context, work, "triage_repair", result, triage)
                        decision = daily_decision(triage, guards, model_context(context))
                        write_json(work / "triage_repair.json", triage)
                        context["triage"] = triage
                        context["maintenance_repair_history"] = repair_history
                        if decision == "blocked":
                            raise RuntimeError("triage_repair_blocked_insufficient_evidence")
                        if decision != "update" and not (review_contract and decision == 'retain'):
                            break
                        continue
                elif not reason.startswith("update_not_allowed_"):
                    raise  # Integrity errors never trigger another model automatically.
                update_rejection = reason
                if policy.get('routing_revision', 1) >= 21 and reason.startswith('update_not_allowed_typed_data:'):
                    # An invalid response shape is not evidence of company risk.
                    # Risk/ITV were routed independently before this repair loop.
                    write_json(work / 'update_rejected.json', {'reason': reason,
                        'next': 'failed_review_contract_no_sol', 'luna_repair': repair_history})
                    raise RuntimeError('maintenance_review_contract_failed_no_sol: ' + reason) from exc
                if policy.get('routing_revision', 1) >= 25:
                    from src.local_runner.volume_arithmetic import arithmetic_only
                    if arithmetic_only(exc):
                        write_json(work / 'update_rejected.json', {'reason': reason,
                            'next': 'failed_volume_arithmetic_no_sol', 'luna_repair': repair_history})
                        raise RuntimeError('maintenance_volume_arithmetic_failed_no_sol: ' + reason) from exc
                if review_contract:
                    from src.local_runner.review_contract import review_contract_only
                    if review_contract_only(exc):
                        write_json(work / 'update_rejected.json', {'reason': reason,
                            'next': 'failed_review_contract_no_sol', 'luna_repair': repair_history})
                        raise RuntimeError('maintenance_review_contract_failed_no_sol: ' + reason) from exc
                if policy.get('routing_revision', 1) >= 14:
                    from src.local_runner.maintenance_change import change_justification_only
                    if change_justification_only(exc):
                        write_json(work / 'update_rejected.json', {
                            'reason': reason, 'next': 'failed_change_justification_no_sol',
                            'luna_repair': repair_history})
                        raise RuntimeError('maintenance_change_justification_failed_no_sol: ' + reason) from exc
                if policy.get('routing_revision', 1) >= 12:
                    from src.local_runner.semantic_sources import source_selection_only
                    if source_selection_only(exc):
                        write_json(work / 'update_rejected.json', {
                            'reason': reason, 'next': 'failed_source_selection_no_sol',
                            'luna_repair': repair_history})
                        raise RuntimeError('maintenance_source_selection_failed_no_sol: ' + reason) from exc
                write_json(work / "update_rejected.json", {"reason": reason, "next": "sol_review", "luna_repair": repair_history})
                context["maintenance_escalation"] = reason
                decision = "escalate"
                break
    review = {"symbol": symbol, "strategy": "adaptive-codex-v1", "reviewed_at": now.isoformat(),
              "market_data_at": context["slim"].get("as_of"), "itv": itv, "guards": guards,
              "generation_provider": "codex", "generation_provider_requested": "codex",
               "fallback_used": False, "receipts": receipts,
               "input_sha256": hashlib.sha256((work / "input.json").read_bytes()).hexdigest()}
    if policy.get("routing_revision", 1) >= 3:
        review.update(base_report_sha256=reference_key(ref), sol_anchor_sha256=reference_key(anchor),
                      maintenance_escalation=update_rejection,
                      maintenance_normalizations=maintenance_normalizations)
    if "review_flags" in context:
        review["routing_revision"] = policy["routing_revision"]
        review["review_flags"] = context["review_flags"]
    if repair_history:
        review["luna_repair"] = {"attempted": True, "rejections": repair_history, "decision": decision}
    if (context.get("news") or {}).get("luna_research"):
        review["luna_news_research"] = context["news"]["luna_research"]
    if decision == "escalate":
        result = model_call(root, work, symbol, budget, policy, "report", context,
                            itv=scheduled_itv, reuse_only=reuse_only)
        receipts.append({k: v for k, v in result.items() if k != "text"})
        if policy.get('routing_revision', 1) >= 9:
            from src.local_runner.semantic_report import full_document, render_document, validation_result
            if policy.get('routing_revision', 1) >= 11:
                from src.local_runner.semantic_binding import bind_response
                response_binding = bind_response(context, result, 'report')
            semantic_doc = full_document(json.loads(result['text']), model_context(context), binding=response_binding)
            md = render_document(semantic_doc)
            validation = validation_result(semantic_doc)
        else:
            md = one.normalize_report_dates(result["text"])
            validation = one.validate_markdown(md, authoritative_context=validation_context(context),
                                               require_support_strengths=True, require_resistance=True,
                                               require_separate_scores=True)
        if not validation.ok:
            write_json(work / "validation.json", validation.to_dict())
            raise RuntimeError("validation_failed_no_automatic_regeneration: " + "; ".join(validation.errors))
        # A recovered report keeps its original completion date, not today's
        # publication date. Otherwise retries would silently reset the ITV age.
        generated = timestamp(result.get("completed_at")) or datetime.fromtimestamp(
            (work / "report.response").stat().st_mtime, timezone.utc)
        if semantic_doc is not None:
            from src.local_runner.semantic_report import publication_fields
            semantic_fields = publication_fields(semantic_doc, md, ref, generated)
        payload = one._build_ok_payload(
            symbol=symbol, now=generated, analysis_md=md, slim=context["slim"],
            analyst_quality=context["analyst_quality"], analyst_ratings_summary=context["analyst_summary"],
            recent_analyst_actions=context["analyst_actions"], recent_ibkr_news=context["news"],
            recent_ibkr_news_events=one._news_events_not_used(), validation=validation.to_dict(),
            previous_analysis_markdown=ref.get("analysis_markdown", ""),
            generation_model=policy["report_model"], reasoning_effort=policy["report_effort"],
            execution_context="batch", analysis_kind="reference", reference_tier=context["tier"],
            owned=context["owned"], generation_provider="codex",
            structured_report={'schema_version': 7, **semantic_fields} if semantic_fields is not None else None)
        payload.update(reference_model=policy["report_model"], reference_generated_at=generated.isoformat(),
                       reference_tier=context["tier"], reference_score=payload["decision"].get("score"))
        review.update(status="regenerated", last_full_report_at=generated.isoformat(),
                      effective_model=policy["report_model"])
        staged = work / "publish" / "output" / symbol
        staged.mkdir(parents=True, exist_ok=True)
        try:
            save_research(root, work, symbol, payload)
        except (OSError, RuntimeError) as exc:
            write_json(work / "research_cache_warning.json", {"error": str(exc), "effect": "no_reuse"})
        (staged / "latest.md").write_text(md, encoding="utf-8")
        one.write_analysis_html(md, staged / "latest.html", symbol=symbol)
    elif decision == "update":
        # Completion time comes from the original Luna receipt, never the retry.
        generated = timestamp(result.get("completed_at")) or datetime.fromtimestamp(
            (work / ("triage_repair.response" if repair_history else "triage.response")).stat().st_mtime, timezone.utc)
        md = updated_md
        banner = ("Mantenimiento técnico: Luna · " + generated.date().isoformat() +
                  ". Texto narrativo, catalizadores y evento conservados del informe Sol · " +
                  str(anchor.get("generated_at", ""))[:10] + "; no investigados de nuevo.")
        # Visible provenance avoids presenting preserved fundamental claims as researched today.
        if md.startswith("Mantenimiento técnico: Luna · "):
            md = md.split("\n\n", 1)[1]
        md = banner + "\n\n" + md
        if policy.get('routing_revision', 1) < 9:
            update_validation = one.validate_markdown(md, authoritative_context=validation_context(context),
                require_support_strengths=True, require_resistance=True, require_separate_scores=True)
        write_json(work / "update_validation.json", update_validation.to_dict())
        if not update_validation.ok:
            raise RuntimeError("maintenance_presentation_validation_failed_no_automatic_regeneration: " +
                "; ".join(update_validation.errors))
        if semantic_doc is not None:
            from src.local_runner.semantic_report import publication_fields
            semantic_fields = publication_fields(semantic_doc, md, ref, generated)
        payload = one._build_ok_payload(symbol=symbol, now=generated, analysis_md=md, slim=context["slim"],
            analyst_quality=context["analyst_quality"], analyst_ratings_summary=context["analyst_summary"],
            recent_analyst_actions=context["analyst_actions"], recent_ibkr_news=context["news"],
            recent_ibkr_news_events=one._news_events_not_used(), validation=update_validation.to_dict(),
            previous_analysis_markdown=ref.get("analysis_markdown", ""), generation_model=policy["triage_model"],
            reasoning_effort=policy["triage_effort"], execution_context="batch", analysis_kind="daily_update",
            reference_tier=context["tier"], owned=context["owned"], generation_provider="codex",
            structured_report={'schema_version': 7, **semantic_fields} if semantic_fields is not None else None)
        payload.update(reference_model=anchor.get("generation_model"), reference_generated_at=anchor.get("generated_at"),
            reference_score=(anchor.get("decision") or {}).get("score"), last_full_report_at=anchor.get("generated_at"),
            sol_anchor_sha256=reference_key(anchor), maintenance={"model": policy["triage_model"],
            "updated_at": generated.isoformat(), "edits": triage.get('edits', []),
            "normalizations": maintenance_normalizations, "base_report_sha256": reference_key(ref)})
        review.update(status="updated", last_full_report_at=anchor.get("generated_at"),
                      effective_model=policy["triage_model"])
        staged = work / "publish" / "output" / symbol
        staged.mkdir(parents=True, exist_ok=True)
        (staged / "latest.md").write_text(md, encoding="utf-8")
        one.write_analysis_html(md, staged / "latest.html", symbol=symbol)
    else:
        # No scores, levels, market snapshot or report dates are touched.
        payload = dict(ref)
        review.update(status="retained", last_full_report_at=anchor.get("generated_at"),
                      effective_model=policy["triage_model"])
        staged = work / "publish" / "output" / symbol
        if policy.get('routing_revision', 1) >= 29:
            from src.local_runner.plan_scope import migrate_retained
            payload, changed = migrate_retained(ref, anchor, policy.get('routing_revision', 29))
            if changed:
                review['presentation_changed'] = True
                staged.mkdir(parents=True, exist_ok=True)
                (staged / 'latest.md').write_text(payload['analysis_markdown'], encoding='utf-8')
                one.write_analysis_html(payload['analysis_markdown'], staged / 'latest.html', symbol=symbol)
    if semantic_doc is not None and decision in ('update', 'escalate'):
        payload.update(semantic_fields)
        if decision == 'update':
            payload['maintenance']['semantic_update'] = deepcopy(triage['update'])
    if policy.get('routing_revision', 1) >= 32 and decision in ('retain', 'update'):
        from src.local_runner.reader_report import migrate_payload
        payload, changed = migrate_payload(payload, ref, anchor, triage.get('reader_review'),
                                           revision=policy['routing_revision'])
        if changed:
            review['presentation_changed'] = True
            staged.mkdir(parents=True, exist_ok=True)
            (staged / 'latest.md').write_text(payload['analysis_markdown'], encoding='utf-8')
            one.write_analysis_html(payload['analysis_markdown'], staged / 'latest.html', symbol=symbol)
    if policy.get('routing_revision', 1) >= 36 and decision in ('retain', 'update'):
        from src.local_runner.support_validity import migrate_payload
        payload, changed = migrate_payload(payload, ref, anchor,
            triage.get('support_validity_review'), model_context(context))
        if changed:
            review['presentation_changed'] = True
            staged.mkdir(parents=True, exist_ok=True)
            (staged / 'latest.md').write_text(payload['analysis_markdown'], encoding='utf-8')
            one.write_analysis_html(payload['analysis_markdown'], staged / 'latest.html', symbol=symbol)
    review["analysis_status"] = "ok"
    if policy.get('routing_revision', 1) >= 16:
        from src.local_runner.review_memory import build_memory
        payload['review_memory'] = build_memory(context, payload, review)
    payload["daily_review"] = review
    write_json(staged / "latest.json", payload)
    write_json(work / "review.json", review)
    return review


def _copy_json(source: Path, destination: str) -> None:
    import os
    run_bounded([require_gcloud(), "storage", "cp", "--content-type=application/json; charset=utf-8",
                 str(source), destination], check=True, timeout=120,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)


def publish(root: Path, work: Path, symbol: str) -> dict:
    lock = root / "output" / symbol / "adaptive_publish.lock"
    lock.parent.mkdir(parents=True, exist_ok=True)
    with _exclusive_read_lock(lock):
        return _publish_locked(root, work, symbol)


def _publish_locked(root: Path, work: Path, symbol: str) -> dict:
    review = read_json(work / "review.json")
    if review.get("analysis_status") != "ok":
        raise RuntimeError("adaptive_review_not_validated")
    if review.get("published_at"):
        return review
    source = work / "publish" / "output" / symbol
    payload = read_json(source / "latest.json")
    current = _read_json_gcs(f"gs://{TEST_BUCKET}/{symbol}/latest.json") or {}
    if review.get('routing_revision', 1) >= 16:
        previous_review_at = timestamp((current.get('daily_review') or {}).get('reviewed_at'))
        reviewed_at = timestamp(review.get('reviewed_at'))
        if previous_review_at and (reviewed_at is None or previous_review_at > reviewed_at):
            raise RuntimeError('publication_rejected_newer_review_exists')
    candidate_at, current_at = timestamp(payload.get("generated_at")), timestamp(current.get("generated_at"))
    if current_at and (candidate_at is None or current_at > candidate_at):
        raise RuntimeError("publication_rejected_newer_report_exists")
    if review.get("routing_revision", 1) >= 3:
        # A newer full Sol anchor also invalidates an old Luna candidate.
        anchor_now = _read_json_gcs(f"gs://{TEST_BUCKET}/_analysis_state/{symbol}/reference.json") or {}
        if review["status"] != "regenerated" and anchor_now.get("analysis_status") != "ok":
            raise RuntimeError("publication_rejected_missing_or_invalid_sol_anchor")
        if anchor_now and reference_key(anchor_now) not in {review["sol_anchor_sha256"], reference_key(payload)}:
            raise RuntimeError("publication_rejected_sol_anchor_changed")
        if current.get("analysis_status") == "ok" and reference_key(current) not in {
                review["base_report_sha256"], reference_key(payload)}:
            raise RuntimeError("publication_rejected_current_report_changed")
    if review.get('routing_revision', 1) >= 16:
        from src.local_runner.review_memory import read_memory
        # Every writer, including authorized manual corrections, must produce
        # state readable by the next analysis BEFORE the first external write.
        read_memory(payload, payload if review['status'] == 'regenerated' else anchor_now)
    if review["status"] in {"regenerated", "updated"} or review.get('presentation_changed'):
        # This frozen staging root is also the source of every publication retry.
        one._upload(work / "publish", symbol, upload_kind="real", dry_run=False)
        if review["status"] == "regenerated":
            save_reference_payload(root, symbol, payload)
    else:
        for uri in (f"gs://{TEST_BUCKET}/{symbol}/latest.json",
                    f"gs://{SHEET_REPORT_MIRROR_BUCKET}/{SHEET_REPORT_MIRROR_PREFIX}/{symbol}.json"):
            _copy_json(source / "latest.json", uri)
    if review.get("routing_revision", 1) >= 3 and (
            review["status"] in {"regenerated", "updated"} or review.get('routing_revision', 1) >= 16):
        current_payload = dict(payload)
        if review["status"] == "regenerated":
            current_payload.update(sol_anchor_sha256=reference_key(payload), last_full_report_at=payload["generated_at"])
        elif review.get('routing_revision', 1) >= 16:
            current_payload.update(sol_anchor_sha256=review['sol_anchor_sha256'],
                                   last_full_report_at=review['last_full_report_at'])
        state = root / "data" / "analysis_state" / symbol / "current.json"
        if review.get('routing_revision', 1) >= 16:
            # An upload failure must not make an unpublished memory look like
            # valid fallback state on the next transient remote-read failure.
            staged_state = work / 'publish' / 'current_state.json'
            write_json(staged_state, current_payload)
            _copy_json(staged_state, current_uri(symbol))
            write_json(state, current_payload)
        else:
            write_json(state, current_payload)
            _copy_json(state, current_uri(symbol))
    _copy_json(work / "review.json", f"gs://{TEST_BUCKET}/{symbol}/review.json")
    target = root / "output" / symbol
    target.mkdir(parents=True, exist_ok=True)
    for path in source.glob("latest.*"):
        shutil.copy2(path, target / path.name)
    review["published_at"] = datetime.now(timezone.utc).isoformat()
    write_json(work / "review.json", review)
    write_json(target / "daily_review.json", review)
    return review


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("ticker")
    parser.add_argument("--stage", choices=["prepare", "analyze", "publish"], required=True)
    parser.add_argument("--batch-dir", type=Path, required=True)
    parser.add_argument("--owned", action="store_true")
    parser.add_argument("--tier", default="tracking")
    parser.add_argument("--force-full", action="store_true")
    args = parser.parse_args(argv)
    root = one._find_repo_root(Path.cwd())
    work = args.batch_dir.resolve() / "adaptive" / args.ticker
    work.mkdir(parents=True, exist_ok=True)
    try:
        with _exclusive_read_lock(work / "stage.lock"):
            require_activation(load_policy(root))
            if args.stage == "prepare":
                prepare(root, work, args.ticker, args.owned, args.tier)
            elif args.stage == "analyze":
                analyze(root, work, args.ticker, args.batch_dir / "codex_budget.json", args.force_full)
            else:
                publish(root, work, args.ticker)
        print(f"OK {args.ticker}: adaptive {args.stage}", flush=True)
        return 0
    except Exception as exc:
        write_json(work / "failure.json", {"analysis_status": "failed", "stage": args.stage,
                                          "error_type": type(exc).__name__, "error_message": str(exc),
                                          "at": datetime.now(timezone.utc).isoformat()})
        print(f"FAILED {args.ticker}: {exc}", flush=True)
        return 1


def run_individual(root: Path, symbol: str, args) -> int:
    from src.local_runner.adaptive_preflight import check
    require_activation(load_policy(root))
    from src.local_runner.ownership import recorded_ownership
    from src.local_runner.analysis_policy import parse_reference_summary, resolve_tier
    # Omitted, explicitly owned and explicitly not-owned are distinct inputs.
    if args.owned is not None:
        owned, ownership = args.owned, {'source': 'explicit --owned' if args.owned else 'explicit --no-owned'}
    else:
        owned, ownership = recorded_ownership(symbol)
    reference = parse_reference_summary(load_reference_payload(symbol))
    tier = resolve_tier(owned=owned, reference_score=reference.score, previous_tier=reference.tier)
    check(root, load_policy(root))
    if not args.skip_ibkr_gateway_ensure:
        one.ensure_gateway(root)
    if not args.skip_preflight_updates:
        one._run_preflight_updates(root, symbol)
    batch = root / "logs" / "adaptive_individual" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")
    work = batch / symbol
    work.mkdir(parents=True, exist_ok=True)
    try:
        prepare(root, work, symbol, owned, tier, ownership=ownership)
        analyze(root, work, symbol, batch / "codex_budget.json", True)
        publish(root, work, symbol)
        print(f"OK {symbol}: analisis generado y subido.")
        return 0
    except Exception as exc:
        write_json(work / "failure.json", {"analysis_status": "failed", "error_message": str(exc)})
        print(f"FAILED {symbol}: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
