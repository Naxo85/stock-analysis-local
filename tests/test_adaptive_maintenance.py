from __future__ import annotations

from copy import deepcopy
import hashlib
import unittest

from src.local_runner.adaptive_maintenance import (
    RISK_FIELDS, apply_update, maintenance_decision, maintenance_schema,
)
from src.local_runner.adaptive_policy import SECTIONS

MD = """# CAT

Fecha del análisis: 02-10-2026
Precio de referencia: $100

## 0) Resumen ejecutivo
Tesis: 8 / 10
Motivo de Tesis: Negocio estable.
Setup: 6 / 10
Motivo de Setup: Soporte con defensa.
Narrativa actual: Crecimiento con riesgos conocidos.

## 1) Narrativa y catalizadores activos
02-10-2026 · Resultados confirmados · (+5)
Guidance mantenido.

## 2) Próximo evento clave
29-10-2026 · Resultados Q3
Importan ingresos y márgenes.

## 3) Plan
Entrada: $90-92 (-10,00% a -8,00% vs precio actual)
Estado actual: por encima de la zona
Motivo: Se conserva el soporte.
Entrada ambiciosa: $80-82 (-20,00% a -18,00% vs precio actual)
Motivo: Se conserva el suelo.
Stop de gestión: $85 (-15,00% vs precio actual)
Motivo: Bajo soporte operativo.
Stop estructural: $70 (-30,00% vs precio actual)
Motivo: Invalida la estructura profunda.
Resistencia estructural: $110-112 (+10,00% a +12,00% vs precio actual)
Motivo: Techo técnico.
Salida / objetivo principal: $110 (+10,00% vs precio actual)
Motivo: Primera barrera.

## 4) Conclusión sencilla
Esperar soporte; tesis estable.
"""


def context():
    ref = {"analysis_markdown": MD, "analysis_status": "ok", "generated_at": "2026-10-02T10:00:00Z"}
    return {"reference": ref, "sol_reference": deepcopy(ref), "prepared_at": "2026-10-03T10:00:00Z",
            "slim": {"latest_price": 100, "levels": {"supports": [{"level": 90}]}},
            "news": {"items": [{"headline": "Actualización rutinaria", "url": "https://example.test/news"}]},
            "analyst_actions": {"actions": [{"rating": "maintain"}]}, "guards": []}


def payload():
    return {"decision": "update", "uncertainty": False, "reason": "Mantenimiento técnico respaldado.",
            **{key: {"assessment": "Comparado contra Sol.", "evidence": ["/slim", "/sol_reference"]} for key in SECTIONS},
            "base_markdown_sha256": hashlib.sha256(MD.encode()).hexdigest(),
            "edits": [{"before": "Fecha del análisis: 02-10-2026", "after": "Fecha del análisis: 03-10-2026",
                       "reason": "Fecha de la revisión.", "evidence": ["/slim"]}],
            "risk": {key: False for key in RISK_FIELDS}, "routine_note": ""}


def edit(before, after, evidence=None):
    return {"before": before, "after": after, "reason": "Datos actuales justifican el cambio.",
            "evidence": evidence or ["/slim", "/reference"]}


