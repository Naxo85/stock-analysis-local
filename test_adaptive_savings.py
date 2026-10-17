import hashlib
import json
import tempfile
import unittest
from copy import deepcopy
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch
from test_adaptive_analysis import NOW, ROOT, POLICY, triage
import test_adaptive_analysis as fixtures
from src.local_runner import adaptive_stage as stage, adaptive_budget as budget, adaptive_cache as cache
from src.local_runner.adaptive_policy import triage_schema
from src.local_runner.adaptive_context import model_context, pack_model_context, unpack_model_context, serialize_model_input
from src.local_runner.analyst_recent_actions import load_recent_analyst_actions
from src.local_runner.run_batch import _analysis_worker_count


class SavingsTests(unittest.TestCase):
    def context(self):
        value = fixtures.StageTests().context()
        value.update(guards=[], itv={"due": False})
        return model_context(value)

    def test_six_model_workers_are_effective_not_just_configured(self):
        self.assertEqual(POLICY["max_model_parallel"], 6)
        self.assertEqual(_analysis_worker_count(ticker_count=46, browser_session=None,
            generator_fallback=False, max_parallel=6, model_parallel=POLICY["max_model_parallel"]), 6)
        self.assertEqual(_analysis_worker_count(ticker_count=2, browser_session=None,
            generator_fallback=False, max_parallel=6, model_parallel=6), 2)

    def test_six_models_overlap_in_the_actual_pipeline(self):
        import threading
        from test_run_batch_pipeline import _config, _ok_stage
        from src.local_runner.run_batch import _PipelineTracker, _run_ticker_pass, BatchConfig
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tickers = tuple("T" + str(i) for i in range(6))
            original = _config(root, tickers)
            config = BatchConfig(**{**original.__dict__, "max_parallel": 6, "adaptive_codex": True})
            tracker = _PipelineTracker(config.log_dir / "pipeline_state.json", tickers=tickers,
                source="test", started_at=NOW, resume=False)
            barrier = threading.Barrier(6)
            def fake_stage(config, task, name):
                if name == "analyze":
                    barrier.wait(timeout=5)
                return _ok_stage(task, name)
            with patch("src.local_runner.adaptive_policy.load_policy", return_value=POLICY), patch(
                    "src.local_runner.run_batch._run_pipeline_stage", side_effect=fake_stage):
                results = _run_ticker_pass(config, tickers, attempt=1, tracker=tracker)
            self.assertEqual(sum(r["status"] == "ok" for r in results), 6)

    def test_lossless_aliases_identical_and_different_snapshots(self):
        evidence = {"all": list(range(100)), "text": "No loss / ~ Unicode á"}
        for changed in (False, True):
            value = {"slim": {"levels": evidence}, "reference": {"slim_snapshot": {"levels": deepcopy(evidence)}},
                     "news": {"items": [deepcopy(evidence), deepcopy(evidence)]},
                     "literal": {"$same_as": "/not/an/alias"}, "odd/key~": deepcopy(evidence)}
            if changed:
                value["reference"]["slim_snapshot"]["levels"]["all"][0] = -1
            original = deepcopy(value)
            packed = pack_model_context(value)
            self.assertEqual(unpack_model_context(packed), original)
            self.assertEqual(value, original)
            self.assertLess(len(serialize_model_input(value)), len(json.dumps(value, ensure_ascii=False)))

    def test_real_saved_inputs_roundtrip_with_all_news_and_fields(self):
        for symbol in ("CAT", "NVDA"):
            path = ROOT / "logs/adaptive_smoke/20261001T111917974635" / symbol / "triage.input.json"
            if not path.exists():
                self.skipTest("local saved smoke not available")
            value = model_context(json.loads(path.read_text(encoding="utf-8")))
            packed = json.loads(serialize_model_input(value))
            self.assertEqual(unpack_model_context(packed), value)
            self.assertLess(len(serialize_model_input(value)), len(json.dumps(value)) * .8)

    def test_due_itv_and_guards_skip_luna(self):
        for guards, due in (([], True), (["price_below_management_stop"], False)):
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                budget.write_json(root / "input.json", self.context())
                budget.write_json(root / "policy.json", POLICY)
                with patch.object(stage, "data_ready"), patch.object(stage, "safeguards", return_value=guards), patch.object(stage, "itv_state", return_value={"due": due}), patch.object(stage, "model_call", side_effect=RuntimeError("stop before report generation")) as model:
                    with self.assertRaises(RuntimeError):
                        stage.analyze(root, root, "CAT", root / "budget.json", False)
                self.assertEqual(model.call_count, 1)
                self.assertEqual(model.call_args.args[5], "report")

    def test_uncapped_input_and_all_analyst_actions(self):
        value = self.context()
        value["reference"]["analysis_markdown"] = "x" * 180001
        for key in ("news", "analyst_actions"):
            value[key]["as_of"] = NOW.isoformat()
        value["news"]["window"] = {"start": NOW.isoformat()}
        stage.data_ready(value, {**POLICY, "max_input_chars": 1}, NOW)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / "data/analyst_ratings/CAT/current.json"
            budget.write_json(path, {"as_of": NOW.isoformat(), "firms": {str(i): {
                "firm": str(i), "last_event": {"published_at": NOW.isoformat(), "headline": str(i)}} for i in range(1001)}})
            payload = load_recent_analyst_actions(root, "CAT", since=(NOW - timedelta(days=1)).isoformat(), limit=None)
            self.assertEqual(len(payload["actions"]), 1001)
            self.assertFalse(payload["truncated"])

    def test_exact_cache_invalidates_evidence_contract_day_and_event(self):
        value = self.context()
        value["reference"]["next_event"] = {"at": (NOW + timedelta(hours=1)).isoformat()}
        schema = triage_schema(value)
        key = cache.triage_key(value, POLICY, "same", schema, NOW)
        later_prepared = {**value, "prepared_at": (NOW + timedelta(minutes=1)).isoformat()}
        self.assertEqual(key, cache.triage_key(later_prepared, POLICY, "same", schema, NOW + timedelta(minutes=1)))
        for change in ("slim", "news", "analyst_actions", "reference", "guards", "itv"):
            new = deepcopy(value)
            new[change] = {"different": True}
            self.assertNotEqual(key, cache.triage_key(new, POLICY, "same", schema, NOW))
        for clock in (NOW + timedelta(hours=2), NOW + timedelta(days=1)):
            self.assertNotEqual(key, cache.triage_key(value, POLICY, "same", schema, clock))
        self.assertNotEqual(key, cache.triage_key(value, POLICY, "changed", schema, NOW))
        self.assertNotEqual(key, cache.triage_key(value, {**POLICY, "triage_model": "different"}, "same", schema, NOW))

    def test_cache_across_launches_zero_new_calls_and_corruption_is_miss(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            value = self.context()
            def fake_call(**kw):
                return {"text": json.dumps(triage()), "exit_code": 0, "usage": {"input_tokens": 100, "output_tokens": 5},
                        "model": kw["model"], "reasoning_effort": kw["effort"], "research_enabled": False,
                        "input_sha256": hashlib.sha256(serialize_model_input(kw["data"]).encode()).hexdigest(),
                        "instructions_sha256": hashlib.sha256(kw["instructions"].encode()).hexdigest(),
                        "schema_sha256": hashlib.sha256(json.dumps(kw["schema"], sort_keys=True).encode()).hexdigest()}
            for name in ("first", "second", "third"):
                work = root / name
                work.mkdir()
                (work / "triage_instructions.md").write_text("same", encoding="utf-8")
            with patch.object(stage, "call_codex", side_effect=fake_call) as model, patch.object(budget, "read_codex_rate_limits", return_value={"primary": {"used_percent": 5}}):
                stage.model_call(root, root / "first", "CAT", root / "budget1.json", POLICY, "triage", value)
                result = stage.model_call(root, root / "second", "CAT", root / "budget2.json", POLICY, "triage", {**value, "prepared_at": "new bookkeeping only"})
                self.assertTrue(result["cache_reused"])
                self.assertEqual(result["usage"]["total_tokens"], 0)
                self.assertEqual(model.call_count, 1)
                recovered = stage.model_call(root, root / "second", "CAT", root / "budget2.json", POLICY, "triage", {**value, "prepared_at": "new bookkeeping only"})
                self.assertTrue(recovered["cache_reused"])
                path = next((root / ".local/adaptive-cache/triage").rglob("*.json"))
                corrupt = budget.read_json(path)
                corrupt["text"] = json.dumps(triage("escalate"))
                budget.write_json(path, corrupt)
                stage.model_call(root, root / "third", "CAT", root / "budget3.json", POLICY, "triage", value)
                self.assertEqual(model.call_count, 2)

    def test_research_is_report_bound_dated_and_not_claimed_verified(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            payload = {"generated_at": NOW.isoformat(), "generation_model": "gpt-6.1-sol",
                       "analysis_markdown": "Historical earnings [IR](https://company.test/results)\n\nRisk [Filing](https://sec.test/filing)"}
            (root / "report.events.jsonl").write_text(json.dumps({"type": "item.completed", "item": {
                "type": "web_search", "results": [{"url": "https://company.test/next", "title": "Next"}]}}), encoding="utf-8")
            cache.save_research(root, root, "CAT", payload)
            memory = cache.load_research(root, "CAT", payload)
            self.assertEqual(len(memory["cited_evidence"]), 2)
            self.assertEqual(memory["as_of_report"], payload["generated_at"])
            self.assertIn("not_verified", memory["discovery_sources"][0]["provenance"])
            self.assertIsNone(cache.load_research(root, "CAT", {**payload, "analysis_markdown": "new baseline"}))
            self.assertIsNone(cache.load_research(root, "AMD", payload))

    def test_malformed_cache_is_a_miss_not_a_batch_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            value = self.context()
            key = cache.triage_key(value, POLICY, "same", triage_schema(value), NOW)
            path = cache._path(root, "triage", "CAT", key)
            for malformed in ([], {"receipt": []}, {"receipt": {"usage": []}}, {"text": "bad"}):
                budget.write_json(path, malformed)
                self.assertIsNone(cache.load_triage(root, "CAT", key, value))
            path = cache._path(root, "research", "CAT", cache.reference_key(value["reference"]))
            budget.write_json(path, [])
            self.assertIsNone(cache.load_research(root, "CAT", value["reference"]))

    def test_stale_sources_block_before_cache_or_model(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            context = self.context()
            context["slim"]["as_of"] = "2020-01-01"
            budget.write_json(root / "input.json", context)
            budget.write_json(root / "policy.json", POLICY)
            with patch.object(stage, "model_call") as model:
                with self.assertRaisesRegex(RuntimeError, "stale"):
                    stage.analyze(root, root, "CAT", root / "budget.json", False)
                model.assert_not_called()


if __name__ == "__main__":
    unittest.main()
