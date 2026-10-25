"""Offline semantic repair and incident formatting regressions, no model/GCS."""
from contextlib import ExitStack
from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from src.common.analysis_validator import ValidationResult
from src.local_runner import adaptive_stage as stage
from src.local_runner import adaptive_codex as codex
from src.local_runner.adaptive_budget import read_json, write_json
from src.local_runner.adaptive_context import model_context, serialize_model_input
from src.local_runner.adaptive_maintenance import apply_update, _wall_metric_claims, _refresh_wall_facts
from src.local_runner.adaptive_patch_normalization import normalize_factor_qualifier
from src.local_runner.adaptive_repair import repair_context, repairable_update_error

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("repair_stage_fixture", ROOT / "tests/test_adaptive_maintenance_stage.py")
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)


class CosmeticTests(unittest.TestCase):
    def context(self):
        data = base.context()
        data["routing_revision"] = 4
        return data

    def test_exact_noop_ignored_but_real_stop_changes_rejected(self):
        data = self.context()
        value = base.update_payload(data)
        value["edits"].append(base.FIXTURE.edit("Motivo: Bajo soporte operativo.", "Motivo: Bajo soporte operativo."))
        audit = []
        candidate = apply_update(value, data, audit=audit)
        self.assertIn("exact_noop_edit_ignored", [row["method"] for row in audit])
        self.assertIn("Stop de gestión: $85", candidate)
        value["edits"][-1] = base.FIXTURE.edit("Stop de gestión: $85", "Stop de gestión: $86")
        with self.assertRaisesRegex(ValueError, "management_stop_changed"):
            apply_update(value, data)

    def test_only_noops_are_not_a_new_report_and_legacy_stays_strict(self):
        data = self.context()
        value = base.update_payload(data)
        value["edits"] = [base.FIXTURE.edit("Setup: 6 / 10", "Setup: 6 / 10")]
        with self.assertRaisesRegex(ValueError, "empty_patch"):
            apply_update(value, data)
        data["routing_revision"] = 3
        with self.assertRaisesRegex(ValueError, "noop_edit"):
            apply_update(value, data)
        data["routing_revision"] = 4
        value["edits"] = [base.FIXTURE.edit("not present", "not present")]
        with self.assertRaises(ValueError):
            apply_update(value, data)

    def test_exact_existing_note_routes_through_same_note_gate(self):
        data = self.context()
        previous = "Nota técnica histórica, no investigación nueva."
        data["reference"]["analysis_markdown"] += "\n## Actualización diaria (Luna)\n\n" + previous + "\n"
        value = base.update_payload(data)
        value["edits"].append(base.FIXTURE.edit(previous, "Actualización rutinaria respaldada."))
        audit = []
        result = apply_update(value, data, audit=audit)
        self.assertNotIn(previous, result)
        self.assertIn("exact_existing_daily_note_replacement", [item["method"] for item in audit])
        self.assertEqual(result.count("## Actualización diaria (Luna)"), 1)
        value["edits"][-1]["after"] = "## Nueva tesis\nCambio fundamental"
        with self.assertRaisesRegex(ValueError, "note_structure"):
            apply_update(value, data)
        value["edits"][-1] = base.FIXTURE.edit("histórica", "futura")
        with self.assertRaisesRegex(ValueError, "protected_span"):
            apply_update(value, data)

    def test_oi_percent_is_not_contracts_in_both_orders(self):
        for segment in ("OI 11.0% y 9,149 contratos", "11.0% del OI y OI 9,149",
                        "OI: 11,0% y OI 9149", "OI 11 % y 9149 contratos"):
            with self.subTest(segment=segment):
                claims = _wall_metric_claims(segment)
                self.assertEqual([key for key, _ in claims].count("oi"), 1)
                self.assertEqual([key for key, _ in claims].count("oi_share_pct"), 1)
                oi = next(match for key, match in claims if key == "oi")
                self.assertIn(oi.groupdict().get("number") or oi.groupdict().get("contracts"), ("9,149", "9149"))

    def test_only_observed_absence_qualifiers_are_merged(self):
        for label, final in (
            ("Entrada", "sin dominio excepcional demostrado frente a vecinos."),
            ("Resistencia", "rechazos históricos no disponibles y ningún POC/HVN a ≤5% del bloque."),
        ):
            raw = f"Factores de {label}: evidencia uno; evidencia dos; evidencia tres; evidencia cuatro; {final}\n"
            result, audit = normalize_factor_qualifier(raw, {"routing_revision": 4})
            self.assertEqual(result.replace(",", ";", 1), raw)
            self.assertEqual(len(audit), 1)
            self.assertEqual(normalize_factor_qualifier(raw, {"routing_revision": 3}), (raw, []))
        genuine = "Factores de Entrada: POC; puts; volumen; rebotes; quinto HVN confirmado.\n"
        self.assertEqual(normalize_factor_qualifier(genuine, {"routing_revision": 4}), (genuine, []))

    def test_reverse_oi_percentage_still_requires_evidence_and_correct_value(self):
        data = self.context()
        data["slim"]["levels"]["resistances"] = [
            {"type": "call_wall", "level": 190, "expiration": "2026-10-16", "oi": 9149, "oi_share_pct": 11, "gamma_share_pct": 20.6}]
        line = "Factores de Resistencia: call wall $190 del 16-Oct con 20.6% del gamma call, OI 11.0% y 9,149 contratos.\n"
        self.assertEqual(_refresh_wall_facts("", line, data), (line, []))
        with self.assertRaisesRegex(ValueError, "stale_or_unproven_wall_metric") as caught:
            _refresh_wall_facts("", line.replace("OI 11.0%", "OI 12.0%"), data)
        details = caught.exception.maintenance_details
        self.assertEqual(details["field"], "oi_share_pct")
        self.assertEqual(details["claimed"], "12.0")
        self.assertEqual(details["current_value"], 11)
        feedback = repair_context(data, base.update_payload(data), str(caught.exception), validation_details=details)
        self.assertEqual(feedback["maintenance_repair"]["validation_details"], details)
        del data["slim"]["levels"]["resistances"][0]["oi_share_pct"]
        with self.assertRaisesRegex(ValueError, "unproven_current_wall_metric"):
            _refresh_wall_facts("", line, data)

    def quote_case(self):
        data = self.context()
        old = "*Snapshot: 02-10-2026, 08:00 UTC. Mid indicativo; bid $98.00, ask $102.00 y spread 4.000%. No se utilizan precios web.*"
        new = "*Snapshot: 03-10-2026, 10:00 UTC. Mid indicativo; bid $99.00, ask $101.00 y spread 2.000%. No se utilizan precios web.*"
        data["reference"]["analysis_markdown"] = base.FIXTURE.MD.replace("## 0)", old + "\n\n## 0)")
        data["slim"]["market_state"] = {"bid": 99, "ask": 101, "spread_pct": 2}
        value = base.update_payload(data)
        value["edits"].append(base.FIXTURE.edit(old, new))
        return data, value, old, new

    def test_structured_quote_snapshot_uses_current_exact_source(self):
        data, value, _, new = self.quote_case()
        self.assertIn(new, apply_update(value, data))
        for replacement in ("bid $99.00", "ask $101.00", "spread 2.000%", "10:00 UTC"):
            bad = deepcopy(value)
            bad["edits"][-1]["after"] = new.replace(replacement, {
                "bid $99.00": "bid $98.00", "ask $101.00": "ask $102.00",
                "spread 2.000%": "spread 4.000%", "10:00 UTC": "08:00 UTC"}[replacement])
            with self.subTest(replacement=replacement), self.assertRaises(ValueError):
                apply_update(bad, data)

    def test_mid_qualifier_is_allowed_but_position_must_be_correct(self):
        data = self.context()
        value = base.update_payload(data)
        value["edits"].append(base.FIXTURE.edit(
            "Estado actual: por encima de la zona",
            "Estado actual: por encima de la zona según el mid; ejecución no validada"))
        self.assertIn("según el mid", apply_update(value, data))
        quoted_price = data["slim"]["latest_price"]
        value["edits"][-1]["after"] = f"Estado actual: por encima de la zona según el mid de ${quoted_price}; ejecución no validada"
        self.assertIn(f"mid de ${quoted_price}", apply_update(value, data))
        value["edits"][-1]["after"] = f"Estado actual: por encima de la zona según el mid de ${quoted_price + 1}; ejecución no validada"
        with self.assertRaisesRegex(ValueError, "stale_current_state"):
            apply_update(value, data)
        value["edits"][-1]["after"] = "Estado actual: por debajo de la zona según el mid; ejecución no validada"
        with self.assertRaisesRegex(ValueError, "stale_current_state"):
            apply_update(value, data)
        data, value, _, new = self.quote_case()
        for replacement in ("Snapshot: precio seguro", new + "\nSnapshot: duplicado", "", new.replace("Mid indicativo", "Ejecutable")):
            bad = deepcopy(value)
            bad["edits"][-1]["after"] = replacement or "Snapshot eliminado"
            with self.subTest(replacement=replacement), self.assertRaises(ValueError):
                apply_update(bad, data)


class LunaRepairTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.work = self.root / "adaptive/CAT"
        self.work.mkdir(parents=True)
        self.data = base.context()
        self.data["routing_revision"] = 4
        self.policy = {**base.POLICY, "routing_revision": 4, "luna_repair_version": 1}
        write_json(self.work / "input.json", self.data)
        write_json(self.work / "policy.json", self.policy)
        self.good = base.update_payload(self.data)
        self.bad = deepcopy(self.good)
        self.bad["edits"].append(base.FIXTURE.edit("wrong bold spelling", "corrected text"))

    def run_case(self, repaired=None, *, initial=None, repair_exception=None, guards=None, due=False,
                 validation_results=None):
        initial = self.bad if initial is None else initial
        repaired = self.good if repaired is None else repaired
        self.seen = []
        def call(root, work, symbol, budget, policy, kind, data, **kwargs):
            self.seen.append((kind, deepcopy(data)))
            if kind == "triage_repair" and repair_exception:
                raise repair_exception
            response = initial if kind == "triage" else repaired
            text = base.FIXTURE.MD.replace("02-10-2026", "03-10-2026") if kind == "report" else json.dumps(response)
            (work / (kind + ".response")).write_text(text, encoding="utf-8")
            return {"text": text, "exit_code": 0, "completed_at": base.COMPLETED.isoformat(),
                    "model": policy["report_model" if kind == "report" else "triage_model"],
                    "reasoning_effort": "high", "usage": {"input_tokens": 100, "output_tokens": 20}}
        with ExitStack() as stack:
            stack.enter_context(patch.object(stage, "datetime", base.FrozenClock))
            stack.enter_context(patch.object(stage, "maintenance_precheck", return_value={"guards": guards or [], "review_flags": []}))
            stack.enter_context(patch.object(stage, "itv_state", return_value={"due": due, "age_sessions": 1}))
            stack.enter_context(patch.object(stage, "model_call", side_effect=call))
            stack.enter_context(patch.object(stage.one, "validate_markdown",
                side_effect=validation_results,
                return_value=ValidationResult(ok=True, status="ok", errors=())))
            stack.enter_context(patch.object(stage, "reserve", side_effect=AssertionError("NO REAL RESERVATION")))
            stack.enter_context(patch.object(stage, "call_codex", side_effect=AssertionError("NO REAL MODEL")))
            return stage.analyze(self.root, self.work, "CAT", self.root / "budget.json", False)

    def test_corrective_luna_keeps_original_input_and_sol_age_and_receipts(self):
        original = (self.work / "input.json").read_bytes()
        result = self.run_case()
        self.assertEqual(result["status"], "updated")
        self.assertEqual([k for k, _ in self.seen], ["triage", "triage_repair"])
        feedback = self.seen[1][1]["maintenance_repair"]
        self.assertEqual(feedback["previous_response"], self.bad)
        self.assertEqual(feedback["rejection"], "invalid_update_ambiguous_or_missing_match")
        self.assertEqual(self.seen[1][1]["reference"], self.seen[0][1]["reference"])
        self.assertEqual(result["last_full_report_at"], self.data["sol_reference"]["generated_at"])
        self.assertEqual(len(result["receipts"]), 2)
        self.assertEqual(read_json(self.work / "triage.json"), self.bad)
        self.assertEqual(read_json(self.work / "triage_repair.json"), self.good)
        self.assertEqual((self.work / "input.json").read_bytes(), original)
        with patch.object(stage, "model_call", side_effect=AssertionError("NO REPEAT")):
            self.assertEqual(stage.analyze(self.root, self.work, "CAT", self.root / "budget.json", False), result)

    def test_only_one_correction_then_sol_for_repeated_match_error(self):
        result = self.run_case(self.bad)
        self.assertEqual(result["status"], "regenerated")
        self.assertEqual([k for k, _ in self.seen], ["triage", "triage_repair", "report"])
        self.assertEqual(len(result["luna_repair"]["rejections"]), 2)
        self.assertEqual(self.seen[-1][1]["maintenance_escalation"], "invalid_update_ambiguous_or_missing_match")

    def test_full_validator_rejection_is_sent_verbatim_and_validated_again(self):
        valid = ValidationResult(ok=True, status="ok", errors=())
        invalid = ValidationResult(ok=False, status="failed", errors=("wrong strength sum",))
        result = self.run_case(initial=self.good, validation_results=[invalid, valid, valid])
        self.assertEqual(result["status"], "updated")
        self.assertEqual([k for k, _ in self.seen], ["triage", "triage_repair"])
        self.assertIn("wrong strength sum", self.seen[1][1]["maintenance_repair"]["rejection"])
        self.assertFalse(read_json(self.work / "update_validation_initial.json")["ok"])
        self.assertTrue(read_json(self.work / "update_validation.json")["ok"])

    def non_update(self, decision):
        return {**deepcopy(self.good), "decision": decision, "edits": [], "routine_note": ""}

    def test_repair_can_retain_or_escalate_but_blocked_stays_visible(self):
        result = self.run_case(self.non_update("retain"))
        self.assertEqual(result["status"], "retained")
        self.assertEqual([k for k, _ in self.seen], ["triage", "triage_repair"])
        # Fresh isolated work for each behavior, never overwrite a production result.
        for name in ("review.json", "validated_result.json"):
            (self.work / name).unlink(missing_ok=True)
        result = self.run_case(self.non_update("escalate"))
        self.assertEqual(result["status"], "regenerated")
        self.assertEqual([k for k, _ in self.seen], ["triage", "triage_repair", "report"])
        for name in ("review.json", "validated_result.json"):
            (self.work / name).unlink(missing_ok=True)
        with self.assertRaisesRegex(RuntimeError, "triage_repair_blocked"):
            self.run_case(self.non_update("blocked"))
        self.assertEqual([k for k, _ in self.seen], ["triage", "triage_repair"])

    def test_wrong_hash_timeout_and_missing_evidence_do_not_trigger_sol(self):
        initial = deepcopy(self.bad)
        initial["base_markdown_sha256"] = "wrong"
        with self.assertRaisesRegex(ValueError, "base_hash"):
            self.run_case(initial=initial)
        self.assertEqual([k for k, _ in self.seen], ["triage"])
        with self.assertRaisesRegex(RuntimeError, "ambiguous timeout"):
            self.run_case(repair_exception=RuntimeError("ambiguous timeout"))
        self.assertEqual([k for k, _ in self.seen], ["triage", "triage_repair"])
        with self.assertRaisesRegex(RuntimeError, "triage_blocked"):
            self.run_case(initial=self.non_update("blocked"))
        self.assertEqual([k for k, _ in self.seen], ["triage"])

    def test_itv_or_guards_do_not_pay_for_luna_repair(self):
        result = self.run_case(due=True)
        self.assertEqual(result["status"], "regenerated")
        self.assertEqual([k for k, _ in self.seen], ["report"])

    def test_feedback_is_deepcopy_and_integrity_not_repairable(self):
        context = deepcopy(self.data)
        response = deepcopy(self.bad)
        repair_context(context, response, "invalid_update_ambiguous_or_missing_match")
        self.assertEqual(context, self.data)
        self.assertEqual(response, self.bad)
        for reason in ("invalid_update_base_hash", "invalid_update_missing_base",
                       "update_not_allowed_uncertain_or_critical", "triage_blocked_insufficient_evidence"):
            self.assertFalse(repairable_update_error(reason))


