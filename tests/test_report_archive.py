from __future__ import annotations

import unittest

from src.local_runner.report_archive import (
    compact_history_entry,
    merge_history,
    select_stale_snapshot_uris,
)


class ReportArchiveTests(unittest.TestCase):
    def test_keeps_five_successful_snapshots_and_two_failures(self) -> None:
        uris: list[str] = []
        for day in range(1, 8):
            prefix = f"gs://bucket/RKLB/2026-07-{day:02d}/10-00-00"
            uris.extend([f"{prefix}.md", f"{prefix}.html", f"{prefix}.json"])
        for day in range(1, 5):
            uris.append(
                f"gs://bucket/RKLB/2026-06-{day:02d}/10-00-00.error.json"
            )

        stale = select_stale_snapshot_uris(uris)

        self.assertEqual(len(stale), 8)
        self.assertIn("gs://bucket/RKLB/2026-07-01/10-00-00.json", stale)
        self.assertNotIn("gs://bucket/RKLB/2026-07-03/10-00-00.json", stale)
        self.assertIn("gs://bucket/RKLB/2026-06-01/10-00-00.error.json", stale)
        self.assertNotIn("gs://bucket/RKLB/2026-06-03/10-00-00.error.json", stale)

    def test_ignores_latest_history_and_unrelated_objects(self) -> None:
        uris = [
            "gs://bucket/RKLB/latest.json",
            "gs://bucket/RKLB/history.json",
            "gs://bucket/RKLB/config.json",
        ]

        self.assertEqual(select_stale_snapshot_uris(uris), [])

    def test_builds_compact_history_entry(self) -> None:
        payload = {
            "symbol": "RKLB",
            "generated_at": "2026-07-12T08:00:00+00:00",
            "analysis_status": "ok",
            "latest_price": 75.0,
            "analysis_markdown": """
Valoración: **7.4 / 10**
1) Narrativa y catalizadores activos
- 2026-07-12 · Contrato · (+8)
Explicación corta
2) Próximo evento clave
2026-07-15 · Lanzamiento
Explicación
3) Plan
Entrada: **$74.8 - $75.5**
Entrada ambiciosa: **$70.0 - $71.0**
Estado actual: dentro de la zona
Stop de gestión: $72
Stop estructural: $66
Salida / objetivo principal: $90
""",
        }

        entry = compact_history_entry(payload)

        self.assertEqual(entry["score"], 7.4)
        self.assertEqual(entry["entry"], {"lower": 74.8, "upper": 75.5})
        self.assertEqual(entry["target"], "$90")
        self.assertEqual(entry["current_state"], "dentro de la zona")
        self.assertTrue(entry["catalysts"])

    def test_merge_history_replaces_same_generated_at(self) -> None:
        history = {
            "schema_version": 1,
            "entries": [{"generated_at": "2026-07-12", "score": 6.0}],
        }
        updated = merge_history(
            history,
            {"generated_at": "2026-07-12", "score": 7.0},
        )

        self.assertEqual(updated["entries"], [{"generated_at": "2026-07-12", "score": 7.0}])


if __name__ == "__main__":
    unittest.main()
