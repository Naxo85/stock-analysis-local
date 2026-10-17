"""Offline causal-policy invariants; not predictions of future model decisions."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import unittest

from src.local_runner.adaptive_context import (
    model_context, resolve_evidence, serialize_model_input, unpack_model_context,
)
from src.local_runner.adaptive_delta import plan_source_inventory
from src.local_runner.adaptive_maintenance import maintenance_decision, maintenance_schema
from test_adaptive_maintenance import context, payload

ROOT = Path(__file__).resolve().parents[1]
BATCH = ROOT / "logs/batch/2026-10-05/12-38-33/adaptive"


class CausalReviewTests(unittest.TestCase):
    def data(self):
        data = context()
        data["routing_revision"] = 6
        data["slim"]["levels"] = {
            "supports": [{"level": 81.25, "type": "avwap_event_support"}],
            "put_walls_top": [{"level": 91, "type": "put_wall", "expiration": "2026-10-09"}],
            "resistances": [{"level": 111, "type": "gap_down_upper"}],
        }
        data["reference"]["slim_snapshot"] = {"levels": {
            "supports": [{"level": 81, "type": "put_wall", "expiration": "2026-10-02"}],
        }}
        return data

    def test_exact_current_and_historical_pointers_not_loss_verdict(self):
        data = self.data()
        frozen = deepcopy(data)
        view = model_context(data)
        inventory = view["comparison"]["plan_source_inventory"]
        self.assertEqual(view["comparison"]["contract"], "adaptive-maintenance-context-v6")
        row = inventory["zones"][1]
        self.assertEqual(row["current"][0]["type"], "avwap_event_support")
        self.assertEqual(row["historical"][0]["expiration"], "2026-10-02")
        for zone in inventory["zones"]:
            for state in ("current", "historical"):
                for item in zone[state]:
                    self.assertEqual(resolve_evidence(view, item["pointer"])["level"], item["level"])
        self.assertNotIn("decision", inventory)
        self.assertEqual(data, frozen)
        self.assertEqual(unpack_model_context(json.loads(serialize_model_input(view))), view)

    def test_no_matching_tolerance_rounding_or_option_identity_guess(self):
        data = self.data()
        data["slim"]["levels"]["supports"] += [
            {"level": 82.00000001, "type": "avwap_event_support"},
            {"level": True}, {"level": float("nan")}, {"level": "81"},
        ]
        data["slim"]["levels"]["put_walls_top"] += [
            {"level": 91, "type": "put_wall", "expiration": "2026-10-16"}]
        rows = plan_source_inventory(data)["zones"]
        self.assertEqual(len(rows[1]["current"]), 1)
        self.assertEqual([r["expiration"] for r in rows[0]["current"]], ["2026-10-09", "2026-10-16"])

    def test_duplicate_wall_copies_not_claimed_independent_support(self):
        data = self.data()
        data["slim"]["levels"]["supports"] = deepcopy(data["slim"]["levels"]["put_walls_top"])
        rows = plan_source_inventory(data)["zones"]
        self.assertEqual(len(rows[0]["current"]), 2)
        self.assertTrue(all(r["type"] == "put_wall" for r in rows[0]["current"]))
        self.assertIn("not independent", plan_source_inventory(data)["meaning"])

    def test_untyped_origin_and_absent_optional_zone_not_fabricated(self):
        data = self.data()
        data["slim"]["levels"]["supports"] = [{"level": 81}]
        self.assertIsNone(plan_source_inventory(data)["zones"][1]["current"][0]["type"])
        data["reference"]["analysis_markdown"] = "Entrada ambiciosa: Sin zona verificable"
        row = plan_source_inventory(data)["zones"][1]
        self.assertIsNone(row["range"])
        self.assertEqual(row["current"], [])

    def test_legacy_context_and_shared_schema_unchanged(self):
        data = self.data()
        for revision in range(1, 6):
            data["routing_revision"] = revision
            self.assertNotIn("plan_source_inventory", model_context(data)["comparison"])
        self.assertEqual(maintenance_schema({"routing_revision": 6}),
                         maintenance_schema({"routing_revision": 5}))

    def test_no_risk_demotion_or_new_reason_format_gate(self):
        data = model_context(self.data())
        value = payload()
        value.update(decision="retain", edits=[], evidence_gap="none", reason="Explicación libre.")
        self.assertEqual(maintenance_decision(value, [], data), "retain")
        self.assertEqual(maintenance_decision(value, ["structural_stop_crossed"], data), "escalate")
        for key in value["risk"]:
            candidate = deepcopy(value)
            candidate["risk"][key] = True
            self.assertEqual(maintenance_decision(candidate, [], data), "escalate")
        value["uncertainty"] = True
        self.assertEqual(maintenance_decision(value, [], data), "escalate")
        value.update(uncertainty=False, evidence_gap="research")
        self.assertEqual(maintenance_decision(value, [], data), "escalate")
        value["evidence_gap"] = "essential_data"
        self.assertEqual(maintenance_decision(value, [], data), "blocked")

    def test_real_TSLA_historical_AVWAP_is_not_current_backing(self):
        source = BATCH / "TSLA/input.json"
        if not source.exists():
            self.skipTest("Optional production artifacts unavailable")
        original = source.read_bytes()
        data = json.loads(original)
        data["routing_revision"] = 6  # In-memory fixture, never rewrite a frozen run.
        row = model_context(data)["comparison"]["plan_source_inventory"]["zones"][1]
        self.assertEqual(row["current"], [])
        self.assertIn(351.3628, [r["level"] for r in row["historical"]])
        self.assertEqual(source.read_bytes(), original)

    def test_all_last_batch_views_resolve_and_originals_stay_identical(self):
        if not BATCH.exists():
            self.skipTest("Optional production artifacts unavailable")
        sources = sorted(BATCH.glob("*/input.json"))
        self.assertEqual(len(sources), 46)
        for source in sources:
            original = source.read_bytes()
            data = json.loads(original)
            legacy_view = model_context(data)
            self.assertNotIn("plan_source_inventory", legacy_view["comparison"])
            data["routing_revision"] = 6
            view = model_context(data)
            inventory = view["comparison"]["plan_source_inventory"]
            for zone in inventory["zones"]:
                for state in ("current", "historical"):
                    for row in zone[state]:
                        self.assertEqual(resolve_evidence(view, row["pointer"])["level"], row["level"])
            self.assertEqual(unpack_model_context(json.loads(serialize_model_input(view))), view)
            self.assertEqual(hashlib.sha256(source.read_bytes()).digest(), hashlib.sha256(original).digest())


if __name__ == "__main__":
    unittest.main()
