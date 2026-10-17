from __future__ import annotations
import json
import tempfile
import subprocess
import unittest
from datetime import date, datetime, timezone
from pathlib import Path
from unittest.mock import patch
from src.local_runner import adaptive_policy as policy
from src.local_runner import adaptive_budget as budget
from src.local_runner import adaptive_stage as stage
from src.local_runner import adaptive_codex as codex
from src.local_runner.adaptive_context import model_context, resolve_evidence, validation_context

ROOT = Path(__file__).resolve().parent
# These saved-output fixtures exercise historical revision-2 receipt semantics.
# Revision-3 publication and update contracts have their own stage suite.
POLICY = {**policy.load_policy(ROOT), "routing_revision": 2}
NOW = datetime(2026, 10, 1, 14, tzinfo=timezone.utc)


def triage(decision="retain"):
    return {"decision": decision, "uncertainty": False, "reason": "Current evidence supports prior report",
            **{k: {"assessment": "Compared", "evidence": ["/slim/levels"]} for k in policy.SECTIONS}}


class PolicyTests(unittest.TestCase):
    def test_existing_validator_receives_previous_levels_and_slim(self):
        from src.common.analysis_validator import _validate_previous_level_references, _distinct_lower_support
        context = {"symbol": "CAT", "reference": {"analysis_markdown": "Stop de gestión: $799\n"},
                   "slim": {"latest_price": 110, "levels": {"supports": [{"level": 90}]}}}
        adapted = validation_context(context)
        changed = "Stop de gestión: $795\nMotivo: Se corrige: el anterior $799 quedaba dentro de la banda."
        self.assertEqual(_validate_previous_level_references(changed, adapted), [])
        self.assertTrue(_validate_previous_level_references(changed.replace("anterior $799", "anterior $750"), adapted))
        self.assertEqual(_distinct_lower_support(adapted, entry_floor=100), 90)

    def test_activation_gate_blocks_unverified_production(self):
        for value in ({}, {"production_enabled": False}):
            with self.assertRaisesRegex(RuntimeError, "validation_pending"):
                policy.require_activation(value)
        policy.require_activation({"production_enabled": True})

    def test_schema_limits_citations_to_existing_source_sections(self):
        context = {"slim": {"levels": []}, "reference": {"analysis_markdown": "full"}, "news": {"items": []},
                   "analyst_actions": {"actions": []}, "guards": []}
        schema = policy.triage_schema(context)
        pointers = schema["$defs"]["evidence_pointer"]["enum"]
        self.assertIn("/news", pointers)
        self.assertEqual(schema, policy.triage_schema({**context, "slim": {"mirror_url": "optional", "options": []}}))
        self.assertNotIn("/reference/slim_snapshot/plan", pointers)
        for pointer in pointers:
            resolve_evidence(context, pointer)
        for key in policy.SECTIONS:
            self.assertEqual(schema["properties"][key]["properties"]["evidence"]["items"],
                             {"$ref": "#/$defs/evidence_pointer"})

    def test_model_context_preserves_evidence_not_historical_changes(self):
        original = {"reference": {"analysis_markdown": "full baseline", "slim_snapshot": {"as_of": "then"},
                                 "plan": {"resistance": 910}, "changes": {"plan_changes": "old change"},
                                 "daily_review": {"receipts": ["large"]}},
                    "slim": {"as_of": "now"}, "news": {"items": ["all headlines"]},
                    "analyst_actions": {"actions": ["all actions"]}}
        view = model_context(original)
        for key in ("analysis_markdown", "slim_snapshot", "plan"):
            self.assertEqual(view["reference"][key], original["reference"][key])
        for key in ("news", "analyst_actions", "slim"):
            self.assertEqual(view[key], original[key])
        self.assertNotIn("changes", view["reference"])
        self.assertNotIn("daily_review", view["reference"])
        self.assertIn("changes", original["reference"])
        self.assertFalse(view["comparison"]["same_market_snapshot"])
        original["slim"] = original["reference"]["slim_snapshot"]
        self.assertTrue(model_context(original)["comparison"]["same_market_snapshot"])

    def test_evidence_rejects_invented_paths(self):
        context = {"slim": {"levels": []}, "news": {"items": [{"headline": "fact"}]}}
        for pointer in ("reference.plan.next_event", "/reference/plan/next_event", "/slim_snapshot/levels",
                        "/news/items/-1", "/news/items/01", "/news/items/1", "/news/~2"):
            value = triage("escalate")
            value["news"]["evidence"] = [pointer]
            with self.assertRaises(ValueError):
                policy.triage_decision(value, [], context)
        self.assertEqual(policy.triage_decision(triage(), [], context), "retain")
        self.assertEqual(resolve_evidence(context, "/news/items/0/headline"), "fact")
        self.assertEqual(resolve_evidence({"a/b": {"~": 1}}, "/a~1b/~0"), 1)

    def test_holidays_and_session_age(self):
        for day in (date(2026, 1, 1), date(2026, 4, 3), date(2026, 6, 19), date(2026, 7, 3)):
            self.assertFalse(policy.market_session(day))
        self.assertTrue(policy.market_session(date(2021, 12, 31)))
        self.assertEqual(policy.session_age(datetime(2026, 9, 24, 14, tzinfo=timezone.utc), NOW), 5)
        self.assertFalse(policy.market_session(date(2025, 1, 9), POLICY["extra_market_closures"]))

    def test_itv_due_after_five_sessions_for_every_tier(self):
        for owned, priority in ((True, False), (False, True), (False, False)):
            for generated_at, due in (("2026-09-25T14:00:00Z", False), ("2026-09-24T14:00:00Z", True)):
                with self.subTest(owned=owned, priority=priority, generated_at=generated_at):
                    ref = {"analysis_status": "ok", "generated_at": generated_at,
                           "generation_model": "gpt-6.1-sol", "reasoning_effort": "high"}
                    state = policy.itv_state(ref, owned=owned, priority=priority, now=NOW, policy=POLICY)
                    self.assertEqual(state["limit_sessions"], 5)
                    self.assertEqual(state["due"], due)

    def test_itv_does_not_trust_bootstrap_or_luna(self):
        ref = {"analysis_status": "ok", "generated_at": NOW.isoformat(), "reference_model": "gpt-5.6-sol",
               "generation_model": "gpt-6-luna", "reasoning_effort": "high"}
        self.assertTrue(policy.itv_state(ref, owned=True, priority=False, now=NOW, policy=POLICY)["due"])
        ref["generation_model"] = "gpt-6.1-sol"
        self.assertFalse(policy.itv_state(ref, owned=True, priority=False, now=NOW, policy=POLICY)["due"])

    def test_guards_override_luna(self):
        self.assertEqual(policy.triage_decision(triage(), ["prior_support_evidence_missing"]), "escalate")
        self.assertEqual(policy.triage_decision(triage("blocked"), ["guard"]), "blocked")
        value = triage()
        value["uncertainty"] = True
        self.assertEqual(policy.triage_decision(value, []), "escalate")

    def test_schema_requires_all_evidence(self):
        value = triage()
        value["levels"]["evidence"] = []
        with self.assertRaises(ValueError):
            policy.triage_decision(value, [])

    def test_quota_unknown_or_exhausted_fail_closed(self):
        for value in ({}, {"primary": {"used_percent": 100}},
                      {"primary": {"used_percent": 50}, "rate_limit_reached_type": "usage_limit"},
                      {"primary": {"used_percent": 50}, "secondary": {"used_percent": 100}}):
            with self.assertRaises(RuntimeError):
                budget.check_quota(value)
        for used in (60, 70, 71, 90, 99.9):
            budget.check_quota({"primary": {"used_percent": used}})

    def test_no_reserved_quota_even_with_legacy_policy(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(budget, "read_codex_rate_limits", return_value={"primary": {"used_percent": 90}}):
            key = budget.reserve(Path(tmp) / "budget.json", ticker="CAT", kind="triage", itv=False,
                                 policy={**POLICY, "max_used_percent": 70}, root=ROOT)
            self.assertEqual(key, "CAT:triage")

    def test_reservation_prevents_duplicate_after_crash(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(budget, "read_codex_rate_limits", return_value={"primary": {"used_percent": 10}}):
            path = Path(tmp) / "budget.json"
            key = budget.reserve(path, ticker="CAT", kind="triage", itv=False, policy=POLICY, root=ROOT)
            with self.assertRaisesRegex(RuntimeError, "already_reserved"):
                budget.reserve(path, ticker="CAT", kind="triage", itv=False, policy=POLICY, root=ROOT)
            budget.finish(path, key, error="provider unavailable")
            ledger = budget.read_json(path)
            ledger["circuit_open"] = "historical failed call"
            budget.write_json(path, ledger)
            self.assertEqual(budget.reserve(path, ticker="AMD", kind="report", itv=False, policy=POLICY, root=ROOT), "AMD:report")
            with self.assertRaisesRegex(RuntimeError, "already_reserved"):
                budget.reserve(path, ticker="CAT", kind="triage", itv=False, policy=POLICY, root=ROOT)

    def test_missing_support_and_broken_stop_force_review(self):
        ref = {"analysis_status": "ok", "analysis_markdown": "Entrada: 100-102\nEntrada ambiciosa: 90-92",
               "plan": {"management_stop": 95}, "latest_price": 100}
        slim = {"latest_price": 94, "levels": {"supports": [{"level": 80}]}}
        guards = policy.safeguards(ref, slim)
        self.assertIn("prior_support_evidence_missing", guards)
        self.assertIn("price_below_management_stop", guards)

    def test_same_price_different_support_does_not_hide_lost_origin(self):
        ref = {"analysis_status": "ok", "analysis_markdown": "Entrada: 100-102\nEntrada ambiciosa: 90-92",
               "slim_snapshot": {"levels": {"supports": [{"level": 101, "type": "old", "strength_score": 80}]}}}
        slim = {"latest_price": 105, "levels": {"supports": [{"level": 101, "type": "new", "strength_score": 80}]}}
        self.assertIn("prior_supports_origin_missing", policy.safeguards(ref, slim))

    def test_full_batch_has_no_artificial_caps_with_frozen_legacy_policy(self):
        legacy = {**POLICY, **{key: 1 for key in budget.RETIRED_LIMITS}}
        with tempfile.TemporaryDirectory() as tmp, patch.object(budget, "read_codex_rate_limits", return_value={"primary": {"used_percent": 90}}):
            path = Path(tmp) / "budget.json"
            budget.write_json(path, {"calls": {}, "policy": legacy})
            for ticker in range(46):
                for kind in ("triage", "report"):
                    # Switching to current config must also accept an old ledger
                    # whose only differences are now-removed spending limits.
                    selected = legacy if ticker == 0 else POLICY
                    key = budget.reserve(path, ticker=str(ticker), kind=kind, itv=kind == "report",
                                         policy=selected, root=ROOT)
                    budget.finish(path, key, receipt={"usage": {"output_tokens": 100001,
                                                               "uncached_input_tokens": 2000001}})
            self.assertEqual(len(budget.read_json(path)["calls"]), 92)


class StageTests(unittest.TestCase):
    def context(self):
        return {"symbol": "CAT", "prepared_at": NOW.isoformat(), "owned": False, "tier": "tracking",
                "reference": {"analysis_status": "ok", "generated_at": NOW.isoformat(),
                              "generation_model": "gpt-6.1-sol", "reasoning_effort": "high",
                              "analysis_markdown": "unchanged", "latest_price": 100},
                "slim": {"as_of": NOW.isoformat(), "latest_price": 100, "levels": {"supports": [{"level": 99}]}},
                "analyst_actions": {"status": "ok", "actions": []}, "news": {"status": "ok", "items": []}}

    def test_stale_data_never_reaches_model(self):
        value = self.context()
        value["slim"]["as_of"] = "2020-01-01"
        with self.assertRaisesRegex(RuntimeError, "stale"):
            stage.data_ready(value, POLICY, NOW)

    def test_retain_preserves_entire_report_except_review(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            context = self.context()
            budget.write_json(root / "input.json", context)
            budget.write_json(root / "policy.json", POLICY)
            with patch.object(stage, "data_ready"), patch.object(stage, "safeguards", return_value=[]), patch.object(stage, "itv_state", return_value={"due": False}), patch.object(stage, "model_call", return_value={"text": json.dumps(triage()), "usage": {"output_tokens": 100}}) as model:
                result = stage.analyze(root, root, "CAT", root / "budget.json", False)
                stage.analyze(root, root, "CAT", root / "budget.json", False)
            self.assertEqual(model.call_count, 1)
            self.assertEqual(result["status"], "retained")
            payload = budget.read_json(root / "publish/output/CAT/latest.json")
            payload.pop("daily_review")
            self.assertEqual(payload, context["reference"])

    def test_luna_failure_does_not_call_sol(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            budget.write_json(root / "input.json", self.context())
            budget.write_json(root / "policy.json", POLICY)
            with patch.object(stage, "data_ready"), patch.object(stage, "safeguards", return_value=[]), patch.object(stage, "itv_state", return_value={"due": False}), patch.object(stage, "model_call", side_effect=RuntimeError("Luna unavailable")) as model:
                with self.assertRaises(RuntimeError):
                    stage.analyze(root, root, "CAT", root / "budget.json", False)
            self.assertEqual(model.call_count, 1)
            self.assertFalse((root / "review.json").exists())

    def test_completed_report_reused_on_publish_retry(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            budget.write_json(root / "review.json", {"analysis_status": "ok", "status": "retained"})
            budget.write_json(root / "publish/output/CAT/latest.json", {"generated_at": "old"})
            with patch.object(stage, "_copy_json") as upload, patch.object(stage, "_read_json_gcs", return_value=None):
                stage.publish(root, root, "CAT")
                stage.publish(root, root, "CAT")
            self.assertEqual(upload.call_count, 3)

    def test_retain_cannot_overwrite_a_newer_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            budget.write_json(root / "review.json", {"analysis_status": "ok", "status": "retained"})
            budget.write_json(root / "publish/output/CAT/latest.json", {"generated_at": "2026-09-01T14:00:00Z"})
            with patch.object(stage, "_copy_json") as upload, patch.object(stage, "_read_json_gcs", return_value={"generated_at": NOW.isoformat()}):
                with self.assertRaisesRegex(RuntimeError, "newer_report"):
                    stage.publish(root, root, "CAT")
            upload.assert_not_called()


class GeneratorTests(unittest.TestCase):
    def test_research_enabled_does_not_require_unnecessary_search(self):
        for searched in (False, True):
            with self.subTest(searched=searched), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                def fake_run(command, **kwargs):
                    Path(command[command.index("--output-last-message")+1]).write_text("report", encoding="utf-8")
                    events = [{"type": "turn.completed", "usage": {"input_tokens": 100, "output_tokens": 10}}]
                    if searched:
                        events.insert(0, {"type": "item.completed", "item": {"type": "web_search", "id": "search_1"}})
                    return subprocess.CompletedProcess(command, 0, "\n".join(json.dumps(x) for x in events), "")
                with patch.object(codex, "require_codex", return_value="codex"), patch.object(codex, "run_bounded", side_effect=fake_run):
                    def call():
                        return codex.call_codex(workspace=root, artifacts=root, kind="report", instructions="research",
                            data={}, model="gpt-6.1-sol", effort="high", timeout=20, research=True)
                    self.assertEqual(call()["web_search_count"], int(searched))

    def test_unknown_call_kind_cannot_enable_web_research(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(codex, "run_bounded") as execute:
            root = Path(tmp)
            with self.assertRaisesRegex(ValueError, "unsupported_call_kind"):
                codex.call_codex(workspace=root, artifacts=root, kind="unapproved_research", instructions="stable",
                    data={}, model="gpt-6-luna", effort="medium", timeout=20, research=True)
            execute.assert_not_called()

    def test_model_receipt_cannot_reuse_different_context(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "triage_instructions.md").write_text("stable", encoding="utf-8")
            (root / "triage.response").write_text("old", encoding="utf-8")
            budget.write_json(root / "triage.receipt.json", {"exit_code": 0, "usage": {"input_tokens": 10},
                                                          "input_sha256": "old"})
            with patch.object(stage, "reserve") as reserve:
                with self.assertRaisesRegex(RuntimeError, "context_mismatch"):
                    stage.model_call(root, root, "CAT", root / "budget.json", POLICY, "triage", {})
            reserve.assert_not_called()

    def test_stable_prefix_separate_data_and_measured_usage(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            calls = []
            def fake_run(command, **kwargs):
                calls.append((command, kwargs))
                output = Path(command[command.index("--output-last-message")+1])
                output.write_text(json.dumps(triage()), encoding="utf-8")
                return subprocess.CompletedProcess(command, 0,
                    '{"type":"turn.completed","usage":{"input_tokens":1000,"cached_input_tokens":800,"output_tokens":120,"reasoning_output_tokens":40}}\n', "")
            with patch.object(codex, "require_codex", return_value="codex"), patch.object(codex, "run_bounded", side_effect=fake_run):
                results = [codex.call_codex(workspace=root / "workspace", artifacts=root / ticker,
                    kind="triage", instructions="stable instructions", data={"symbol": ticker},
                    model="gpt-6-luna", effort="medium", timeout=20, schema=policy.TRIAGE_SCHEMA)
                    for ticker in ("CAT", "NVDA")]
            self.assertEqual(results[0]["instructions_sha256"], results[1]["instructions_sha256"])
            self.assertNotEqual(results[0]["input_sha256"], results[1]["input_sha256"])
            self.assertEqual(results[0]["usage"]["total_tokens"], 1120)
            self.assertEqual(results[0]["usage"]["cached_input_tokens"], 800)
            for command, kwargs in calls:
                self.assertIn('forced_login_method="chatgpt"', command)
                self.assertIn('service_tier="default"', command)
                self.assertIn("read-only", command)
                self.assertIn("features.shell_tool=false", command)
                self.assertNotIn("OPENAI_API_KEY", kwargs["env"])
                self.assertIn('"symbol"', kwargs["input"])
                self.assertNotIn("stable instructions", kwargs["input"])

    def test_stale_response_never_accepted(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "triage.response").write_text("old", encoding="utf-8")
            with patch.object(codex, "run_bounded") as execute:
                with self.assertRaisesRegex(RuntimeError, "already_exists"):
                    codex.call_codex(workspace=root, artifacts=root, kind="triage", instructions="stable",
                        data={}, model="gpt-6-luna", effort="medium", timeout=20)
            execute.assert_not_called()


if __name__ == "__main__":
    unittest.main()
