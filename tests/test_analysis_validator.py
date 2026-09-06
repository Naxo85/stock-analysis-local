from __future__ import annotations

import unittest

from src.common.analysis_validator import validate_markdown


class AnalysisValidatorTests(unittest.TestCase):
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
