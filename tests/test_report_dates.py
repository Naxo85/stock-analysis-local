from __future__ import annotations

import unittest
from datetime import datetime, timezone

from src.local_runner.report_dates import normalize_report_dates
from src.local_runner.report_schema import build_structured_report


class ReportDateTests(unittest.TestCase):
    def test_normalizes_dates_and_sorts_complete_catalyst_blocks(self) -> None:
        markdown = """RKLB
Fecha del análisis: 2026-09-11

1) Narrativa y catalizadores activos
2026-08-30 · Antiguo · (-6)
Primera línea antigua
Segunda línea antigua

11-09-2026 · Reciente A · (+8)
Explicación reciente A

2026-99-40 · Fecha inválida · (+5)
Explicación inválida

2026-09-11 · Reciente B · (-7)
Explicación reciente B

2) Próximo evento clave
2026-10-03 · Lanzamiento
Explicación del evento

3) Plan
Entrada: $10 - $11
"""

        result = normalize_report_dates(markdown)

        self.assertIn("Fecha del análisis: 11-09-2026", result)
        self.assertIn("03-10-2026 · Lanzamiento", result)
        positions = [
            result.index("Reciente A"),
            result.index("Reciente B"),
            result.index("Antiguo"),
            result.index("Fecha inválida"),
        ]
        self.assertEqual(positions, sorted(positions))
        self.assertLess(result.index("Primera línea antigua"), result.index("Segunda línea antigua"))
        self.assertLess(result.index("Segunda línea antigua"), result.index("Fecha inválida"))

    def test_structured_contract_keeps_iso_dates_for_compatibility(self) -> None:
        markdown = """RKLB
Fecha del análisis: 11-09-2026
0) Resumen ejecutivo
Valoración: 7 / 10
Narrativa actual: Vigente.
1) Narrativa y catalizadores activos
10-09-2026 · Contrato · (+7)
Explicación
2) Próximo evento clave
03-10-2026 · Lanzamiento
Explicación
3) Plan
Entrada: $10 - $11
Motivo: Soporte
Entrada ambiciosa: $8 - $9
Motivo: Soporte profundo
Stop de gestión: $9
Motivo: Riesgo
Stop estructural: $7
Motivo: Invalida
Salida / objetivo principal: $15
Motivo: Resistencia
"""
        result = build_structured_report(
            markdown=markdown,
            generated_at=datetime(2026, 9, 11, tzinfo=timezone.utc),
            latest_price=12.0,
        )

        self.assertEqual(result["catalysts"][0]["date"], "2026-09-10")
        self.assertEqual(result["next_event"]["date"], "2026-10-03")
        self.assertEqual(result["next_event"]["days_away"], 22)


if __name__ == "__main__":
    unittest.main()
