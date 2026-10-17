from __future__ import annotations

import unittest

from src.common.analysis_validator import validate_markdown


class AnalysisValidatorTests(unittest.TestCase):
    def test_parses_compact_unsigned_price_ranges(self) -> None:
        result = validate_markdown(
            """
Valoración: 4.8 / 10
Entrada: 52.6-53 (-1.3% a -0.6% vs precio actual)
Entrada ambiciosa: 47.8-48.2 (-10.3% a -9.6% vs precio actual)
"""
        )

        self.assertTrue(result.ok, result.errors)
        self.assertEqual(result.entry_range.to_dict(), {"lower": 52.6, "upper": 53.0})
        self.assertEqual(
            result.ambitious_entry_range.to_dict(),
            {"lower": 47.8, "upper": 48.2},
        )

    def test_requires_strength_for_both_supports_on_new_reports(self) -> None:
        result = validate_markdown(
            """
Valoración: 7.0 / 10
Entrada: $59.70 - $60.20
Motivo: soporte vigente
Fortaleza de Entrada: 86/100 · fuerte
Desglose de Entrada: estructura 22/25; volumen 17/20; opciones 21/25; confluencia 13/15; durabilidad 13/15
Factores de Entrada: EMA20 ascendente; HVN confirmado; put wall mensual
Entrada ambiciosa: $55.00 - $55.50
Motivo: soporte profundo
Fortaleza de Entrada ambiciosa: 72/100 · sólido
Desglose de Entrada ambiciosa: estructura 18/25; volumen 14/20; opciones 17/25; confluencia 11/15; durabilidad 12/15
Factores de Entrada ambiciosa: SMA200; mínimo previo
""",
            require_support_strengths=True,
        )

        self.assertTrue(result.ok)
        self.assertEqual(result.entry_strength.score, 86)
        self.assertEqual(result.entry_strength.category, "fuerte")
        self.assertEqual(result.ambitious_entry_strength.score, 72)

    def test_requires_structural_resistance_range_and_strength_on_schema_six_reports(self) -> None:
        result = validate_markdown(
            """
Valoración: 7.0 / 10
Entrada: $59.70 - $60.20
Entrada ambiciosa: Sin zona verificable
Resistencia estructural: $74.50 - $76.00
Fortaleza de Resistencia: 88/100 · fuerte
Desglose de Resistencia: estructura 22/25; volumen 17/20; opciones 22/25; confluencia 14/15; durabilidad 13/15
Factores de Resistencia: máximo semanal; rechazos con volumen; call wall mensual
""",
            require_resistance=True,
        )

        self.assertTrue(result.ok, result.errors)
        self.assertEqual(
            result.resistance_range.to_dict(),
            {"lower": 74.5, "upper": 76.0},
        )
        self.assertEqual(result.resistance_strength.score, 88)

    def test_rejects_missing_structural_resistance_strength(self) -> None:
        result = validate_markdown(
            """
Valoración: 7.0 / 10
Entrada: $59.70 - $60.20
Entrada ambiciosa: Sin zona verificable
Resistencia estructural: $74.50 - $76.00
""",
            require_resistance=True,
        )

        self.assertFalse(result.ok)
        self.assertTrue(
            any("resistance_strength" in error for error in result.errors)
        )

    def test_rejects_wrong_strength_category(self) -> None:
        result = validate_markdown(
            """
Valoración: 7.0 / 10
Entrada: $59.70 - $60.20
Fortaleza de Entrada: 81/100 · fuerte
Desglose de Entrada: estructura 21/25; volumen 16/20; opciones 20/25; confluencia 12/15; durabilidad 12/15
Factores de Entrada: EMA20; HVN
Entrada ambiciosa: Sin zona verificable
Fortaleza de Entrada ambiciosa: No aplicable
Desglose de Entrada ambiciosa: No aplicable
Factores de Entrada ambiciosa: No existe una zona defendible
""",
            require_support_strengths=True,
        )

        self.assertFalse(result.ok)
        self.assertTrue(any("entry_strength" in error for error in result.errors))

    def test_rejects_strength_without_evidence_text(self) -> None:
        result = validate_markdown(
            """
Valoración: 7.0 / 10
Entrada: $59.70 - $60.20
Fortaleza de Entrada: 86/100 · fuerte
Desglose de Entrada: estructura 22/25; volumen 17/20; opciones 21/25; confluencia 13/15; durabilidad 13/15
Factores de Entrada:
Entrada ambiciosa: Sin zona verificable
Fortaleza de Entrada ambiciosa: No aplicable
Desglose de Entrada ambiciosa: No aplicable
Factores de Entrada ambiciosa: No existe una zona defendible
""",
            require_support_strengths=True,
        )

        self.assertFalse(result.ok)
        self.assertTrue(any("entry_strength" in error for error in result.errors))

    def test_accepts_not_applicable_strength_only_without_ambitious_zone(self) -> None:
        result = validate_markdown(
            """
Valoración: 7.0 / 10
Entrada: $59.70 - $60.20
Fortaleza de Entrada: 75/100 · sólido
Desglose de Entrada: estructura 20/25; volumen 15/20; opciones 18/25; confluencia 11/15; durabilidad 11/15
Factores de Entrada: EMA20; HVN
Entrada ambiciosa: Sin zona verificable
Fortaleza de Entrada ambiciosa: No aplicable
Desglose de Entrada ambiciosa: No aplicable
Factores de Entrada ambiciosa: No existe una zona defendible
""",
            require_support_strengths=True,
        )

        self.assertTrue(result.ok)
        self.assertFalse(result.ambitious_entry_strength.applicable)

    def test_starts_strong_category_at_85(self) -> None:
        result = validate_markdown(
            """
Valoración: 7.0 / 10
Entrada: $59.70 - $60.20
Fortaleza de Entrada: 85/100 · fuerte
Desglose de Entrada: estructura 20/25; volumen 15/20; opciones 20/25; confluencia 15/15; durabilidad 15/15
Factores de Entrada: estructura multihorizonte; tres defensas; put wall mensual
Entrada ambiciosa: Sin zona verificable
Fortaleza de Entrada ambiciosa: No aplicable
Desglose de Entrada ambiciosa: No aplicable
Factores de Entrada ambiciosa: No existe una zona defendible
""",
            require_support_strengths=True,
        )

        self.assertTrue(result.ok)
        self.assertEqual(result.entry_strength.category, "fuerte")

    def test_starts_solid_category_at_70_with_required_evidence(self) -> None:
        result = validate_markdown(
            """
Valoración: 7.0 / 10
Entrada: $59.70 - $60.20
Fortaleza de Entrada: 70/100 · sólido
Desglose de Entrada: estructura 13/25; volumen 10/20; opciones 17/25; confluencia 15/15; durabilidad 15/15
Factores de Entrada: pivote diario; defensas históricas; put wall mensual
Entrada ambiciosa: Sin zona verificable
Fortaleza de Entrada ambiciosa: No aplicable
Desglose de Entrada ambiciosa: No aplicable
Factores de Entrada ambiciosa: No existe una zona defendible
""",
            require_support_strengths=True,
        )

        self.assertTrue(result.ok, result.errors)
        self.assertEqual(result.entry_strength.category, "sólido")

    def test_rejects_solid_total_without_minimum_structure(self) -> None:
        result = validate_markdown(
            """
Valoración: 7.0 / 10
Entrada: $59.70 - $60.20
Fortaleza de Entrada: 70/100 · sólido
Desglose de Entrada: estructura 12/25; volumen 14/20; opciones 18/25; confluencia 13/15; durabilidad 13/15
Factores de Entrada: put wall mensual; HVN aproximado; rango poco definido
Entrada ambiciosa: Sin zona verificable
Fortaleza de Entrada ambiciosa: No aplicable
Desglose de Entrada ambiciosa: No aplicable
Factores de Entrada ambiciosa: No existe una zona defendible
""",
            require_support_strengths=True,
        )

        self.assertFalse(result.ok)
        self.assertTrue(any("entry_strength" in error for error in result.errors))

    def test_rejects_options_heavy_strong_total_without_two_primary_pillars(self) -> None:
        result = validate_markdown(
            """
Valoración: 7.0 / 10
Entrada: $59.70 - $60.20
Fortaleza de Entrada: 85/100 · fuerte
Desglose de Entrada: estructura 17/25; volumen 13/20; opciones 25/25; confluencia 15/15; durabilidad 15/15
Factores de Entrada: put wall semanal; gamma concentrado; confluencia declarada
Entrada ambiciosa: Sin zona verificable
Fortaleza de Entrada ambiciosa: No aplicable
Desglose de Entrada ambiciosa: No aplicable
Factores de Entrada ambiciosa: No existe una zona defendible
""",
            require_support_strengths=True,
        )

        self.assertFalse(result.ok)
        self.assertTrue(any("entry_strength" in error for error in result.errors))

    def test_rejects_exceptional_total_without_exceptional_structure_and_volume(self) -> None:
        result = validate_markdown(
            """
Valoración: 8.0 / 10
Entrada: $59.70 - $60.20
Fortaleza de Entrada: 95/100 · excepcional
Desglose de Entrada: estructura 25/25; volumen 15/20; opciones 25/25; confluencia 15/15; durabilidad 15/15
Factores de Entrada: soporte técnico; defensas; opciones
Entrada ambiciosa: Sin zona verificable
Fortaleza de Entrada ambiciosa: No aplicable
Desglose de Entrada ambiciosa: No aplicable
Factores de Entrada ambiciosa: No existe una zona defendible
""",
            require_support_strengths=True,
        )

        self.assertFalse(result.ok)

    def test_rejects_breakdown_that_does_not_sum_to_total(self) -> None:
        result = validate_markdown(
            """
Valoración: 7.0 / 10
Entrada: $59.70 - $60.20
Fortaleza de Entrada: 85/100 · fuerte
Desglose de Entrada: estructura 21/25; volumen 16/20; opciones 20/25; confluencia 12/15; durabilidad 12/15
Factores de Entrada: EMA20; HVN
Entrada ambiciosa: Sin zona verificable
Fortaleza de Entrada ambiciosa: No aplicable
Desglose de Entrada ambiciosa: No aplicable
Factores de Entrada ambiciosa: No existe una zona defendible
""",
            require_support_strengths=True,
        )

        self.assertFalse(result.ok)
        self.assertTrue(any("entry_strength" in error for error in result.errors))

    def test_accepts_explicitly_unavailable_ambitious_entry(self) -> None:
        result = validate_markdown(
            """
Valoración: 7.0 / 10
Entrada: $59.70 - $60.20
Entrada ambiciosa: Sin zona verificable
Motivo: Se retira: no existe soporte vigente defendible.
"""
        )

        self.assertTrue(result.ok)
        self.assertIsNone(result.ambitious_entry_range)

    def test_rejects_unavailable_ambitious_entry_when_slim_has_lower_support(self) -> None:
        result = validate_markdown(
            """
Valoración: 6.7 / 10
Entrada: $140 - $141
Entrada ambiciosa: Sin zona verificable
Motivo: el soporte de $119 está demasiado lejos y tiene poca confluencia.
""",
            authoritative_context="""
## JSON Técnico Slim

```json
{"latest_price": 156.28, "levels": {"supports": [
  {"level": 143.47, "type": "range_bottom_3_6m"},
  {"level": 119.27, "type": "52_week_low"}
]}}
```
""",
        )

        self.assertFalse(result.ok)
        self.assertTrue(
            any(
                "ambitious_entry_unavailable_despite_lower_support" in error
                and "$119.27" in error
                for error in result.errors
            )
        )

    def test_allows_unavailable_ambitious_entry_without_distinct_lower_support(self) -> None:
        result = validate_markdown(
            """
Valoración: 6.7 / 10
Entrada: $140 - $141
Entrada ambiciosa: Sin zona verificable
Motivo: no existe soporte inferior distinto.
""",
            authoritative_context="""
## JSON Técnico Slim

```json
{"levels": {"supports": [{"level": 139.5, "type": "moving_average"}]}}
```
""",
        )

        self.assertTrue(result.ok)

    def test_allows_unavailable_ambitious_entry_when_only_lower_support_is_remote(self) -> None:
        result = validate_markdown(
            """
Valoración: 6.7 / 10
Entrada: $140 - $141
Entrada ambiciosa: Sin zona verificable
Motivo: el único soporte inferior está fuera de la ventana operativa.
""",
            authoritative_context="""
## JSON Técnico Slim

```json
{"latest_price": 156.28, "technicals": {"atr10": 5.0}, "options": {"expected_move_1w_abs": 6.0}, "levels": {"supports": [
  {"level": 119.27, "type": "52_week_low"}
]}}
```
""",
        )

        self.assertTrue(result.ok)

    def test_rejects_unavailable_ambitious_entry_when_lower_support_is_reachable(self) -> None:
        result = validate_markdown(
            """
Valoración: 6.7 / 10
Entrada: $140 - $141
Entrada ambiciosa: Sin zona verificable
Motivo: no existe soporte inferior distinto.
""",
            authoritative_context="""
## JSON Técnico Slim

```json
{"latest_price": 156.28, "technicals": {"atr10": 10.0}, "options": {"expected_move_1w_abs": 15.0}, "levels": {"supports": [
  {"level": 132.0, "type": "range_bottom_3_6m"}
]}}
```
""",
        )

        self.assertFalse(result.ok)
        self.assertTrue(
            any("ambitious_entry_unavailable_despite_lower_support" in error for error in result.errors)
        )

    def test_parses_us_thousands_separators_without_losing_scale(self) -> None:
        result = validate_markdown(
            """
Valoracion: 7.7 / 10
Entrada: $1,450 - $1,460
Entrada ambiciosa: $1,355 - $1,365
"""
        )

        self.assertTrue(result.ok)
        self.assertEqual(result.entry_range.lower, 1450.0)
        self.assertEqual(result.entry_range.upper, 1460.0)
        self.assertEqual(result.ambitious_entry_range.lower, 1355.0)

    def test_parses_spanish_thousands_separators_without_losing_scale(self) -> None:
        result = validate_markdown(
            """
Valoracion: 7.5 / 10
Entrada: $1.638 - $1.646
Entrada ambiciosa: $1.576 - $1.586
"""
        )

        self.assertTrue(result.ok)
        self.assertEqual(result.entry_range.lower, 1638.0)
        self.assertEqual(result.entry_range.upper, 1646.0)
        self.assertEqual(result.ambitious_entry_range.lower, 1576.0)

    def test_rejects_missing_ambitious_entry(self) -> None:
        result = validate_markdown(
            """
Valoración: 7.0 / 10
Entrada: $59.70 - $60.20
"""
        )

        self.assertFalse(result.ok)
        self.assertTrue(any("ambitious_entry" in error for error in result.errors))

if __name__ == "__main__":
    unittest.main()
