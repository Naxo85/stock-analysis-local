"""Offline news-tool/authority/cache integration; no real CLI/model/network calls."""
from contextlib import ExitStack, nullcontext
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import test_adaptive_maintenance_stage as fixtures
from src.common.analysis_validator import ValidationResult
from src.local_runner import adaptive_cache as cache, adaptive_codex as codex, adaptive_stage as stage
from src.local_runner.adaptive_budget import read_json, write_json
from src.local_runner.adaptive_context import model_context
from src.local_runner.adaptive_maintenance import apply_update, maintenance_schema
from src.local_runner.adaptive_news_research import (
    news_research_enabled, news_research_instructions, collect_news_research, attach_news_research,
)

URL = "https://example.test/company/news"
OTHER = "https://example.test/unrelated"


def events():
    return json.dumps({"type": "item.completed", "item": {"id": "web-1", "type": "web_search",
        "results": [{"url": URL, "title": "Company announcement", "snippet": "Article discovery"},
                    {"url": OTHER, "title": "Unused result"}]}}) + "\n"


def receipt(text=None):
    text = events() if text is None else text
    return {"research_enabled": True, "web_search_count": 1, "exit_code": 0,
        "model": "gpt-6-luna", "completed_at": fixtures.NOW.isoformat(),
        "usage": {"input_tokens": 100, "output_tokens": 20},
        "luna_news_events_sha256": hashlib.sha256(text.encode()).hexdigest()}


def verdict(data, decision="update"):
    value = fixtures.update_payload(data)
    value["evidence_gap"] = "none"
    value["news"] = {"assessment": f"Anuncio rutinario fechado, fuente [empresa]({URL}).", "evidence": ["/news"]}
    value["decision"] = decision
    if decision == "update":
        value["routine_note"] = f"Anuncio rutinario; no modifica la conclusión fundamental. [Fuente]({URL})."
    else:
        value.update(edits=[], routine_note="")
    return value