class MaintenanceTests(unittest.TestCase):
    def test_schema_is_invariant_and_requires_exact_patch_contract(self):
        first = maintenance_schema(context())
        self.assertEqual(first, maintenance_schema({}))
        self.assertIn("update", first["properties"]["decision"]["enum"])
        self.assertIn("edits", first["required"])
        self.assertIn("/sol_reference", first["$defs"]["evidence_pointer"]["enum"])

    def test_updates_date_and_setup_without_touching_fundamentals(self):
        value = payload()
        value["edits"].append(edit("Setup: 6 / 10", "Setup: 6,5 / 10"))
        result = apply_update(value, context())
        self.assertIn("Setup: 6,5 / 10", result)
        self.assertIn("Tesis: 8 / 10", result)
        self.assertIn("Guidance mantenido.", result)

    def test_distinct_supported_entries_resistance_and_target_are_not_hardbanned(self):
        value = payload()
        value["edits"].extend([
            edit("Entrada: $90-92 (-10,00% a -8,00% vs precio actual)", "Entrada: $91-93 (-9,00% a -7,00% vs precio actual)"),
            edit("Resistencia estructural: $110-112 (+10,00% a +12,00% vs precio actual)",
                 "Resistencia estructural: $115-117 (+15,00% a +17,00% vs precio actual)"),
            edit("Salida / objetivo principal: $110 (+10,00% vs precio actual)", "Salida / objetivo principal: $115 (+15,00% vs precio actual)"),
        ])
        data = context()
        data["slim"]["levels"]["supports"].append({"level": 92})
        data["slim"]["levels"]["resistances"] = [{"level": 115}]
        result = apply_update(value, data)
        self.assertIn("Entrada: $91-93", result)
        self.assertIn("Salida / objetivo principal: $115", result)

    def test_protected_thesis_reason_narrative_catalyst_event_and_headers(self):
        cases = [("Tesis: 8 / 10", "Tesis: 7 / 10"),
                 ("Negocio estable.", "Negocio roto."),
                 ("Narrativa actual: Crecimiento con riesgos conocidos.", "Narrativa actual: Contracción."),
                 ("Guidance mantenido.", "Guidance reducido."),
                 ("29-10-2026 · Resultados Q3", "30-10-2026 · Resultados Q3"),
                 ("## 3) Plan", "## 3) Plan nuevo"), ("# CAT", "# AMD")]
        for before, after in cases:
            with self.subTest(before=before):
                value = payload()
                value["edits"].append(edit(before, after))
                with self.assertRaisesRegex(ValueError, "update_not_allowed_protected"):
                    apply_update(value, context())

    def test_cannot_insert_hidden_thesis_or_catalyst_fields_into_allowed_plan(self):
        for extra in ("\nTesis: 2 / 10", "\n## 1) Nuevos catalizadores", "\nNarrativa actual: Tesis rota."):
            with self.subTest(extra=extra):
                value = payload()
                value["edits"].append(edit("Motivo: Primera barrera.", "Motivo: Primera barrera." + extra))
                # New duplicate summary fields can alter semantic parser or
                # section layout; either authority gate must reject them.
                with self.assertRaises(ValueError):
                    apply_update(value, context())

    def test_rendering_wrappers_cannot_hide_protected_content(self):
        for wrapper in ("\n```", "\n~~~", "<style>body{display:none}</style>", "<details>", "<!--"):
            value = payload()
            value["edits"].append(edit("Motivo de Setup: Soporte con defensa.",
                                       "Motivo de Setup: Soporte con defensa." + wrapper))
            with self.subTest(wrapper=wrapper), self.assertRaisesRegex(ValueError, "rendering_wrapper"):
                apply_update(value, context())

    def test_risk_or_uncertainty_escalates_before_editing(self):
        for key in (*RISK_FIELDS, "uncertainty"):
            value = payload()
            if key == "uncertainty":
                value[key] = True
            else:
                value["risk"][key] = True
            self.assertEqual(maintenance_decision(value, [], context()), "escalate")
            with self.assertRaisesRegex(ValueError, "update_not_allowed_uncertain_or_critical"):
                apply_update(value, context())

    def test_guards_override_retain_or_update_but_blocked_stays_blocked(self):
        value = payload()
        self.assertEqual(maintenance_decision(value, ["breach"], context()), "escalate")
        value.update(decision="blocked", edits=[])
        self.assertEqual(maintenance_decision(value, ["breach"], context()), "blocked")

    def test_wrong_base_hash_fails_without_semantic_escalation(self):
        value = payload()
        value["base_markdown_sha256"] = "wrong"
        with self.assertRaisesRegex(ValueError, "invalid_update_base_hash"):
            apply_update(value, context())

    def test_empty_noop_missing_ambiguous_and_overlapping_edits_are_malformed(self):
        cases = [[], [edit("no match", "replacement")], [edit("Motivo:", "Reason:")],
                 [edit("Setup: 6 / 10", "Setup: 6 / 10")],
                 [edit("Setup: 6 / 10", "Setup: 7 / 10"), edit("6 / 10", "7 / 10")]]
        for changes in cases:
            with self.subTest(changes=changes):
                value = payload()
                value["edits"] = changes
                with self.assertRaisesRegex(ValueError, "invalid_update_"):
                    apply_update(value, context())

    def test_edits_are_simultaneous_not_cascaded(self):
        value = payload()
        value["edits"].extend([edit("Setup: 6 / 10", "Setup: 6,5 / 10"),
                               edit("Motivo de Setup: Soporte con defensa.", "Motivo de Setup: Setup: 6 / 10 era el anterior.")])
        result = apply_update(value, context())
        self.assertIn("Motivo de Setup: Setup: 6 / 10 era el anterior.", result)
        self.assertIn("\nSetup: 6,5 / 10", result)

    def test_mandatory_resolved_evidence_and_restricted_edit_roots(self):
        for pointers in ([], ["/guards"], ["/prepared_at"], ["/slim/missing"], ["/news/items/99"]):
            value = payload()
            value["edits"][0]["evidence"] = pointers
            with self.subTest(pointers=pointers), self.assertRaises(ValueError):
                apply_update(value, context())

    def test_unsupported_urls_are_policy_denied_known_urls_allowed(self):
        value = payload()
        value["edits"].append(edit("Esperar soporte; tesis estable.", "Ver [dato](https://evil.test/invented)."))
        with self.assertRaisesRegex(ValueError, "unsupported_url"):
            apply_update(value, context())
        value["edits"][-1] = edit("Esperar soporte; tesis estable.", "Ver [dato](https://example.test/news).", ["/news"])
        self.assertIn("https://example.test/news", apply_update(value, context()))

    def test_structural_stop_value_and_rationale_cannot_change(self):
        for before, after in (("Stop estructural: $70 (-30,00% vs precio actual)", "Stop estructural: $69 (-31,00% vs precio actual)"),
                              ("Motivo: Invalida la estructura profunda.", "Motivo: Nuevo soporte profundo.")):
            value = payload()
            value["edits"].append(edit(before, after))
            with self.subTest(before=before), self.assertRaisesRegex(ValueError, "structural_stop"):
                apply_update(value, context())

    def test_management_stop_cannot_be_lowered_or_moved_to_hide_a_breach(self):
        value = payload()
        value["edits"].append(edit("Stop de gestión: $85 (-15,00% vs precio actual)", "Stop de gestión: $80 (-20,00% vs precio actual)"))
        with self.assertRaisesRegex(ValueError, "management_stop_changed"):
            apply_update(value, context())

    def test_changed_price_requires_all_current_percentages(self):
        value, data = payload(), context()
        data["slim"]["latest_price"] = 110
        value["edits"].append(edit("Precio de referencia: $100", "Precio de referencia: $110"))
        with self.assertRaisesRegex(ValueError, "stale_level_percentages"):
            apply_update(value, data)
        replacements = {
            "-10,00% a -8,00%": "-18,18% a -16,36%", "-20,00% a -18,00%": "-27,27% a -25,45%",
            "-15,00%": "-22,73%", "-30,00%": "-36,36%", "+10,00% a +12,00%": "+0,00% a +1,82%",
        }
        for old, new in replacements.items():
            value["edits"].append(edit(old, new))
        value["edits"].append(edit("Salida / objetivo principal: $110 (+10,00% vs precio actual)",
                                   "Salida / objetivo principal: $110 (+0,00% vs precio actual)"))
        self.assertIn("Stop estructural: $70 (-36,36%", apply_update(value, data))

    def test_stale_or_missing_date_price_and_percentages_denied(self):
        variants = [("Fecha del análisis: 03-10-2026", "Fecha del análisis: 02-10-2026", "stale_report_date"),
                    ("Precio de referencia: $100", "Precio de referencia: $101", "stale_reference_price"),
                    ("Entrada: $90-92 (-10,00% a -8,00% vs precio actual)", "Entrada: $90-92", "missing_level_percentages")]
        for before, after, error in variants:
            value = payload()
            if "Fecha" in before:
                value["edits"] = [edit("Setup: 6 / 10", "Setup: 6,5 / 10")]
            else:
                value["edits"].append(edit(before, after))
            with self.subTest(error=error), self.assertRaisesRegex(ValueError, error):
                apply_update(value, context())

    def test_reference_price_three_decimal_locale_is_resolved_against_source(self):
        from src.local_runner.adaptive_maintenance import _candidate_market_gate
        for raw in ("100.000", "100,000"):
            with self.subTest(raw=raw):
                data = context()
                candidate = MD.replace("02-10-2026", "03-10-2026", 1).replace("Precio de referencia: $100", "Precio de referencia: $" + raw)
                _candidate_market_gate(candidate, data)
        candidate = MD.replace("02-10-2026", "03-10-2026", 1).replace("Precio de referencia: $100", "Precio de referencia: $100,001")
        with self.assertRaisesRegex(ValueError, "stale_reference_price"):
            _candidate_market_gate(candidate, context())

    def test_typographic_minus_in_current_percentages_is_not_positive(self):
        from src.local_runner.adaptive_maintenance import _candidate_market_gate
        candidate = MD.replace("02-10-2026", "03-10-2026", 1)
        for old in ("-10,00%", "-8,00%", "-20,00%", "-18,00%", "-15,00%", "-30,00%"):
            candidate = candidate.replace(old, old.replace("-", "−"))
        _candidate_market_gate(candidate, context())

    def test_long_only_target_and_structural_stop_must_fit_new_entries(self):
        for before, after, error in (
            ("Salida / objetivo principal: $110 (+10,00% vs precio actual)", "Salida / objetivo principal: $90 (-10,00% vs precio actual)", "long_only_target"),
            ("Entrada ambiciosa: $80-82 (-20,00% a -18,00% vs precio actual)", "Entrada ambiciosa: $65-67 (-35,00% a -33,00% vs precio actual)", "structural_stop_not_below_entries")):
            value = payload()
            value["edits"].append(edit(before, after))
            with self.subTest(error=error), self.assertRaisesRegex(ValueError, error):
                apply_update(value, context())

    def test_ambitious_must_be_distinct_lower_and_resistance_a_current_roof(self):
        cases = [("Entrada ambiciosa: $80-82 (-20,00% a -18,00% vs precio actual)",
                  "Entrada ambiciosa: $88-90 (-12,00% a -10,00% vs precio actual)", "ambitious_not_distinct"),
                 ("Resistencia estructural: $110-112 (+10,00% a +12,00% vs precio actual)",
                  "Resistencia estructural: $95-97 (-5,00% a -3,00% vs precio actual)", "resistance_not_current_roof")]
        for before, after, error in cases:
            value = payload()
            value["edits"].append(edit(before, after))
            with self.subTest(error=error), self.assertRaisesRegex(ValueError, error):
                apply_update(value, context())

    def test_estado_actual_must_match_price_and_entry_including_boundaries(self):
        value = payload()
        value["edits"].append(edit("Estado actual: por encima de la zona", "Estado actual: dentro de la zona"))
        with self.assertRaisesRegex(ValueError, "stale_current_state"):
            apply_update(value, context())
        value["edits"].append(edit("Entrada: $90-92 (-10,00% a -8,00% vs precio actual)",
                                   "Entrada: $100-102 (+0,00% a +2,00% vs precio actual)"))
        data = context()
        data["slim"]["levels"]["supports"].append({"level": 100})
        self.assertIn("Estado actual: dentro de la zona", apply_update(value, data))

    def test_correct_estado_may_include_noncontradictory_distance_explanation(self):
        value = payload()
        value["edits"].append(edit("Estado actual: por encima de la zona",
                                   "Estado actual: por encima de la zona, por $8 respecto al límite superior."))
        self.assertIn("por $8", apply_update(value, context()))
        value["edits"][-1]["after"] = "Estado actual: por encima de la zona, dentro de la zona principal."
        with self.assertRaisesRegex(ValueError, "stale_current_state"):
            apply_update(value, context())

    def test_changed_zones_require_current_not_expired_or_historical_origins(self):
        changes = [edit("Entrada: $90-92 (-10,00% a -8,00% vs precio actual)",
                        "Entrada: $91-93 (-9,00% a -7,00% vs precio actual)"),
                   edit("Salida / objetivo principal: $110 (+10,00% vs precio actual)",
                        "Salida / objetivo principal: $115 (+15,00% vs precio actual)")]
        for change in changes:
            value, data = payload(), context()
            value["edits"].append(change)
            with self.subTest(change=change), self.assertRaisesRegex(ValueError, "unproven_current_"):
                apply_update(value, data)
        for expiration, oi in (("2026-10-02", 50), (None, 50), ("2026-10-09", 0)):
            value, data = payload(), context()
            value["edits"].append(changes[0])
            data["slim"]["levels"]["put_walls_top"] = [{"type": "put_wall", "level": 92,
                "expiration": expiration, "oi": oi}]
            with self.subTest(expiration=expiration, oi=oi), self.assertRaisesRegex(ValueError, "unproven_current_entry"):
                apply_update(value, data)
        data["slim"]["levels"]["put_walls_top"][0].update(expiration="2026-10-09", oi=50)
        self.assertIn("Entrada: $91-93", apply_update(value, data))

    def test_noncanonical_new_headings_or_missing_labels_cannot_hide_edits(self):
        value = payload()
        value["edits"].append(edit("Motivo: Primera barrera.", "### Nuevos fundamentales\nMotivo: Primera barrera."))
        with self.assertRaisesRegex(ValueError, "protected_content_changed"):
            apply_update(value, context())
        value["edits"][-1] = edit("Estado actual: por encima de la zona", "Posición actual: por encima de la zona")
        with self.assertRaisesRegex(ValueError, "missing_report_field"):
            apply_update(value, context())

    def test_visible_snapshot_banner_cannot_keep_previous_timestamp(self):
        data, value = context(), payload()
        old = "Snapshot técnico congelado: 02-10-2026, 09:00:00 UTC.\n"
        updated = MD.replace("## 0)", old + "\n## 0)")
        data["reference"]["analysis_markdown"] = updated
        data["slim"]["as_of"] = "2026-10-03T09:00:00Z"
        value["base_markdown_sha256"] = hashlib.sha256(updated.encode()).hexdigest()
        with self.assertRaisesRegex(ValueError, "stale_snapshot_banner"):
            apply_update(value, data)
        value["edits"].append(edit(old, old.replace("02-10-2026", "03-10-2026")))
        self.assertIn("Snapshot técnico congelado: 03-10-2026", apply_update(value, data))

    def test_plain_snapshot_label_is_editable_and_must_be_refreshed(self):
        data, value = context(), payload()
        old = "Snapshot técnico: **02-10-2026, 09:00 UTC**\n"
        updated = MD.replace("## 0)", old + "\n## 0)")
        data["reference"]["analysis_markdown"] = updated
        data["slim"]["as_of"] = "2026-10-03T09:01:19Z"
        value["base_markdown_sha256"] = hashlib.sha256(updated.encode()).hexdigest()
        with self.assertRaisesRegex(ValueError, "stale_snapshot_banner"):
            apply_update(value, data)
        value["edits"].append(edit(old, old.replace("02-10-2026, 09:00", "03-10-2026, 09:01")))
        self.assertIn("Snapshot técnico: **03-10-2026, 09:01", apply_update(value, data))

    def test_inline_snapshot_after_reference_price_is_not_another_price(self):
        from src.local_runner.adaptive_maintenance import _candidate_market_gate
        data = context()
        line = "Precio de referencia: $100 · snapshot técnico del 03-10-2026, 09:00 UTC"
        old = MD.replace("Precio de referencia: $100", line)
        data["reference"]["analysis_markdown"] = old
        data["slim"]["as_of"] = "2026-10-03T09:00:19Z"
        candidate = old.replace("Fecha del análisis: 02-10-2026", "Fecha del análisis: 03-10-2026")
        _candidate_market_gate(candidate, data)
        data["slim"]["as_of"] = "2026-10-03T10:00:19Z"
        with self.assertRaisesRegex(ValueError, "stale_snapshot_banner"):
            _candidate_market_gate(candidate, data)

    def test_routine_note_is_labelled_replaceable_and_cannot_mutate_catalysts(self):
        data, value = context(), payload()
        value["news"]["evidence"] = ["/news"]
        value["analysts"]["evidence"] = ["/analyst_actions"]
        value["routine_note"] = "03-10-2026 · [Actualización rutinaria](https://example.test/news); sin cambio de tesis."
        first = apply_update(value, data)
        self.assertIn("## Actualización diaria (Luna)", first)
        self.assertIn("Guidance mantenido.", first)
        data["reference"]["analysis_markdown"] = first
        value["base_markdown_sha256"] = hashlib.sha256(first.encode()).hexdigest()
        value["edits"] = []
        value["routine_note"] = "03-10-2026 · Seguimiento rutinario actualizado."
        second = apply_update(value, data)
        self.assertEqual(second.count("## Actualización diaria (Luna)"), 1)
        self.assertNotIn("https://example.test/news", second)

    def test_empty_routine_sources_or_injected_headings_denied(self):
        for note, roots, error in (("## 1) Nuevo catalizador", ["/news"], "note_structure"),
                                   ("Cambio rutinario", ["/news/items"], "note_without_sources")):
            value, data = payload(), context()
            value["routine_note"] = note
            value["news"]["evidence"] = roots
            value["analysts"]["evidence"] = ["/analyst_actions/actions"]
            if "without_sources" in error:
                data["news"]["items"] = []
                data["analyst_actions"]["actions"] = []
            with self.subTest(error=error), self.assertRaisesRegex(ValueError, error):
                apply_update(value, data)

    def test_extra_fields_wrong_risk_types_and_nonupdate_patches_are_malformed(self):
        values = [payload(), payload(), payload()]
        values[0]["extra"] = 1
        values[1]["risk"]["critical_catalyst"] = "false"
        values[2]["decision"] = "retain"
        for value in values:
            with self.assertRaisesRegex(ValueError, "invalid_maintenance_"):
                maintenance_decision(value, [], context())

    def test_routine_note_cannot_cite_only_slim_or_empty_metadata_objects(self):
        value, data = payload(), context()
        value["routine_note"] = "03-10-2026 · Se mantiene la recomendación del analista."
        with self.assertRaisesRegex(ValueError, "note_without_sources"):
            apply_update(value, data)
        value["news"]["evidence"] = ["/news"]
        value["analysts"]["evidence"] = ["/analyst_actions"]
        data["news"]["items"] = []
        data["analyst_actions"]["actions"] = []
        with self.assertRaisesRegex(ValueError, "note_without_sources"):
            apply_update(value, data)

    def test_update_hash_is_current_report_not_original_sol_anchor(self):
        data, value = context(), payload()
        current = MD.replace("Setup: 6 / 10", "Setup: 6,5 / 10")
        data["reference"]["analysis_markdown"] = current
        with self.assertRaisesRegex(ValueError, "invalid_update_base_hash"):
            apply_update(value, data)
        value["base_markdown_sha256"] = hashlib.sha256(current.encode()).hexdigest()
        self.assertIn("Setup: 6,5 / 10", apply_update(value, data))

    def test_exact_inherited_motive_rebased_with_dated_raw_rationale(self):
        data, value = context(), payload()
        old = "Motivo: Se reprioriza: anterior **$80-82** sigue vigente; ratio **2*3** y fuerza 73 frente a 70."
        baseline = MD.replace("Motivo: Se conserva el soporte.", old)
        data["reference"]["analysis_markdown"] = baseline
        value["base_markdown_sha256"] = hashlib.sha256(baseline.encode()).hexdigest()
        audit = []
        candidate = apply_update(value, data, audit=audit)
        self.assertIn("Motivo: Se conserva: $90-92. Justificación histórica", candidate)
        self.assertIn("2026-10-02, no una nueva decisión de hoy", candidate)
        self.assertIn("anterior **$80-82** sigue vigente; ratio **2*3** y fuerza 73 frente a 70.", candidate)
        self.assertEqual(audit[0]["method"], "exact_inherited_motive_rebase")
        from src.common.analysis_validator import _validate_previous_level_references
        self.assertNotIn("reprioritized_overlapping_level", " ".join(_validate_previous_level_references(candidate, "entrada_anterior: $90-92")))

    def test_changed_motive_or_range_never_gets_historical_continuity_exemption(self):
        from src.local_runner.adaptive_maintenance import _rebase_inherited_motives
        from src.common.analysis_validator import _validate_previous_level_references
        data = context()
        old = "Motivo: Se reprioriza: anterior $80-82 sigue vigente."
        baseline = MD.replace("Motivo: Se conserva el soporte.", old)
        data["reference"]["analysis_markdown"] = baseline
        candidates = [baseline.replace(old, old + " Nuevo motivo hoy."),
                      baseline.replace("Entrada: $90-92", "Entrada: $91-93")]
        for candidate in candidates:
            with self.subTest(candidate=candidate):
                result, audit = _rebase_inherited_motives(baseline, candidate, data)
                self.assertEqual(result, candidate)
                self.assertEqual(audit, [])
                self.assertIn("reprioritized_overlapping_level", " ".join(_validate_previous_level_references(result, "entrada_anterior: $90-92")))

    def test_unvalidated_undated_or_structural_motive_not_rebased(self):
        from src.local_runner.adaptive_maintenance import _rebase_inherited_motives
        for field, replacement in (("analysis_status", "failed"), ("generated_at", "invalid")):
            data = context()
            baseline = MD.replace("Motivo: Se conserva el soporte.", "Motivo: Se corrige: anterior $88-89.")
            data["reference"]["analysis_markdown"] = baseline
            data["reference"][field] = replacement
            with self.subTest(field=field):
                self.assertEqual(_rebase_inherited_motives(baseline, baseline, data), (baseline, []))
        data = context()
        baseline = MD.replace("Motivo: Invalida la estructura profunda.", "Motivo: Se reprioriza: el anterior $65 sigue vigente.")
        data["reference"]["analysis_markdown"] = baseline
        self.assertEqual(_rebase_inherited_motives(baseline, baseline, data), (baseline, []))

    def test_multiline_historical_motive_is_compared_in_its_entirety(self):
        from src.local_runner.adaptive_maintenance import _rebase_inherited_motives
        data = context()
        motive = "Motivo: Se corrige: anterior $88-89.\nLa segunda línea mantiene la explicación."
        baseline = MD.replace("Motivo: Se conserva el soporte.", motive)
        data["reference"]["analysis_markdown"] = baseline
        candidate = baseline.replace("La segunda línea mantiene", "La segunda línea cambia")
        self.assertEqual(_rebase_inherited_motives(baseline, candidate, data), (candidate, []))

    def test_byteexact_inherited_wall_metrics_refresh_only_same_dated_typed_origin(self):
        from src.local_runner.adaptive_maintenance import _refresh_wall_facts
        data = context()
        raw = "Factores de Entrada ambiciosa: reacción histórica; put wall **$80 del 16-Oct**, 11.3% del gamma put y 1.000 contratos.\n"
        baseline = MD.replace("Motivo: Se conserva el suelo.\n", "Motivo: Se conserva el suelo.\n" + raw)
        data["reference"]["analysis_markdown"] = baseline
        old = {"type": "put_wall", "level": 80, "expiration": "2026-10-16", "gamma_share_pct": 11.3, "oi": 1000}
        data["reference"]["slim_snapshot"] = {"levels": {"put_walls_top": [old]}}
        data["slim"]["levels"]["put_walls_top"] = [{**old, "gamma_share_pct": 12.2, "oi": 900}]
        candidate, audit = _refresh_wall_facts(baseline, baseline, data)
        self.assertIn("12.2% del gamma put y 900 contratos", candidate)
        self.assertEqual({entry["field"] for entry in audit}, {"gamma_share_pct", "oi"})
        self.assertEqual(audit[0]["old_pointer"], "/reference/slim_snapshot/levels/put_walls_top/0/gamma_share_pct")
        self.assertNotIn("Fortaleza", " ".join(entry["field"] for entry in audit))

    def test_changed_model_fact_paragraph_is_checked_not_silently_repaired(self):
        from src.local_runner.adaptive_maintenance import _refresh_wall_facts
        data = context()
        raw = "Factores de Entrada: reacción histórica; put wall $90 del 16-Oct, 11.3% del gamma put.\n"
        baseline = MD.replace("Motivo: Se conserva el soporte.\n", "Motivo: Se conserva el soporte.\n" + raw)
        old = {"type": "put_wall", "level": 90, "expiration": "2026-10-16", "gamma_share_pct": 11.3, "oi": 500}
        data["reference"]["slim_snapshot"] = {"levels": {"put_walls_top": [old]}}
        data["slim"]["levels"]["put_walls_top"] = [{**old, "gamma_share_pct": 12.2}]
        with self.assertRaisesRegex(ValueError, "stale_or_unproven_wall_metric"):
            _refresh_wall_facts(baseline, baseline.replace("reacción histórica", "reacción actual"), data)
        candidate, audit = _refresh_wall_facts(baseline, baseline.replace("11.3%", "12.2%"), data)
        self.assertIn("12.2%", candidate)
        self.assertEqual(audit, [])

    def test_ambiguous_removed_undated_or_unproven_wall_cannot_be_copied(self):
        from src.local_runner.adaptive_maintenance import _refresh_wall_facts
        raw = "Factores de Entrada: dos defensas; put wall $90 del 16-Oct, 11.3% del gamma put.\n"
        baseline = MD.replace("Motivo: Se conserva el soporte.\n", "Motivo: Se conserva el soporte.\n" + raw)
        old = {"type": "put_wall", "level": 90, "expiration": "2026-10-16", "gamma_share_pct": 11.3, "oi": 500}
        possibilities = [[], [{**old, "expiration": None}],
                         [{**old, "gamma_share_pct": 12.2}, {**old, "gamma_share_pct": 13.0}],
                         [{**old, "gamma_share_pct": 12.2}]]
        for index, current in enumerate(possibilities):
            data = context()
            data["reference"]["slim_snapshot"] = {"levels": {"put_walls_top": [old]}}
            data["slim"]["levels"]["put_walls_top"] = current
            if index == 3:
                data["reference"]["slim_snapshot"]["levels"]["put_walls_top"][0] = {**old, "gamma_share_pct": 10.0}
            with self.subTest(index=index), self.assertRaisesRegex(ValueError, "update_not_allowed_"):
                _refresh_wall_facts(baseline, baseline, data)

    def test_explicit_previous_metrics_are_not_misread_as_current(self):
        from src.local_runner.adaptive_maintenance import _refresh_wall_facts
        data = context()
        raw = "Factores de Entrada: reacción histórica; put wall $90 del 16-Oct, 12.2% del gamma put y 900 contratos, frente a 11.3% y 1000 en el snapshot previo.\n"
        old = {"type": "put_wall", "level": 90, "expiration": "2026-10-16", "gamma_share_pct": 11.3, "oi": 1000}
        data["reference"]["slim_snapshot"] = {"levels": {"put_walls_top": [old]}}
        data["slim"]["levels"]["put_walls_top"] = [{**old, "gamma_share_pct": 12.2, "oi": 900}]
        self.assertEqual(_refresh_wall_facts(MD, raw, data), (raw, []))

    def test_expired_wall_with_positive_metrics_is_not_current_evidence(self):
        from src.local_runner.adaptive_maintenance import _refresh_wall_facts
        data = context()
        data["slim"]["as_of"] = "2026-10-03T08:00:00Z"
        wall = {"type": "put_wall", "level": 90, "expiration": "2026-10-02", "gamma_share_pct": 11.3, "oi": 500}
        raw = "Factores de Entrada: dos defensas; put wall $90 del 02-Oct, 11.3% del gamma put y 500 contratos.\n"
        data["reference"]["slim_snapshot"] = {"levels": {"put_walls_top": [wall]}}
        data["slim"]["levels"]["put_walls_top"] = [{**wall, "gamma_share_pct": 12.2}]
        with self.assertRaisesRegex(ValueError, "update_not_allowed_expired_wall_fact"):
            _refresh_wall_facts(raw, raw, data)
        data["slim"]["levels"]["put_walls_top"][0]["gamma_share_pct"] = 11.3
        with self.assertRaisesRegex(ValueError, "update_not_allowed_expired_wall_fact"):
            _refresh_wall_facts(raw, raw, data)

    def test_explicit_historical_expired_wall_is_preserved_not_made_current(self):
        from src.local_runner.adaptive_maintenance import _refresh_wall_facts
        data = context()
        data["slim"]["as_of"] = "2026-10-03T08:00:00Z"
        wall = {"type": "put_wall", "level": 90, "expiration": "2026-10-02", "gamma_share_pct": 11.3, "oi": 500}
        data["reference"]["slim_snapshot"] = {"levels": {"put_walls_top": [wall]}}
        data["slim"]["levels"]["put_walls_top"] = [{**wall, "gamma_share_pct": 12.2, "oi": 300}]
        for prefix, suffix in (("", ", expirado"), ("Histórico: ", ""), ("", ", ya vencido")):
            raw = f"Factores de Entrada: dos defensas; {prefix}put wall $90 del 02-Oct{suffix}, 11.3% del gamma put y 500 contratos.\n"
            with self.subTest(prefix=prefix, suffix=suffix):
                self.assertEqual(_refresh_wall_facts(raw, raw, data), (raw, []))
        # A newly asserted historical number still needs the historical source.
        with self.assertRaisesRegex(ValueError, "unproven_historical_wall_metric"):
            _refresh_wall_facts(raw, raw.replace("11.3%", "99.0%"), data)

    def test_duplicate_wall_metrics_all_have_to_be_consistent_finite_numbers(self):
        from src.local_runner.adaptive_maintenance import _refresh_wall_facts
        data = context()
        wall = {"type": "put_wall", "level": 90, "expiration": "2026-10-16", "gamma_share_pct": 11.3, "oi": 500}
        raw = "Factores de Entrada: dos defensas; put wall $90 del 16-Oct, 11.3% del gamma put.\n"
        data["reference"]["slim_snapshot"] = {"levels": {"put_walls_top": [wall]}}
        for invalid in (True, False, None, "12.2", float("nan"), float("inf"), 13.0):
            data["slim"]["levels"]["put_walls_top"] = [{**wall, "gamma_share_pct": invalid}, {**wall, "gamma_share_pct": 12.2}]
            with self.subTest(invalid=invalid), self.assertRaisesRegex(ValueError, "unproven_current_wall_metric"):
                _refresh_wall_facts(raw, raw, data)
        bad = {key: value for key, value in wall.items() if key != "gamma_share_pct"}
        data["slim"]["levels"]["put_walls_top"] = [bad, {**wall, "gamma_share_pct": 12.2}]
        with self.assertRaisesRegex(ValueError, "unproven_current_wall_metric"):
            _refresh_wall_facts(raw, raw, data)
        data["slim"]["levels"]["put_walls_top"] = [{**wall, "gamma_share_pct": 12.2}, {**wall, "gamma_share_pct": 12.2}]
        updated, audit = _refresh_wall_facts(raw, raw, data)
        self.assertIn("12.2%", updated)
        self.assertEqual(audit[0]["current_pointer"], "/slim/levels/put_walls_top/0/gamma_share_pct")

    @staticmethod
    def continuation_fixture():
        data = context()
        walls = [{"type": "put_wall", "level": level, "expiration": "2026-10-16", "gamma_share_pct": gamma, "oi": 500}
                 for level, gamma in ((90, 9.0), (95, 15.1), (85, 12.2))]
        data["slim"]["levels"]["put_walls_top"] = walls
        raw = ("Factores de Entrada: 12 defensas; POC diario $92; volumen 17; "
               "put wall **$90 del 16-Oct**, 9.0% del gamma put, frente a 15.2% antes; "
               "el wall de $95 marca 15.1% y el de $85 12.2%.\n")
        return data, raw

    def test_proven_options_continuation_changes_one_delimiter_and_full_strength_parses(self):
        from src.local_runner.adaptive_maintenance import _normalize_wall_continuation
        from src.common.analysis_validator import extract_support_strength
        data, raw = self.continuation_fixture()
        strength = ("Fortaleza de Entrada: 69/100 · moderado\n"
                    "Desglose de Entrada: estructura 17/25; volumen 17/20; opciones 16/25; confluencia 9/15; durabilidad 10/15.\n")
        self.assertIsNotNone(extract_support_strength(strength + raw, "Entrada"))
        updated, audit = _normalize_wall_continuation(raw, data)
        self.assertEqual(updated, raw.replace("; el wall de", ", el wall de"))
        self.assertIsNotNone(extract_support_strength(strength + updated, "Entrada"))
        self.assertEqual(audit[0]["method"], "proven_options_factor_delimiter")
        self.assertEqual(audit[0]["before"], ";")
        self.assertEqual(audit[0]["after"], ",")
        self.assertEqual({neighbor["level"] for neighbor in audit[0]["neighbors"]}, {85, 95})

    def test_genuine_fifth_factor_and_nonexact_continuations_never_normalized(self):
        from src.local_runner.adaptive_maintenance import _normalize_wall_continuation
        data, raw = self.continuation_fixture()
        variants = [raw.replace("el wall de $95 marca 15.1% y el de $85 12.2%.", "RSI alcanza 40."),
                    raw.replace("12.2%.", "12.2%, RSI alcanza 40."),
                    raw.replace("volumen 17;", "volumen 17; RSI 40;"),
                    raw.replace("16-Oct", "expirado"),
                    raw.replace("9.0% del gamma put", "500 contratos")]
        for candidate in variants:
            with self.subTest(candidate=candidate):
                result, audit = _normalize_wall_continuation(candidate, data)
                self.assertEqual((result, audit), (candidate, []))

    def test_continuation_neighbors_require_same_current_side_expiry_and_metrics(self):
        from src.local_runner.adaptive_maintenance import _normalize_wall_continuation
        for mutation in ("removed", "wrong_side", "wrong_expiry", "wrong_metric", "bool", "expired"):
            data, raw = self.continuation_fixture()
            walls = data["slim"]["levels"]["put_walls_top"]
            if mutation == "removed":
                walls.pop()
            elif mutation == "wrong_side":
                walls.pop()
                data["slim"]["levels"]["call_walls_top"] = [{"type": "call_wall", "level": 85, "expiration": "2026-10-16", "gamma_share_pct": 12.2}]
            elif mutation == "wrong_expiry":
                walls[-1]["expiration"] = "2026-10-23"
            elif mutation == "wrong_metric":
                walls[-1]["gamma_share_pct"] = 13.0
            elif mutation == "bool":
                walls.append({**walls[-1], "gamma_share_pct": True})
            else:
                data["slim"]["as_of"] = "2026-10-17T08:00:00Z"
            with self.subTest(mutation=mutation), self.assertRaisesRegex(ValueError, "update_not_allowed_"):
                _normalize_wall_continuation(raw, data)

    def test_apply_update_preserves_delimiters_and_protected_report(self):
        data, raw = self.continuation_fixture()
        value = payload()
        value["edits"].append(edit("Motivo: Se conserva el soporte.", "Motivo: Se conserva el soporte.\n" + raw))
        audit = []
        result = apply_update(value, data, audit=audit)
        self.assertIn("; el wall de $95", result)
        self.assertIn("Narrativa actual: Crecimiento con riesgos conocidos.", result)
        self.assertEqual(audit, [])

if __name__ == "__main__":
    unittest.main()
