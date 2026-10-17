from __future__ import annotations

import unittest

from src.local_runner.level_continuity import build_level_continuity_precheck


PREVIOUS = """
Entrada: $59.70 - $60.20
Entrada ambiciosa: $44.50 - $45.00
"""


class LevelContinuityTests(unittest.TestCase):
    def test_flags_orphaned_ambitious_entry(self) -> None:
        slim = {
            "levels": {
                "supports": [
                    {"level": 60.25, "type": "gap_up_lower", "date": "2025-12-19"},
                    {"level": 37.57, "type": "52_week_low", "date": "2025-11-21"},
                ],
                "put_walls_top": [{"level": 60.0, "expiration": "2026-09-18"}],
            },
            "technicals": {"atr10": 2.6, "donchian20_low": 61.45},
        }

        result = build_level_continuity_precheck(PREVIOUS, slim)

        self.assertIn("Entrada anterior: 59.7-60.2", result)
        self.assertIn("evidence_present_in_current_slim", result)
        ambitious = result.split("Entrada ambiciosa anterior:", 1)[1]
        self.assertIn("missing_from_current_slim", ambitious)
        self.assertIn("prohíbe conservarlo por inercia", ambitious)

    def test_matches_current_technical_level_with_atr_tolerance(self) -> None:
        slim = {
            "levels": {"supports": [], "put_walls_top": []},
            "technicals": {"atr10": 2.0, "sma200": 45.4},
        }

        result = build_level_continuity_precheck(PREVIOUS, slim)
        ambitious = result.split("Entrada ambiciosa anterior:", 1)[1]

        self.assertIn("evidence_present_in_current_slim", ambitious)
        self.assertIn("sma200=45.4", ambitious)

    def test_without_previous_report_has_no_precheck(self) -> None:
        self.assertIn(
            "Sin informe anterior",
            build_level_continuity_precheck("", {}),
        )


if __name__ == "__main__":
    unittest.main()