class RepairTransportTests(unittest.TestCase):
    def test_repair_uses_same_clean_luna_session_contract_not_new_prefix(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            observed = []
            real_key = codex.contract_key
            def capture(**kwargs):
                result = real_key(**kwargs)
                observed.append((kwargs, result))
                return result
            with patch.object(codex, "require_codex", return_value="codex"), \
                 patch.object(codex, "contract_key", side_effect=capture), \
                 patch.object(codex, "_capacity_admission", side_effect=RuntimeError("offline_probe")), \
                 patch.object(codex, "run_bounded", side_effect=AssertionError("NO CLI OR MODEL")):
                for kind in ("triage", "triage_repair"):
                    with self.assertRaisesRegex(RuntimeError, "offline_probe"):
                        codex.call_codex(workspace=root / "workspace", artifacts=root / kind,
                            kind=kind, instructions="identical prefix", data={"ticker": "CAT"},
                            model="gpt-6-luna", effort="high", timeout=240, schema={"type": "object"})
            self.assertEqual(observed[0][1], observed[1][1])
            self.assertEqual(observed[1][0]["kind"], "triage")
            self.assertTrue((root / "triage_repair/triage_repair.input.json").exists())

    def test_separate_receipt_same_luna_contract_no_cache_or_second_reservation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            work = root / "adaptive/CAT"
            work.mkdir(parents=True)
            (work / "triage_instructions.md").write_text("Stable Luna instructions", encoding="utf-8")
            policy = {**base.POLICY, "routing_revision": 4, "luna_repair_version": 1}
            data = repair_context({**base.context(), "routing_revision": 4}, base.FIXTURE.payload(), "invalid_update_noop_edit")
            def fake_codex(**kwargs):
                projected = model_context(data)
                projected.pop("research_memory", None)
                receipt = {"exit_code": 0, "usage": {"input_tokens": 100, "output_tokens": 20},
                    "model": policy["triage_model"], "reasoning_effort": policy["triage_effort"],
                    "research_enabled": False,
                    "input_sha256": hashlib.sha256(serialize_model_input(projected).encode()).hexdigest(),
                    "response_sha256": hashlib.sha256(b"{}").hexdigest(),
                    "instructions_sha256": hashlib.sha256(kwargs["instructions"].encode()).hexdigest(),
                    "schema_sha256": hashlib.sha256(json.dumps(kwargs["schema"], sort_keys=True).encode()).hexdigest()}
                (work / "triage_repair.response").write_text("{}", encoding="utf-8")
                write_json(work / "triage_repair.receipt.json", receipt)
                return {**receipt, "text": "{}"}
            with patch.object(stage, "reserve", return_value="CAT:triage_repair") as reserve, \
                 patch.object(stage, "finish") as finish, \
                 patch.object(stage, "call_codex", side_effect=fake_codex) as call, \
                 patch.object(stage, "load_triage", side_effect=AssertionError("NO REPAIR CACHE")), \
                 patch.object(stage, "save_triage", side_effect=AssertionError("NO REPAIR CACHE")):
                first = stage.model_call(root, work, "CAT", root / "budget.json", policy, "triage_repair", data)
                self.assertEqual(first, stage.model_call(root, work, "CAT", root / "budget.json", policy, "triage_repair", data))
                self.assertEqual(call.call_count, 1)
                self.assertEqual(reserve.call_count, 1)
                self.assertEqual(reserve.call_args.kwargs["kind"], "triage_repair")
                self.assertEqual(call.call_args.kwargs["model"], policy["triage_model"])
                self.assertFalse(call.call_args.kwargs["research"])
                changed = deepcopy(data)
                changed["maintenance_repair"]["rejection"] = "different reason"
                with self.assertRaisesRegex(RuntimeError, "context_mismatch"):
                    stage.model_call(root, work, "CAT", root / "budget.json", policy, "triage_repair", changed)


if __name__ == "__main__":
    unittest.main()