class NewsResearchTests(unittest.TestCase):
    def test_policy_opt_in_and_legacy_prefix_unchanged(self):
        for revision in range(1, 7):
            self.assertFalse(news_research_enabled({"routing_revision": revision, "luna_news_research_enabled": True}))
        self.assertFalse(news_research_enabled({"routing_revision": 7}))
        self.assertTrue(news_research_enabled({"routing_revision": 7, "luna_news_research_enabled": True}))
        self.assertEqual(news_research_instructions("Frozen prefix", enabled=False), "Frozen prefix")
        enabled = news_research_instructions("Frozen prefix", enabled=True)
        self.assertIn("No fixed minimum or maximum", enabled)
        self.assertIn("never include holdings", enabled)
        self.assertIn("slim remains authoritative", enabled)
        self.assertEqual(maintenance_schema({"routing_revision": 7}), maintenance_schema({"routing_revision": 5}))

    def test_only_cited_actual_tool_sources_not_self_reported_urls(self):
        data = fixtures.context()
        value = verdict(data)
        value["news"]["assessment"] += " https://invented.test/fake"
        collected = collect_news_research(events(), receipt(), value)
        self.assertEqual([s["url"] for s in collected["sources"]], [URL])
        self.assertIn("not_independent_fact_check", collected["provenance"])
        self.assertEqual(collected["retrieved_at"], fixtures.NOW.isoformat())
        self.assertNotIn("published_at", collected)

    def test_integrity_and_tool_count_mismatch_stay_visible(self):
        value = verdict(fixtures.context())
        with self.assertRaisesRegex(ValueError, "integrity_mismatch"):
            collect_news_research(events() + " ", receipt(), value)
        with self.assertRaisesRegex(ValueError, "count_mismatch"):
            collect_news_research(events(), {**receipt(), "web_search_count": 2}, value)

    def test_attachment_preserves_inputs_and_reconstructs_once_per_call(self):
        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory)
            data = fixtures.context()
            data["routing_revision"] = 7
            frozen = deepcopy(data)
            value = verdict(data)
            for kind in ("triage", "triage_repair", "triage_repair"):
                (work / f"{kind}.events.jsonl").write_text(events(), encoding="utf-8")
                attach_news_research(data, work, kind, receipt(), value)
            calls = data["news"]["luna_research"]["calls"]
            self.assertEqual([r["source_call"] for r in calls], ["triage", "triage_repair"])
            self.assertEqual(data["slim"], frozen["slim"])
            self.assertEqual(data["reference"], frozen["reference"])
            self.assertEqual(data["news"]["items"], frozen["news"]["items"])
            self.assertNotIn("luna_research", frozen["news"])

    def test_no_search_no_attachment_and_old_contract_ignores_new_artifacts(self):
        data = fixtures.context()
        frozen = deepcopy(data)
        attach_news_research(data, Path("not-present"), "triage", receipt(), verdict(data))
        self.assertEqual(data, frozen)
        data["routing_revision"] = 7
        attach_news_research(data, Path("not-present"), "triage", {**receipt(), "web_search_count": 0}, verdict(data))
        self.assertNotIn("luna_research", data["news"])
        with self.assertRaisesRegex(ValueError, "events_missing"):
            attach_news_research(data, Path("not-present"), "triage", receipt(), verdict(data))

    def test_web_note_supported_without_IBKR_items_but_invented_url_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory)
            data = fixtures.context()
            data["routing_revision"] = 7
            data["news"]["items"] = []
            data["analyst_actions"]["actions"] = []
            value = verdict(data)
            (work / "triage.events.jsonl").write_text(events(), encoding="utf-8")
            attach_news_research(data, work, "triage", receipt(), value)
            self.assertIn(URL, apply_update(value, model_context(data)))
            value["routine_note"] += " [inventada](https://invented.test/fake)"
            with self.assertRaisesRegex(ValueError, "unsupported_url"):
                apply_update(value, model_context(data))

    def test_news_lookup_does_not_expand_fundamental_edit_authority(self):
        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory)
            data = fixtures.context()
            data["routing_revision"] = 7
            value = verdict(data)
            value["edits"].append(fixtures.FIXTURE.edit("Tesis: 8 / 10", "Tesis: 9 / 10", ["/news"]))
            (work / "triage.events.jsonl").write_text(events(), encoding="utf-8")
            attach_news_research(data, work, "triage", receipt(), value)
            with self.assertRaises(ValueError):
                apply_update(value, model_context(data))

    def test_model_prose_and_snippet_links_do_not_create_citation_authority(self):
        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory)
            data = {**fixtures.context(), "routing_revision": 7}
            value = verdict(data)
            fake = "https://invented.test/fake"
            value["news"]["assessment"] += f" [falsa]({fake})"
            value["routine_note"] += f" [falsa]({fake})"
            event = json.loads(events())
            event["item"]["results"][0]["snippet"] = f"Another URL mentioned: {fake}"
            raw = json.dumps(event) + "\n"
            (work / "triage.events.jsonl").write_text(raw, encoding="utf-8")
            attach_news_research(data, work, "triage", receipt(raw), value)
            with self.assertRaisesRegex(ValueError, "unsupported_url"):
                apply_update(value, model_context(data))

    def test_researched_verdict_not_saved_and_web_capable_zero_search_can_reuse(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            data = model_context({**fixtures.context(), "routing_revision": 7})
            value = verdict(data, "retain")
            result = {**receipt(), "text": json.dumps(value)}
            cache.save_triage(root, "CAT", "web-used", result, data)
            self.assertIsNone(cache.load_triage(root, "CAT", "web-used", data))
            result["web_search_count"] = 0
            cache.save_triage(root, "CAT", "no-search", result, data)
            self.assertIsNotNone(cache.load_triage(root, "CAT", "no-search", data))
            path = cache._path(root, "triage", "CAT", "no-search")
            saved = read_json(path)
            saved["receipt"]["web_search_count"] = 1
            write_json(path, saved)
            self.assertIsNone(cache.load_triage(root, "CAT", "no-search", data))

    def test_web_enabled_without_measured_search_count_cannot_cache(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            data = model_context({**fixtures.context(), "routing_revision": 7})
            result = {**receipt(), "text": json.dumps(verdict(data, "retain"))}
            result.pop("web_search_count")
            cache.save_triage(root, "CAT", "unknown", result, data)
            self.assertIsNone(cache.load_triage(root, "CAT", "unknown", data))


class NewsResearchStageTests(unittest.TestCase):
    def setUp(self):
        self.case = fixtures.MaintenanceStageTests("test_update_builds_full_bundle_luna_provenance_and_original_completion_time")
        self.case.setUp()
        self.addCleanup(self.case.doCleanups)
        self.case.data["routing_revision"] = 7
        self.case.write_input()
        self.policy = {**fixtures.POLICY, "routing_revision": 7, "luna_news_research_enabled": True}
        write_json(self.case.work / "policy.json", self.policy)

    def run_case(self, decision="update", *, gap="none", guards=None, due=False):
        case = self.case
        value = verdict(case.data, decision)
        value["evidence_gap"] = gap
        if gap == "research":
            value["risk"]["requires_research"] = True
        self.seen = []
        def call(root, work, symbol, budget, policy, kind, data, **kwargs):
            self.seen.append((kind, deepcopy(data)))
            text = json.dumps(value) if kind == "triage" else fixtures.FIXTURE.MD.replace("02-10-2026", "03-10-2026")
            (work / f"{kind}.response").write_text(text, encoding="utf-8")
            result = {**receipt(), "text": text}
            if kind == "triage":
                (work / f"{kind}.events.jsonl").write_text(events(), encoding="utf-8")
            return result
        with ExitStack() as stack:
            stack.enter_context(patch.object(stage, "datetime", fixtures.FrozenClock))
            stack.enter_context(patch.object(stage, "maintenance_precheck", return_value={"guards": guards or [], "review_flags": []}))
            stack.enter_context(patch.object(stage, "itv_state", return_value={"due": due, "age_sessions": 1}))
            stack.enter_context(patch.object(stage, "model_call", side_effect=call))
            stack.enter_context(patch.object(stage.one, "validate_markdown", return_value=ValidationResult(ok=True, status="ok", errors=())))
            stack.enter_context(patch.object(stage, "call_codex", side_effect=AssertionError("NO REAL MODEL")))
            return stage.analyze(case.root, case.work, "CAT", case.root / "budget.json", False)

    def test_routine_web_update_one_luna_call_and_anchor_unchanged(self):
        original = (self.case.work / "input.json").read_bytes()
        result = self.run_case()
        self.assertEqual(result["status"], "updated")
        self.assertEqual([k for k, _ in self.seen], ["triage"])
        self.assertEqual(result["last_full_report_at"], self.case.data["sol_reference"]["generated_at"])
        self.assertEqual(result["luna_news_research"]["calls"][0]["sources"][0]["url"], URL)
        self.assertEqual((self.case.work / "input.json").read_bytes(), original)
        with patch.object(stage, "model_call", side_effect=AssertionError("NO REPEAT")):
            self.assertEqual(stage.analyze(self.case.root, self.case.work, "CAT", self.case.root / "budget.json", False), result)

    def test_essential_unresolved_news_passes_sources_and_finding_to_sol(self):
        result = self.run_case("escalate", gap="research")
        self.assertEqual(result["status"], "regenerated")
        self.assertEqual([k for k, _ in self.seen], ["triage", "report"])
        supplied = self.seen[1][1]
        self.assertEqual(supplied["news"]["luna_research"]["calls"][0]["sources"][0]["url"], URL)
        self.assertIn(URL, supplied["triage"]["news"]["assessment"])
        self.assertFalse(result["fallback_used"])

    def test_itv_and_critical_guards_still_go_directly_to_sol(self):
        result = self.run_case(due=True)
        self.assertEqual([k for k, _ in self.seen], ["report"])
        self.assertEqual(result["status"], "regenerated")

    def test_critical_guard_goes_directly_to_sol_without_luna_lookup(self):
        result = self.run_case(guards=["structural_stop_crossed"])
        self.assertEqual([k for k, _ in self.seen], ["report"])
        self.assertEqual(result["status"], "regenerated")

    def test_incomplete_essential_sources_still_block_before_any_model(self):
        self.case.data["news"]["truncated"] = True
        self.case.write_input()
        write_json(self.case.work / "policy.json", self.policy)
        with self.assertRaises(RuntimeError):
            self.run_case()
        self.assertEqual(self.seen, [])


class NewsResearchTransportTests(unittest.TestCase):
    def test_live_news_tool_same_luna_model_readonly_no_shell_and_actual_receipt(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            admission = SimpleNamespace(feedback=lambda **kw: None, receipt=lambda: {})
            session = SimpleNamespace(thread_id=None, completed=lambda *a, **kw: None, receipt=lambda: {})
            commands = []
            def run(command, **kwargs):
                commands.append(command)
                Path(command[command.index("--output-last-message") + 1]).write_text("{}", encoding="utf-8")
                return subprocess.CompletedProcess(command, 0, stdout=events(), stderr="")
            with patch.object(codex, "require_codex", return_value="codex"), \
                 patch.object(codex, "_capacity_admission", return_value=nullcontext(admission)), \
                 patch.object(codex, "session_lease", return_value=nullcontext(session)), \
                 patch.object(codex, "parse_codex_jsonl_usage", return_value={"input_tokens": 100}), \
                 patch.object(codex, "run_bounded", side_effect=run):
                result = codex.call_codex(workspace=root / "work", artifacts=root / "CAT", kind="triage",
                    instructions=news_research_instructions("prefix", enabled=True), data={"symbol": "CAT"},
                    model="gpt-6-luna", effort="high", timeout=240, schema={"type": "object"}, research=True)
            command = commands[0]
            for setting in ('web_search="live"', 'features.shell_tool=false', 'apps._default.enabled=false', 'forced_login_method="chatgpt"'):
                self.assertIn(setting, command)
            self.assertEqual(command[command.index("--sandbox") + 1], "read-only")
            self.assertEqual(result["web_search_count"], 1)
            collected = collect_news_research((root / "CAT/triage.events.jsonl").read_text(encoding="utf-8"), result,
                                              {"news": {"assessment": URL}})
            self.assertEqual(collected["sources"][0]["url"], URL)

    def test_stage_enables_same_prefix_for_triage_and_repair_but_not_legacy(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for revision in (6, 7):
                for kind in ("triage", "triage_repair"):
                    work = root / f"{revision}-{kind}"
                    work.mkdir()
                    (work / "triage_instructions.md").write_text("frozen", encoding="utf-8")
                    data = {**fixtures.context(), "routing_revision": revision}
                    policy = {**fixtures.POLICY, "routing_revision": revision, "luna_news_research_enabled": True,
                              "triage_model": "gpt-6-luna", "triage_effort": "high"}
                    with patch.object(stage, "reserve", return_value=f"CAT:{kind}"), \
                         patch.object(stage, "finish"), patch.object(stage, "load_triage", return_value=None), \
                         patch.object(stage, "call_codex", side_effect=RuntimeError("offline_probe")) as call:
                        with self.assertRaisesRegex(RuntimeError, "offline_probe"):
                            stage.model_call(root, work, "CAT", root / "budget.json", policy, kind, data)
                    self.assertEqual(call.call_args.kwargs["research"], revision == 7)
                    self.assertEqual(call.call_args.kwargs["model"], "gpt-6-luna")
                    self.assertEqual(call.call_args.kwargs["effort"], "high")
                    self.assertEqual(call.call_args.kwargs["instructions"], news_research_instructions("frozen", enabled=revision == 7))


if __name__ == "__main__":
    unittest.main()
