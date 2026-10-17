"""Pure factual delta tests: never call a model, GCS or a source refresh."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import unittest

from src.local_runner.adaptive_delta import deterministic_comparison
from src.local_runner.adaptive_context import model_context, serialize_model_input, unpack_model_context
from src.local_runner.adaptive_maintenance import maintenance_schema, maintenance_decision, apply_update
from src.local_runner.adaptive_policy import load_policy

ROOT = Path(__file__).resolve().parents[1]


def fixture():
    slim = {"as_of": "2026-10-03T07:00:00+00:00", "latest_price": 46.795,
        "mirror_url": "https://example.test/old", "technicals": {"rsi14": 50},
        "levels": {"supports": [{"level": 45}], "put_walls_top": [
            {"level": 45, "expiration": "2026-10-09", "oi": 100, "gamma_share_pct": 12.2}]},
        "options": {"expirations": [{"date": "2026-10-09", "dte": 6}]}}
    item = {"articleId": "a", "providerCode": "DJ-N", "published_at": "2026-10-03T06:00:00Z", "headline": "Known risk"}
    ref = {"generated_at": "2026-10-03T08:00:00+00:00", "latest_price": 46.795,
        "analysis_markdown": "# MP\n**Salida / objetivo principal: $47.00 (+0.4%)**",
        "slim_snapshot": deepcopy(slim), "ibkr_recent_news": {"items": [item]},
        "analyst_recent_actions": {"actions": []}}
    return {"routing_revision": 4, "reference": ref, "sol_reference": deepcopy(ref),
        "slim": slim, "news": {"status": "ok", "items": [deepcopy(item)], "truncated": False},
        "analyst_actions": {"status": "ok", "actions": [], "truncated": False}, "guards": []}


class DeltaTests(unittest.TestCase):
    def note_fixture(self):
        from test_adaptive_maintenance import context, payload
        data, value = context(), payload()
        data.update(routing_revision=4)
        data["reference"]["slim_snapshot"] = deepcopy(data["slim"])
        data["news"]["items"] = []
        data["analyst_actions"]["actions"] = []
        value["routine_note"] = "Cambio técnico: RSI pasa de 50 a 51; no cambia la tesis."
        data["reference"]["slim_snapshot"]["technicals"] = {"rsi14": 50}
        data["slim"]["technicals"] = {"rsi14": 51}
        return data, value

    def test_technical_note_supported_without_news(self):
        data, value = self.note_fixture()
        self.assertIn(value["routine_note"], apply_update(value, data))

    def test_timestamp_only_does_not_authorize_technical_note(self):
        data, value = self.note_fixture()
        data["slim"]["technicals"]["rsi14"] = 50
        data["slim"]["as_of"] = "2026-10-03T12:00:00Z"
        with self.assertRaisesRegex(ValueError, "note_without_sources"):
            apply_update(value, data)

    def test_historical_note_only_does_not_authorize_current_note(self):
        data, value = self.note_fixture()
        for section in ("setup", "levels", "news", "analysts"):
            value[section]["evidence"] = ["/reference"]
        with self.assertRaisesRegex(ValueError, "note_without_sources"):
            apply_update(value, data)

    def test_revision3_keeps_original_note_receipt_semantics(self):
        data, value = self.note_fixture()
        data["routing_revision"] = 3
        with self.assertRaisesRegex(ValueError, "note_without_sources"):
            apply_update(value, data)

    def test_saved_MP_high_candidate_replays_without_another_call(self):
        from src.local_runner import run_one
        from src.local_runner.adaptive_context import validation_context
        saved = ROOT / "logs/adaptive_delta_evaluation/20261003T220938915701/MP"
        if not saved.exists():
            self.skipTest("optional saved candidate not available")
        data = model_context(json.loads((saved / "context.json").read_text(encoding="utf-8")))
        value = json.loads((saved / "triage.response").read_text(encoding="utf-8"))
        md = apply_update(value, data)
        validation = run_one.validate_markdown(md, authoritative_context=validation_context(data),
            require_support_strengths=True, require_resistance=True, require_separate_scores=True)
        self.assertTrue(validation.ok, validation.errors)

    def test_capture_refresh_not_market_move_source_immutable(self):
        value = fixture()
        value["slim"].update(as_of="2026-10-03T18:00:00Z", mirror_url="https://example.test/new")
        frozen = deepcopy(value)
        result = deterministic_comparison(value)
        self.assertTrue(result["since_current"]["same_market_values"])
        self.assertEqual(len(result["since_current"]["capture_only_changes"]), 2)
        self.assertTrue(result["same_current_and_sol_markdown"])
        self.assertEqual(value, frozen)

    def test_exact_changes_no_threshold_rounding_or_dropped_expiry(self):
        value = fixture()
        value["slim"]["technicals"]["rsi14"] += .00001
        value["slim"]["options"]["expirations"][0]["dte"] = 5
        value["slim"]["levels"]["put_walls_top"][0]["gamma_share_pct"] = 12.1
        result = deterministic_comparison(value)["since_full_sol"]
        self.assertFalse(result["same_market_values"])
        self.assertEqual(result["changed_groups"], ["levels", "options", "technicals"])
        self.assertEqual(len(result["changes"]), 3)

    def test_missing_and_null_distinguished_json_pointer_escaped(self):
        value = fixture()
        value["slim"]["odd/key~"] = None
        result = deterministic_comparison(value)["since_current"]["changes"][0]
        self.assertEqual(result["current_pointer"], "/slim/odd~1key~0")
        self.assertFalse(result["previous_present"])
        self.assertTrue(result["current_present"])

    def test_news_seen_not_verified_changed_same_id_and_old_newly_supplied(self):
        value = fixture()
        value["news"]["items"] += [
            {**deepcopy(value["news"]["items"][0]), "headline": "Changed guidance"},
            {"articleId": "b", "providerCode": "DJ-N", "published_at": "2026-10-03T07:00:00Z", "headline": "Older omission"},
            {"articleId": "c", "providerCode": "DJ-N", "published_at": "2026-10-03T10:00:00Z", "headline": "New event"},
            {"articleId": "d", "headline": "Undated"}]
        result = deterministic_comparison(value)["news_since_full_sol"]
        self.assertEqual((result["identical_count"], result["changed_same_id_count"], result["newly_supplied_count"]), (1, 1, 3))
        self.assertEqual(result["after_report_count"], 1)
        self.assertEqual(result["observations"][2]["chronology"], "at_or_before_report")
        self.assertEqual(result["observations"][4]["chronology"], "unknown")
        self.assertIn("NOT independently verified", result["meaning"])

    def test_removed_news_is_not_retraction_and_sources_not_hidden(self):
        value = fixture()
        value["news"]["items"] = []
        value["news"]["truncated"] = True
        view = model_context(value)
        result = view["comparison"]["deterministic"]["news_since_full_sol"]
        self.assertEqual(result["previous_supplied_count"], 1)
        self.assertFalse(result["current_source_complete"])
        self.assertIn("NOT retraction", result["meaning"])
        self.assertTrue(view["news"]["truncated"])

    def test_cumulative_changes_survive_unchanged_current(self):
        value = fixture()
        value["sol_reference"]["slim_snapshot"]["latest_price"] = 40
        value["reference"]["analysis_markdown"] += "\nMaintained plan"
        result = deterministic_comparison(value)
        self.assertTrue(result["since_current"]["same_market_values"])
        self.assertFalse(result["since_full_sol"]["same_market_values"])
        self.assertFalse(result["same_current_and_sol_markdown"])

    def test_missing_baseline_never_means_unchanged(self):
        value = fixture()
        value["sol_reference"] = {}
        result = deterministic_comparison(value)
        self.assertIsNone(result["same_current_and_sol_markdown"])
        self.assertIsNone(result["since_full_sol"]["same_market_values"])

    def test_geometry_MP_target_is_still_above_price(self):
        result = deterministic_comparison(fixture())["current_plan_geometry"]
        self.assertEqual(result["target"], 47)
        self.assertTrue(result["target_above_current_price"])

    def test_legacy_context_receipts_keep_original_semantics(self):
        value = fixture()
        for revision in (1, 2, 3):
            value["routing_revision"] = revision
            self.assertNotIn("deterministic", model_context(value)["comparison"])
            self.assertNotIn("/comparison", maintenance_schema(value)["$defs"]["evidence_pointer"]["enum"])

    def test_schema_citation_and_lossless_transport(self):
        value = model_context(fixture())
        self.assertIn("/comparison", maintenance_schema(value)["$defs"]["evidence_pointer"]["enum"])
        self.assertEqual(unpack_model_context(json.loads(serialize_model_input(value))), value)

    def test_live_policy_high_without_model_substitution_or_ITV_change(self):
        policy = load_policy(ROOT)
        self.assertEqual((policy["routing_revision"], policy["triage_model"], policy["triage_effort"]), (17, "gpt-6-luna", "high"))
        self.assertEqual((policy["report_model"], policy["report_effort"]), ("gpt-6.1-sol", "high"))
        self.assertEqual((policy["priority_itv_sessions"], policy["watchlist_itv_sessions"]), (5, 5))

    def test_last_batch_factual_replay_not_predicted_model_verdicts(self):
        base = ROOT / "logs/batch/2026-10-03/18-29-23/adaptive"
        if not base.exists():
            self.skipTest("optional local incident fixtures not available")
        rows = {}
        for folder in base.iterdir():
            context = json.loads((folder / "input.json").read_text(encoding="utf-8"))
            context["routing_revision"] = 4
            rows[folder.name] = model_context(context)["comparison"]["deterministic"]
        self.assertEqual(len(rows), 46)
        for symbol in ("CIFR", "CLS", "KTOS", "LEU", "MU", "RDDT", "TSM"):
            with self.subTest(symbol=symbol):
                self.assertTrue(rows[symbol]["since_full_sol"]["same_market_values"])
        for symbol in ("CRWV", "MRVL", "RDDT", "QCOM", "RKLB", "MU", "MRNA"):
            with self.subTest(symbol=symbol):
                news = rows[symbol]["news_since_full_sol"]
                self.assertEqual(news["identical_count"], news["current_count"])
                self.assertEqual(news["after_report_count"], 0)
        self.assertTrue(rows["NVDA"]["same_current_and_sol_markdown"])
        self.assertTrue(rows["MP"]["current_plan_geometry"]["target_above_current_price"])

    def test_all_saved_revision3_receipt_inputs_stay_byte_identical(self):
        base = ROOT / "logs/batch/2026-10-03/18-29-23/adaptive"
        if not base.exists():
            self.skipTest("optional local incident fixtures not available")
        for folder in base.iterdir():
            with self.subTest(symbol=folder.name):
                context = json.loads((folder / "input.json").read_text(encoding="utf-8"))
                review = json.loads((folder / "review.json").read_text(encoding="utf-8"))
                context.update(guards=review["guards"], itv=review["itv"], review_flags=review["review_flags"])
                view = model_context(context)
                view.pop("research_memory", None)
                receipt = json.loads((folder / "triage.receipt.json").read_text(encoding="utf-8"))
                self.assertEqual(hashlib.sha256(serialize_model_input(view).encode("utf-8")).hexdigest(), receipt["input_sha256"])


if __name__ == "__main__":
    unittest.main()
