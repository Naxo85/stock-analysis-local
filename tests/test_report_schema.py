from __future__ import annotations

import unittest
from datetime import datetime, timezone

from src.local_runner.report_schema import build_structured_report


def _report(
    *,
    score: float = 7.0,
    entry: str = "$74.8 - $75.5",
    entry_reason: str = "Confluencia de soporte y volumen",
    ambitious_entry: str = "$70 - $71",
    ambitious_reason: str = "Washout",
    structural_stop: str = "$66",
    structural_reason: str = "Pérdida de soporte estructural",
    resistance: str = "$118 - $122",
    resistance_reason: str = "Techo semanal con oferta confirmada",
    target: str = "$90",
    target_reason: str = "Resistencia principal",
    catalyst: str = "Contrato relevante",
    impact: int = 8,
    event_date: str = "2026-07-15",
    event: str = "Lanzamiento de Neutron",
) -> str:
    return f"""RKLB
Fecha del análisis: 2026-07-12
Precio de referencia: $76

0) Resumen ejecutivo
Valoración: {score} / 10
Narrativa actual: Tesis vigente con mejor validación.

1) Narrativa y catalizadores activos
2026-07-12 · {catalyst} · ({impact:+d})
Explicación corta

2) Próximo evento clave
{event_date} · {event}
Explicación del evento

3) Plan
Entrada: {entry}
Motivo: {entry_reason}
Fortaleza de Entrada: 86/100 · fuerte
Desglose de Entrada: estructura 22/25; volumen 17/20; opciones 21/25; confluencia 13/15; durabilidad 13/15
Factores de Entrada: EMA20 ascendente; HVN confirmado; put wall mensual

Entrada ambiciosa: {ambitious_entry}
Motivo: {ambitious_reason}
Fortaleza de Entrada ambiciosa: 72/100 · sólido
Desglose de Entrada ambiciosa: estructura 18/25; volumen 14/20; opciones 17/25; confluencia 11/15; durabilidad 12/15
Factores de Entrada ambiciosa: SMA200; mínimo previo

Stop de gestión: $72
Motivo: Protección táctica

Stop estructural: {structural_stop}
Motivo: {structural_reason}

Resistencia estructural: {resistance}
Motivo: {resistance_reason}
Fortaleza de Resistencia: 88/100 · fuerte
Desglose de Resistencia: estructura 22/25; volumen 17/20; opciones 22/25; confluencia 14/15; durabilidad 13/15
Factores de Resistencia: máximo semanal; rechazos con volumen; call wall mensual

Salida / objetivo principal: {target}
Motivo: {target_reason}
"""


