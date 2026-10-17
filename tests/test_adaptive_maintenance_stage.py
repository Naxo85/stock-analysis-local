"""Offline revision-3 integration: real patch/JSON/HTML, mocked models and GCS.

The compact maintenance fixture omits the full strength rubric, so the common
report validator is mocked only in analyze integration tests. Authority checks,
date/price/topology checks in apply_update and report serialization stay real.
"""
from __future__ import annotations

from contextlib import ExitStack
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from src.common.analysis_validator import ValidationResult
from src.local_runner import adaptive_cache as cache
from src.local_runner import adaptive_current as current
from src.local_runner import adaptive_stage as stage
from src.local_runner.adaptive_budget import read_json, write_json
from src.local_runner.adaptive_context import model_context
from src.local_runner.adaptive_maintenance import maintenance_schema
from src.local_runner.adaptive_policy import load_policy

ROOT = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 10, 3, 10, tzinfo=timezone.utc)
COMPLETED = datetime(2026, 10, 3, 9, 50, tzinfo=timezone.utc)
POLICY = {**load_policy(ROOT), "routing_revision": 3}
_spec = importlib.util.spec_from_file_location("maintenance_stage_fixture",
                                              ROOT / "tests/test_adaptive_maintenance.py")
FIXTURE = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(FIXTURE)


class FrozenClock(datetime):
    @classmethod
    def now(cls, tz=None):
        return NOW if tz is not None else NOW.replace(tzinfo=None)


def context():
    value = FIXTURE.context()
    value.update(symbol="CAT", owned=False, tier="tracking", routing_revision=3,
                 prepared_at=NOW.isoformat(), analyst_quality={}, analyst_summary={})
    value["slim"]["as_of"] = NOW.isoformat()
    for name in ("news", "analyst_actions"):
        value[name].update(status="ok", generated_at=NOW.isoformat())
    value["news"]["window"] = {"start": value["sol_reference"]["generated_at"]}
    for name in ("reference", "sol_reference"):
        value[name].update(symbol="CAT", generation_model="gpt-6.1-sol", reasoning_effort="high",
                           latest_price=100, decision={"score": 8})
    return value


def update_payload(data):
    value = FIXTURE.payload()
    value["base_markdown_sha256"] = hashlib.sha256(data["reference"]["analysis_markdown"].encode()).hexdigest()
    return value


class MaintenanceStageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.work = self.root / "batch/adaptive/CAT"
        self.work.mkdir(parents=True)
        self.data = context()
        self.write_input()

    def write_input(self):
        write_json(self.work / "input.json", self.data)
        write_json(self.work / "policy.json", POLICY)

    def run_analyze(self, verdict=None, *, exception=None, invalid_update=False):
        verdict = update_payload(self.data) if verdict is None else verdict
        seen = []

        def call(root, work, symbol, budget, policy, kind, data, **kwargs):
            seen.append((kind, deepcopy(data)))
            if exception:
                raise exception
            text = json.dumps(verdict) if kind == "triage" else FIXTURE.MD.replace("02-10-2026", "03-10-2026")
            (work / (kind + ".response")).write_text(text, encoding="utf-8")
            return {"text": text, "exit_code": 0, "completed_at": COMPLETED.isoformat(),
                    "model": policy["triage_model" if kind == "triage" else "report_model"],
                    "reasoning_effort": policy["triage_effort" if kind == "triage" else "report_effort"],
                    "usage": {"input_tokens": 100, "output_tokens": 20}}

        valid = ValidationResult(ok=True, status="ok", errors=())
        invalid = ValidationResult(ok=False, status="failed", errors=("unsupported hypothetical level",))
        with ExitStack() as stack:
            stack.enter_context(patch.object(stage, "datetime", FrozenClock))
            stack.enter_context(patch.object(stage, "maintenance_precheck",
                return_value={"guards": [], "review_flags": []}))
            stack.enter_context(patch.object(stage, "itv_state", return_value={"due": False, "age_sessions": 1}))
            stack.enter_context(patch.object(stage, "model_call", side_effect=call))
            stack.enter_context(patch.object(stage.one, "validate_markdown",
                side_effect=[invalid, valid] if invalid_update else None,
                return_value=valid))
            stack.enter_context(patch.object(stage, "reserve", side_effect=AssertionError("NO REAL MODEL RESERVATION")))
            stack.enter_context(patch.object(stage, "call_codex", side_effect=AssertionError("NO REAL MODEL CALL")))
            self.seen = seen
            return stage.analyze(self.root, self.work, "CAT", self.root / "budget.json", False)

    def test_update_builds_full_bundle_luna_provenance_and_original_completion_time(self):
        result = self.run_analyze()
        staged = self.work / "publish/output/CAT"
        payload = read_json(staged / "latest.json")
        markdown = (staged / "latest.md").read_text(encoding="utf-8")
        html = (staged / "latest.html").read_text(encoding="utf-8")
        self.assertEqual(result["status"], "updated")
        self.assertEqual(result["effective_model"], POLICY["triage_model"])
        self.assertEqual(payload["generation_model"], POLICY["triage_model"])
        self.assertEqual(payload["analysis_kind"], "daily_update")
        self.assertEqual(payload["generated_at"], COMPLETED.isoformat())
        self.assertEqual(payload["last_full_report_at"], self.data["sol_reference"]["generated_at"])
        self.assertEqual(payload["reference_generated_at"], self.data["sol_reference"]["generated_at"])
        self.assertEqual(payload["sol_anchor_sha256"], cache.reference_key(self.data["sol_reference"]))
        self.assertEqual(payload["maintenance"]["base_report_sha256"], cache.reference_key(self.data["reference"]))
        self.assertEqual(payload["analysis_markdown"], markdown)
        self.assertTrue(markdown.startswith("Mantenimiento técnico: Luna"))
        self.assertIn("Sol · 2026-10-02", markdown)
        self.assertIn("Mantenimiento técnico: Luna", html)
        self.assertIn("Tesis: 8 / 10", markdown)
        self.assertIn("Guidance mantenido.", markdown)
        self.assertEqual([kind for kind, _ in self.seen], ["triage"])
        with patch.object(stage, "model_call", side_effect=AssertionError("NO REPEAT")):
            self.assertEqual(stage.analyze(self.root, self.work, "CAT", self.root / "budget.json", False), result)

    def test_revision4_omitted_date_update_stays_luna_preserves_sol_age_and_recovers(self):
        self.data['routing_revision'] = 4
        self.write_input()
        write_json(self.work / 'policy.json', {**POLICY, 'routing_revision': 4})
        verdict = update_payload(self.data)
        verdict['edits'] = [FIXTURE.edit('Setup: 6 / 10', 'Setup: 6,5 / 10')]
        result = self.run_analyze(verdict)
        self.assertEqual(result['status'], 'updated')
        self.assertEqual([kind for kind, _ in self.seen], ['triage'])
        self.assertEqual(result['last_full_report_at'], self.data['sol_reference']['generated_at'])
        self.assertIn('exact_inherited_maintenance_date_refresh',
                      [row['method'] for row in result['maintenance_normalizations']])
        bundle = read_json(self.work / 'publish/output/CAT/latest.json')
        self.assertEqual(bundle['last_full_report_at'], self.data['sol_reference']['generated_at'])
        self.assertIn('Fecha del análisis: 03-10-2026', bundle['analysis_markdown'])
        with patch.object(stage, 'model_call', side_effect=AssertionError('NO REPEAT')):
            self.assertEqual(stage.analyze(self.root, self.work, 'CAT', self.root / 'budget.json', False), result)

    def test_luna_receives_distinct_exact_current_and_original_sol_views(self):
        self.data["reference"]["analysis_markdown"] = FIXTURE.MD.replace("Setup: 6 / 10", "Setup: 6,5 / 10")
        self.data["reference"].update(generated_at="2026-10-03T09:00:00Z", generation_model="gpt-6-luna")
        original = deepcopy(self.data)
        self.write_input()
        self.run_analyze()
        observed = model_context(self.seen[0][1])
        self.assertEqual(observed["reference"]["analysis_markdown"], original["reference"]["analysis_markdown"])
        self.assertEqual(observed["sol_reference"]["analysis_markdown"], original["sol_reference"]["analysis_markdown"])
        self.assertNotEqual(observed["reference"], observed["sol_reference"])
        self.assertTrue(observed["comparison"]["compare_cumulative_changes_against_sol"])
        self.assertEqual(observed["comparison"]["last_full_sol_report_at"], original["sol_reference"]["generated_at"])
        self.assertEqual(read_json(self.work / "input.json"), original)

    def test_prepare_freezes_maintained_current_but_sources_cover_original_sol_age(self):
        anchor = deepcopy(self.data["sol_reference"])
        maintained = {**deepcopy(anchor), "analysis_markdown": FIXTURE.MD.replace("Setup: 6 / 10", "Setup: 6,5 / 10"),
                      "generation_model": "gpt-6-luna", "generated_at": "2026-10-03T09:00:00Z"}
        (self.work / "input.json").unlink()
        prompts = self.root / "prompts"
        prompts.mkdir()
        (prompts / "daily_maintenance.md").write_text("Frozen maintenance contract", encoding="utf-8")
        with ExitStack() as stack:
            stack.enter_context(patch.object(stage, "datetime", FrozenClock))
            stack.enter_context(patch.object(stage, "load_policy", return_value=POLICY))
            stack.enter_context(patch.object(stage, "load_reference_payload", return_value=anchor))
            loader = stack.enter_context(patch.object(stage, "load_current_report", return_value=maintained))
            stack.enter_context(patch.object(stage.one, "_fetch_slim", return_value=self.data["slim"]))
            stack.enter_context(patch.object(stage.one, "_load_analyst_quality", return_value={}))
            stack.enter_context(patch.object(stage.one, "load_compact_analyst_summary", return_value={}))
            actions = stack.enter_context(patch.object(stage.one, "load_recent_analyst_actions", return_value=self.data["analyst_actions"]))
            stack.enter_context(patch.object(stage.one, "load_recent_news", return_value=self.data["news"]))
            stack.enter_context(patch.object(stage.one, "_load_system_prompt", return_value="Stable full rubric"))
            stack.enter_context(patch.object(stage, "load_research", return_value=None))
            stack.enter_context(patch.object(stage, "run_bounded", side_effect=AssertionError("NO SOURCE GAP OR MODEL")))
            stage.prepare(self.root, self.work, "CAT", False, "tracking")
        loader.assert_called_once_with(self.root, "CAT", anchor)
        self.assertEqual(actions.call_args.kwargs["since"], anchor["generated_at"])
        self.assertIsNone(actions.call_args.kwargs["limit"])
        frozen = read_json(self.work / "input.json")
        self.assertEqual(frozen["reference"], maintained)
        self.assertEqual(frozen["sol_reference"], anchor)
        self.assertEqual(frozen["routing_revision"], 3)
        self.assertIn("Stable full rubric", (self.work / "triage_instructions.md").read_text(encoding="utf-8"))

    def test_unsafe_patch_is_recorded_escalation_not_silent_fallback(self):
        verdict = update_payload(self.data)
        verdict["edits"].append(FIXTURE.edit("Tesis: 8 / 10", "Tesis: 2 / 10"))
        result = self.run_analyze(verdict)
        self.assertEqual([kind for kind, _ in self.seen], ["triage", "report"])
        self.assertEqual(result["status"], "regenerated")
        self.assertEqual(result["effective_model"], POLICY["report_model"])
        self.assertFalse(result["fallback_used"])
        rejection = read_json(self.work / "update_rejected.json")
        self.assertEqual(rejection["next"], "sol_review")
        self.assertEqual(result["maintenance_escalation"], rejection["reason"])
        self.assertEqual(self.seen[1][1]["maintenance_escalation"], rejection["reason"])

    def test_common_validator_rejection_escalates_and_records_evidence(self):
        result = self.run_analyze(invalid_update=True)
        self.assertEqual(result["status"], "regenerated")
        self.assertEqual([kind for kind, _ in self.seen], ["triage", "report"])
        self.assertFalse(read_json(self.work / "update_validation.json")["ok"])
        self.assertTrue(read_json(self.work / "update_rejected.json")["reason"])

    def test_malformed_patch_contract_never_calls_sol(self):
        cases = [update_payload(self.data), update_payload(self.data)]
        cases[0]["base_markdown_sha256"] = "incorrect"
        cases[1]["edits"][0]["before"] = "not present anywhere"
        for verdict in cases:
            with self.subTest(verdict=verdict), self.assertRaises(ValueError):
                self.run_analyze(verdict)
            self.assertEqual([kind for kind, _ in self.seen], ["triage"])
            self.assertFalse((self.work / "review.json").exists())
            self.assertFalse((self.work / "update_rejected.json").exists())

    def test_provider_error_never_calls_sol_or_stages_fake_success(self):
        with self.assertRaises(RuntimeError):
            self.run_analyze(exception=RuntimeError("provider unavailable"))
        self.assertEqual([kind for kind, _ in self.seen], ["triage"])
        self.assertFalse((self.work / "review.json").exists())
        self.assertFalse((self.work / "publish/output/CAT/latest.json").exists())

    def test_data_coverage_starts_at_sol_not_newer_luna_update(self):
        self.data["reference"]["generated_at"] = "2026-10-03T09:00:00Z"
        self.data["news"]["window"]["start"] = "2026-10-03T08:00:00Z"
        self.write_input()
        with patch.object(stage, "model_call", side_effect=AssertionError("NO MODEL FOR SOURCE GAP")):
            with self.assertRaises(RuntimeError):
                stage.data_ready(self.data, POLICY, NOW)
        self.data["news"]["window"]["start"] = self.data["sol_reference"]["generated_at"]
        stage.data_ready(self.data, POLICY, NOW)

    def test_malformed_support_actions_and_future_reference_fail_before_any_model(self):
        variants = []
        for supports in ({"level": 90}, [], [{"level": None}], [{"level": -1}], ["bad"],
                         [{"level": True}], [{"level": "90"}], [{"level": float("nan")}],
                         [{"level": float("inf")}], [{"level": 90}, {"level": 0}],
                         [{"level": 90}, "malformed second level"]):
            value = deepcopy(self.data)
            value["slim"]["levels"]["supports"] = supports
            variants.append(value)
        for name, field in (("analyst_actions", "actions"), ("news", "items")):
            for items in ({}, ["bad"], [{}, "malformed second item"], [None]):
                value = deepcopy(self.data)
                value[name][field] = items
                variants.append(value)
        for name in ("slim", "news", "analyst_actions"):
            for source in (None, [], "bad source"):
                value = deepcopy(self.data)
                value[name] = source
                variants.append(value)
        for levels in (None, [], "bad levels"):
            value = deepcopy(self.data)
            value["slim"]["levels"] = levels
            variants.append(value)
        for name in ("reference", "sol_reference"):
            value = deepcopy(self.data)
            value[name]["generated_at"] = "2099-01-01T00:00:00Z"
            variants.append(value)
        for value in variants:
            with self.subTest(value=value), self.assertRaises((RuntimeError, ValueError, TypeError)):
                stage.data_ready(value, POLICY, NOW)
            self.data = value
            self.write_input()
            with self.assertRaises((RuntimeError, ValueError, TypeError)):
                self.run_analyze()
            self.assertEqual(self.seen, [])

    def test_cache_invalidates_changes_to_either_current_report_or_sol_anchor(self):
        data = model_context(self.data)
        schema = maintenance_schema(data)
        baseline = cache.triage_key(data, POLICY, "stable", schema, NOW)
        for name in ("reference", "sol_reference"):
            for field in ("analysis_markdown", "generated_at"):
                changed = deepcopy(data)
                changed[name][field] += " changed"
                with self.subTest(name=name, field=field):
                    self.assertNotEqual(cache.triage_key(changed, POLICY, "stable", schema, NOW), baseline)
        changed = deepcopy(data)
        changed["prepared_at"] = "2026-10-03T10:01:00Z"
        self.assertEqual(cache.triage_key(changed, POLICY, "stable", schema, NOW), baseline)

    def test_exact_cached_update_keeps_original_receipt_and_cannot_follow_report_change(self):
        data = model_context(self.data)
        verdict = update_payload(data)
        schema = maintenance_schema(data)
        key = cache.triage_key(data, POLICY, "stable", schema, NOW)
        receipt = {"text": json.dumps(verdict), "exit_code": 0,
                   "usage": {"input_tokens": 100, "output_tokens": 20},
                   "completed_at": COMPLETED.isoformat(), "model": POLICY["triage_model"]}
        cache.save_triage(self.root, "CAT", key, receipt, data)
        loaded = cache.load_triage(self.root, "CAT", key, data)
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded["receipt"]["completed_at"], COMPLETED.isoformat())
        self.assertEqual(json.loads(loaded["text"]), verdict)
        changed = deepcopy(data)
        changed["reference"]["analysis_markdown"] = FIXTURE.MD.replace("Setup: 6 / 10", "Setup: 6,5 / 10")
        new_key = cache.triage_key(changed, POLICY, "stable", schema, NOW)
        self.assertNotEqual(new_key, key)
        self.assertIsNone(cache.load_triage(self.root, "CAT", new_key, changed))

    def test_publish_update_uploads_bundle_and_current_state_never_replaces_sol_anchor(self):
        self.run_analyze()
        with patch.object(stage, "_read_json_gcs", side_effect=self.remote), \
             patch.object(stage.one, "_upload") as upload, patch.object(stage, "_copy_json") as copy, \
             patch.object(stage, "save_reference_payload") as save:
            review = stage.publish(self.root, self.work, "CAT")
            stage.publish(self.root, self.work, "CAT")
        save.assert_not_called()
        upload.assert_called_once_with(self.work / "publish", "CAT", upload_kind="real", dry_run=False)
        self.assertEqual(copy.call_count, 2)
        self.assertEqual(copy.call_args_list[0].args[1], current.current_uri("CAT"))
        state = read_json(self.root / "data/analysis_state/CAT/current.json")
        self.assertEqual(state["generation_model"], POLICY["triage_model"])
        self.assertEqual(state["sol_anchor_sha256"], cache.reference_key(self.data["sol_reference"]))
        self.assertEqual(state["last_full_report_at"], self.data["sol_reference"]["generated_at"])
        self.assertTrue(review["published_at"])
        for extension in ("md", "html", "json"):
            self.assertEqual((self.root / ("output/CAT/latest." + extension)).read_bytes(),
                             (self.work / ("publish/output/CAT/latest." + extension)).read_bytes())

    def remote(self, uri):
        return self.data["sol_reference"] if uri.endswith("/reference.json") else self.data["reference"]

    def test_partial_publish_retry_is_idempotent_from_frozen_bundle(self):
        self.run_analyze()
        candidate = read_json(self.work / "publish/output/CAT/latest.json")
        remote_latest = deepcopy(self.data["reference"])
        attempts = 0

        def upload(*args, **kwargs):
            nonlocal remote_latest
            remote_latest = deepcopy(candidate)

        def read_remote(uri):
            return self.data["sol_reference"] if uri.endswith("/reference.json") else remote_latest

        def copy(source, uri):
            nonlocal attempts
            if uri == current.current_uri("CAT"):
                attempts += 1
                if attempts == 1:
                    raise RuntimeError("partial GCS upload")

        with patch.object(stage, "_read_json_gcs", side_effect=read_remote), \
             patch.object(stage.one, "_upload", side_effect=upload) as bundle, \
             patch.object(stage, "_copy_json", side_effect=copy) as state_copy, \
             patch.object(stage, "save_reference_payload") as save:
            with self.assertRaises(RuntimeError):
                stage.publish(self.root, self.work, "CAT")
            self.assertFalse(read_json(self.work / "review.json").get("published_at"))
            stage.publish(self.root, self.work, "CAT")
            stage.publish(self.root, self.work, "CAT")
        self.assertEqual(bundle.call_count, 2)
        self.assertEqual(state_copy.call_count, 3)
        save.assert_not_called()
        self.assertEqual(remote_latest, candidate)
        self.assertTrue(read_json(self.work / "review.json")["published_at"])

    def test_maintenance_publish_requires_valid_remote_full_sol_anchor(self):
        self.run_analyze()
        for missing in ({}, {"analysis_status": "failed"}):
            def remote(uri):
                return missing if uri.endswith("/reference.json") else self.data["reference"]
            with self.subTest(remote=missing), patch.object(stage, "_read_json_gcs", side_effect=remote), \
                 patch.object(stage.one, "_upload") as upload, patch.object(stage, "_copy_json") as copy:
                with self.assertRaisesRegex(RuntimeError, "missing_or_invalid_sol_anchor"):
                    stage.publish(self.root, self.work, "CAT")
                upload.assert_not_called()
                copy.assert_not_called()

    def test_publish_rejects_changed_current_or_sol_anchor_before_upload(self):
        self.run_analyze()
        for changed_name in ("reference", "sol_reference"):
            mutated = deepcopy(self.data)
            mutated[changed_name]["analysis_markdown"] += "\nConcurrent report changed"
            def remote(uri):
                return mutated["sol_reference"] if uri.endswith("/reference.json") else mutated["reference"]
            with self.subTest(changed=changed_name), patch.object(stage, "_read_json_gcs", side_effect=remote), \
                 patch.object(stage.one, "_upload") as upload, patch.object(stage, "_copy_json") as copy:
                with self.assertRaises(RuntimeError):
                    stage.publish(self.root, self.work, "CAT")
                upload.assert_not_called()
                copy.assert_not_called()


class MaintainedCurrentLoaderTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.anchor = context()["sol_reference"]
        self.current = {**deepcopy(self.anchor), "generated_at": "2026-10-03T09:00:00Z",
            "generation_model": "gpt-6-luna", "analysis_markdown": "maintained valid report",
            "last_full_report_at": self.anchor["generated_at"],
            "sol_anchor_sha256": cache.reference_key(self.anchor)}

    def load(self, value=None, *, raw=None, anchor=None):
        raw = json.dumps(self.current if value is None else value) if raw is None else raw
        with patch.object(current, "read_text_gcs", return_value=raw):
            return current.load_current_report(self.root, "cat", self.anchor if anchor is None else anchor)

    def test_valid_maintained_current_and_missing_state(self):
        self.assertEqual(self.load(), self.current)
        with patch.object(current, "read_text_gcs", return_value=None):
            self.assertEqual(current.load_current_report(self.root, "CAT", self.anchor), self.anchor)

    def test_new_sol_anchor_supersedes_update_of_old_anchor(self):
        newer = {**deepcopy(self.anchor), "generated_at": "2026-10-03T09:30:00Z"}
        self.assertEqual(self.load(anchor=newer), newer)

    def test_same_or_older_anchor_mismatch_cannot_discard_maintenance(self):
        incompatible = {**self.current, "sol_anchor_sha256": "wrong"}
        for anchor in (self.anchor, {**self.anchor, "generated_at": "2026-10-01T10:00:00Z"}):
            with self.subTest(anchor=anchor), self.assertRaises(RuntimeError):
                self.load(incompatible, anchor=anchor)

    def test_corrupt_state_wrong_symbol_failed_status_and_missing_timestamp_are_visible(self):
        for raw in ("not json", "[]", "42"):
            with self.subTest(raw=raw), self.assertRaises((RuntimeError, ValueError)):
                self.load(raw=raw)
        for field, value in (("symbol", "AMD"), ("analysis_status", "failed"),
                             ("analysis_markdown", ""), ("generated_at", "invalid")):
            with self.subTest(field=field), self.assertRaises(RuntimeError):
                self.load({**self.current, field: value})

    def test_future_current_timestamp_is_not_accepted_as_valid_state(self):
        with self.assertRaises(RuntimeError):
            self.load({**self.current, "generated_at": "2099-01-01T00:00:00Z"})

    def test_network_failure_uses_only_valid_local_current_or_fails_visibly(self):
        with patch.object(current, "read_text_gcs", side_effect=RuntimeError("offline")):
            with self.assertRaises(RuntimeError):
                current.load_current_report(self.root, "CAT", self.anchor)
            write_json(self.root / "data/analysis_state/CAT/current.json", self.current)
            self.assertEqual(current.load_current_report(self.root, "CAT", self.anchor), self.current)
            write_json(self.root / "data/analysis_state/CAT/current.json", {**self.current, "symbol": "AMD"})
            with self.assertRaises(RuntimeError):
                current.load_current_report(self.root, "CAT", self.anchor)


if __name__ == "__main__":
    unittest.main()