class ReportSchemaTests(unittest.TestCase):
    def test_exports_support_strengths_to_structured_plan(self) -> None:
        result = build_structured_report(
            markdown=_report(),
            generated_at=datetime(2026, 7, 12, tzinfo=timezone.utc),
            latest_price=76.0,
        )

        self.assertEqual(result["schema_version"], 7)
        self.assertEqual(result["plan"]["entry_strength_score"], 86)
        self.assertEqual(result["plan"]["entry_strength_category"], "fuerte")
        self.assertIn("HVN", result["plan"]["entry_strength_factors"])
        self.assertEqual(result["plan"]["washout_strength_score"], 72)
        self.assertEqual(result["plan"]["entry_strength_breakdown"]["opciones"], 21)
        self.assertEqual(
            result["plan"]["resistance"],
            {"lower": 118.0, "upper": 122.0},
        )
        self.assertEqual(result["plan"]["resistance_strength_score"], 88)

    def test_reports_material_resistance_change_independently_from_target(self) -> None:
        previous = _report(resistance="$118 - $122", target="$90")
        current = _report(
            resistance="$145 - $150",
            resistance_reason=(
                "Se reprioriza: 118-122 sigue vigente, pero 145-150 es la "
                "barrera estructural más fuerte"
            ),
            target="$90",
        )

        result = build_structured_report(
            markdown=current,
            generated_at=datetime(2026, 7, 12, tzinfo=timezone.utc),
            latest_price=76.0,
            previous_markdown=previous,
        )

        changes = result["changes"]["plan_changes"]
        self.assertEqual([item["field"] for item in changes], ["resistance"])

    def test_ignores_small_plan_changes(self) -> None:
        previous = _report(entry="$74.8 - $75.5", target="$90", structural_stop="$66")
        current = _report(
            entry="$74.9 - $75.6",
            entry_reason="Confluencia ligeramente actualizada",
            target="$90.5",
            target_reason="Resistencia recalculada",
            structural_stop="$65.8",
            structural_reason="Soporte recalculado",
        )

        result = build_structured_report(
            markdown=current,
            generated_at=datetime(2026, 7, 12, tzinfo=timezone.utc),
            latest_price=76.0,
            previous_markdown=previous,
        )

        self.assertEqual(result["changes"]["plan_changes"], [])
        self.assertFalse(any(a["type"] == "plan_change" for a in result["alerts"]))

    def test_reports_material_entry_change_with_new_reason(self) -> None:
        previous = _report()
        current = _report(
            entry="$71 - $72",
            entry_reason="Pérdida confirmada del soporte anterior",
        )

        result = build_structured_report(
            markdown=current,
            generated_at=datetime(2026, 7, 12, tzinfo=timezone.utc),
            latest_price=76.0,
            previous_markdown=previous,
        )

        changes = result["changes"]["plan_changes"]
        self.assertEqual([item["field"] for item in changes], ["entry"])
        self.assertIn("Pérdida confirmada", changes[0]["message"])

    def test_reports_material_ambitious_entry_change(self) -> None:
        previous = _report()
        current = _report(
            ambitious_entry="$60 - $61",
            ambitious_reason="Se corrige: desapareció el soporte anterior; nuevo gap vigente",
        )

        result = build_structured_report(
            markdown=current,
            generated_at=datetime(2026, 7, 12, tzinfo=timezone.utc),
            latest_price=76.0,
            previous_markdown=previous,
        )

        change = result["changes"]["plan_changes"][0]
        self.assertEqual(change["field"], "ambitious_entry")
        self.assertEqual(change["change_kind"], "moved")

    def test_reports_removed_ambitious_entry(self) -> None:
        previous = _report()
        current = _report(
            ambitious_entry="Sin zona verificable",
            ambitious_reason="Se retira: el soporte anterior ya no aparece y no hay sustituto",
        )

        result = build_structured_report(
            markdown=current,
            generated_at=datetime(2026, 7, 12, tzinfo=timezone.utc),
            latest_price=76.0,
            previous_markdown=previous,
        )

        change = result["changes"]["plan_changes"][0]
        self.assertEqual(change["field"], "ambitious_entry")
        self.assertEqual(change["change_kind"], "removed")
        self.assertIsNone(change["current"])

    def test_reports_replaced_evidence_at_same_ambitious_range(self) -> None:
        previous = _report(ambitious_reason="Gap alcista antiguo")
        current = _report(
            ambitious_reason="Se sustituye fundamento: ahora coincide con SMA200 vigente",
        )

        result = build_structured_report(
            markdown=current,
            generated_at=datetime(2026, 7, 12, tzinfo=timezone.utc),
            latest_price=76.0,
            previous_markdown=previous,
        )

        change = result["changes"]["plan_changes"][0]
        self.assertEqual(change["change_kind"], "evidence_replaced")

    def test_parses_legacy_reason_prose_after_current_state(self) -> None:
        markdown = _report().replace(
            "Entrada: $74.8 - $75.5\nMotivo: Confluencia de soporte y volumen",
            "Entrada: $74.8 - $75.5\nEstado actual: por encima de la zona\n"
            "Se conserva: confluencia vigente",
        )
        result = build_structured_report(
            markdown=markdown,
            generated_at=datetime(2026, 7, 12, tzinfo=timezone.utc),
            latest_price=76.0,
        )

        self.assertEqual(
            result["plan"]["entry_reason"],
            "Se conserva: confluencia vigente",
        )

    def test_does_not_alert_on_material_number_without_changed_reason(self) -> None:
        previous = _report()
        current = _report(entry="$71 - $72")

        result = build_structured_report(
            markdown=current,
            generated_at=datetime(2026, 7, 12, tzinfo=timezone.utc),
            latest_price=76.0,
            previous_markdown=previous,
        )

        self.assertEqual(result["changes"]["plan_changes"], [])

    def test_score_change_and_new_large_catalyst_create_alerts(self) -> None:
        previous = _report(score=6.6, catalyst="Catalizador anterior", impact=6)
        current = _report(score=7.4, catalyst="Nuevo contrato gubernamental", impact=8)

        result = build_structured_report(
            markdown=current,
            generated_at=datetime(2026, 7, 12, tzinfo=timezone.utc),
            latest_price=76.0,
            previous_markdown=previous,
        )

        alert_types = [alert["type"] for alert in result["alerts"]]
        self.assertIn("score_change", alert_types)
        self.assertIn("new_catalyst", alert_types)

    def test_only_near_event_creates_home_alert(self) -> None:
        near = build_structured_report(
            markdown=_report(event_date="2026-07-15", event="Lanzamiento de Neutron"),
            generated_at=datetime(2026, 7, 12, tzinfo=timezone.utc),
            latest_price=76.0,
        )
        far = build_structured_report(
            markdown=_report(event_date="2026-08-15", event="Resultados Q2"),
            generated_at=datetime(2026, 7, 12, tzinfo=timezone.utc),
            latest_price=76.0,
        )

        self.assertTrue(near["next_event"]["is_near"])
        self.assertTrue(any(a["type"] == "near_event" for a in near["alerts"]))
        self.assertFalse(far["next_event"]["is_near"])
        self.assertFalse(any(a["type"] == "near_event" for a in far["alerts"]))

    def test_routine_options_expiry_never_creates_home_alert(self) -> None:
        result = build_structured_report(
            markdown=_report(
                event_date="2026-07-17",
                event="Vencimiento mensual de opciones",
            ),
            generated_at=datetime(2026, 7, 12, tzinfo=timezone.utc),
            latest_price=76.0,
        )

        self.assertTrue(result["next_event"]["is_near"])
        self.assertTrue(result["next_event"]["is_routine_market_event"])
        self.assertFalse(result["next_event"]["is_home_relevant"])
        self.assertFalse(
            any(a["type"] == "near_event" for a in result["alerts"])
        )

    def test_never_creates_price_position_alerts(self) -> None:
        result = build_structured_report(
            markdown=_report(entry="$75 - $76"),
            generated_at=datetime(2026, 7, 12, tzinfo=timezone.utc),
            latest_price=75.5,
        )

        self.assertFalse(
            any(alert["type"] in {"inside_entry", "near_entry"} for alert in result["alerts"])
        )


if __name__ == "__main__":
    unittest.main()
