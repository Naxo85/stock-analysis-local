from __future__ import annotations

import unittest
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from src.common.analysis_validator import validate_markdown
from src.local_runner.chatgpt_browser_generator import (
    DEFAULT_CLEANUP_DELAY_SECONDS,
    DEFAULT_CLEANUP_MAX_CHATS,
    DEFAULT_CLEANUP_MIN_AGE_SECONDS,
    DEFAULT_RATE_LIMIT_WAIT_SECONDS,
    _eligible_cleanup_items,
    _load_cleanup_queue,
    _queue_chat_for_cleanup,
    build_analysis_request,
    extract_level_continuity_requirements,
    sanitize_internal_citation_markers,
)
from src.local_runner.previous_analysis import PreviousAnalysisContext
from src.local_runner.run_one import _build_previous_analysis_attachment


class ChatGPTPreviousAnalysisTests(unittest.TestCase):
    def test_request_names_both_authoritative_attachments(self) -> None:
        request = build_analysis_request("RKLB")
        self.assertIn("`codex_input.md`", request)
        self.assertIn("`previous_analysis.md`", request)
        self.assertIn("catalizadores", request)

    def test_request_repeats_the_complete_strength_contract_in_composer(self) -> None:
        request = build_analysis_request("RKLB")

        self.assertIn("CONTROL OBLIGATORIO DE SELECCION DE SOPORTES", request)
        self.assertIn("dentro de 1 ATR10", request)
        self.assertIn("dentro de 2 ATR10", request)
        self.assertIn("difieren menos de 5 puntos", request)
        self.assertIn("un soporte remoto no obliga", request)
        self.assertIn("CONTROL FINAL OBLIGATORIO DE FORTALEZA", request)
        self.assertIn("Fortaleza de Entrada: N/100", request)
        self.assertIn("Desglose de Entrada:", request)
        self.assertIn("Factores de Entrada:", request)
        self.assertIn("Fortaleza de Entrada ambiciosa", request)
        self.assertIn("Desglose de Entrada ambiciosa", request)
        self.assertIn("Factores de Entrada ambiciosa", request)
        self.assertIn("Resistencia estructural", request)
        self.assertIn("Fortaleza de Resistencia", request)
        self.assertIn("Desglose de Resistencia", request)
        self.assertIn("Factores de Resistencia", request)
        self.assertIn("no penalices que este al 1%, 20% o 50%", request)
        self.assertIn("A+B+C+D+E debe ser exactamente N", request)
        self.assertIn("Puntua primero A, B, C, D y E", request)
        self.assertIn("asigna la categoria solo al final", request)
        self.assertIn("40, 70, 85 o 95", request)
        self.assertIn("estructura >=13", request)
        self.assertIn("estructura >=18", request)
        self.assertIn("estructura >=22", request)
        self.assertIn("POC/HVN 0-4", request)
        self.assertIn("al menos 3 tests con 2 defensas", request)
        self.assertIn("no puede superar 12", request)

    def test_authoritative_prompt_prevents_strength_threshold_anchoring(self) -> None:
        prompt = Path("prompts/stock_analysis_system_prompt.md").read_text(
            encoding="utf-8"
        )

        self.assertIn("puntúa primero cada subcriterio", prompt)
        self.assertIn("suma después mecánicamente", prompt)
        self.assertIn("asigna la categoría únicamente al final", prompt)
        self.assertIn("No uses 40, 70, 85 ni 95 como valores predeterminados", prompt)
        self.assertIn("Estructura alcanza al menos 13 puntos", prompt)
        self.assertIn("Estructura ≥18, Volumen/reacción ≥14 y Opciones ≥18", prompt)
        self.assertIn("Estructura ≥22, Volumen/reacción ≥17", prompt)

    def test_authoritative_prompt_uses_mechanical_volume_reaction_bands(self) -> None:
        prompt = Path("prompts/stock_analysis_system_prompt.md").read_text(
            encoding="utf-8"
        )

        self.assertIn("POC/HVN, 0–4", prompt)
        self.assertIn("Repetición, 0–5 según `defense_count`", prompt)
        self.assertIn("Tasa de defensa, 0–4", prompt)
        self.assertIn("Magnitud y consistencia, 0–4", prompt)
        self.assertIn("Recencia, 0–3", prompt)
        self.assertIn("el componente no puede superar 12", prompt)
        self.assertIn("Para superar 15 exige POC/HVN", prompt)
        self.assertIn("Para obtener 19–20 exige POC/HVN", prompt)
        self.assertIn("no redistribuyas los puntos retirados", prompt)

    def test_authoritative_prompt_selects_strength_within_reachability_windows(self) -> None:
        prompt = Path("prompts/stock_analysis_system_prompt.md").read_text(
            encoding="utf-8"
        )

        self.assertIn("fortaleza condicionada por alcanzabilidad", prompt)
        self.assertIn("hasta 1 ATR10 o 1 movimiento esperado semanal", prompt)
        self.assertIn("hasta 2 ATR10 o 2 movimientos esperados semanales", prompt)
        self.assertIn("diferencia inferior a 5 puntos no es material", prompt)
        self.assertIn("0,35 ATR10", prompt)
        self.assertIn("Un soporte remoto puede mencionarse", prompt)

    def test_strength_retry_calls_out_all_nine_required_labels(self) -> None:
        request = build_analysis_request(
            "RKLB",
            previous_errors=(
                "missing_or_invalid_entry_strength: expected integer N/100",
            ),
        )

        self.assertIn("respuesta anterior omitio o construyo mal", request)
        self.assertIn("nueve etiquetas obligatorias", request)
        self.assertIn("cada desglose sume su N/100", request)

    def test_request_repeats_exact_previous_levels_in_composer(self) -> None:
        source = """
nota_anterior: 8.0
entrada_anterior: 447-451
entrada_ambiciosa_anterior: 421-426
stop_de_gestion_anterior: $449 (-4.5% vs precio actual)
resistencia_anterior: 520-525
"""
        continuity = extract_level_continuity_requirements(source)
        request = build_analysis_request(
            "AMD",
            continuity_requirements=continuity,
        )
        self.assertIn("entrada_anterior: 447-451", request)
        self.assertIn("entrada_ambiciosa_anterior: 421-426", request)
        self.assertIn("resistencia_anterior: 520-525", request)
        self.assertIn("No recalcules, redondees", request)
        self.assertIn("Se reprioriza", request)
        self.assertIn("Si es el mismo soporte", request)

    def test_retry_explains_previous_level_mismatch_expected_values(self) -> None:
        request = build_analysis_request(
            "AMD",
            previous_errors=(
                "previous_level_mismatch: Entrada expected=447,451",
            ),
        )
        self.assertIn("expected son los precios anteriores exactos", request)

    def test_validation_retry_repairs_only_the_previous_complete_response(self) -> None:
        error = (
            "missing_previous_level_continuity: Salida must explicitly say "
            "Se conserva, Se reprioriza, Se corrige or Se retira"
        )
        request = build_analysis_request(
            "TSLA",
            previous_errors=(error,),
            repair_previous_response=True,
        )

        self.assertIn("Repite completa tu respuesta inmediatamente anterior", request)
        self.assertIn("No vuelvas a investigar ni rehagas el analisis", request)
        self.assertIn(error, request)
        self.assertIn("cambia solo los campos necesarios", request)
        self.assertNotIn("Genera el analisis completo", request)

    def test_chat_cleanup_queue_uses_url_id_and_deduplicates(self) -> None:
        with TemporaryDirectory() as temporary:
            cwd = Path(temporary)
            url = "https://chatgpt.com/c/chat-id-123"
            self.assertIsNone(
                _queue_chat_for_cleanup(cwd, url, symbol="AMD", attempt=1)
            )
            self.assertIsNone(
                _queue_chat_for_cleanup(cwd, url, symbol="AMD", attempt=1)
            )
            queue = _load_cleanup_queue(
                cwd / ".local" / "chatgpt-chat-cleanup-queue.json"
            )
            self.assertEqual(len(queue), 1)
            self.assertEqual(queue[0]["chat_id"], "chat-id-123")
            self.assertEqual(queue[0]["symbol"], "AMD")

    def test_cleanup_is_slow_capped_and_only_uses_aged_chats(self) -> None:
        self.assertEqual(DEFAULT_CLEANUP_MAX_CHATS, 2)
        self.assertEqual(DEFAULT_CLEANUP_DELAY_SECONDS, 600)
        self.assertEqual(DEFAULT_CLEANUP_MIN_AGE_SECONDS, 21600)
        self.assertEqual(DEFAULT_RATE_LIMIT_WAIT_SECONDS, 300)
        queue = [
            {"chat_id": "old-1", "queued_at": "2026-09-09T00:00:00+00:00"},
            {"chat_id": "old-2", "queued_at": "2026-09-09T01:00:00+00:00"},
            {"chat_id": "old-3", "queued_at": "2026-09-09T02:00:00+00:00"},
            {"chat_id": "new", "queued_at": "2026-09-10T11:00:00+00:00"},
        ]

        selected = _eligible_cleanup_items(
            queue,
            max_chats=DEFAULT_CLEANUP_MAX_CHATS,
            min_age_seconds=DEFAULT_CLEANUP_MIN_AGE_SECONDS,
            now=datetime(2026, 9, 10, 12, 0, tzinfo=timezone.utc),
        )

        self.assertEqual([item["chat_id"] for item in selected], ["old-1", "old-2"])

    def test_sanitizes_only_internal_chatgpt_citation_markers(self) -> None:
        markdown = (
            "# APP\n\n"
            "Hecho confirmado. :contentReference[oaicite:0]{index=0}\n\n"
            "[Fuente visible](https://example.com) permanece.\n"
        )

        sanitized, removed = sanitize_internal_citation_markers(markdown)

        self.assertEqual(removed, 1)
        self.assertNotIn("contentReference", sanitized)
        self.assertIn("[Fuente visible](https://example.com)", sanitized)

    def test_sanitizer_is_noop_without_internal_markers(self) -> None:
        markdown = "# APP\n\nTexto normal con oaicite como palabra literal.\n"

        sanitized, removed = sanitize_internal_citation_markers(markdown)

        self.assertEqual((sanitized, removed), (markdown, 0))

    def test_previous_attachment_keeps_complete_report_verbatim(self) -> None:
        report = "# RKLB\n\n1) Narrativa y catalizadores activos\n\n- Catalizador completo.\n"
        context = PreviousAnalysisContext(
            found=True,
            source_uri="gs://bucket/RKLB/latest.json",
            generated_at="2026-09-05T08:16:54+00:00",
            analysis_markdown=report,
        )
        attachment = _build_previous_analysis_attachment("RKLB", context)
        self.assertIn("Generated at: 2026-09-05T08:16:54+00:00", attachment)
        self.assertTrue(attachment.endswith(report))

    def test_rejects_claim_that_previous_report_is_inaccessible(self) -> None:
        result = validate_markdown(
            """
Valoración: 7.0 / 10
Entrada: $59.70 - $60.20
Motivo: Sin comparación de continuidad, porque el informe anterior no está accesible.
Entrada ambiciosa: Sin zona verificable
""",
            authoritative_context="Informe anterior disponible.\nentrada_anterior: 59.7-60.2",
        )
        self.assertFalse(result.ok)
        self.assertTrue(any("previous_analysis_ignored" in error for error in result.errors))

    def test_rejects_replacing_basis_without_recalculating_level(self) -> None:
        result = validate_markdown(
            """
Valoración: 7.0 / 10
Entrada: $55.20 - $55.70
Motivo: Se sustituye fundamento: el soporte técnico anterior desapareció, pero ahora coincide con un put wall.
Entrada ambiciosa: Sin zona verificable
""",
            authoritative_context=(
                "Informe anterior disponible.\n"
                "entrada_anterior: 55.2-55.7\n"
                "entrada_ambiciosa_anterior: null"
            ),
        )
        self.assertFalse(result.ok)
        self.assertTrue(
            any("invalid_previous_level_continuity" in error for error in result.errors)
        )

    def test_accepts_compact_previous_price_ranges_in_correction_reason(self) -> None:
        result = validate_markdown(
            """
Valoración: 8.3 / 10
Entrada: $496-500
Motivo: Se corrige: la Entrada anterior era $447-451; su fundamento ya no aplica y se recalcula desde cero.
Entrada ambiciosa: $477-481
Motivo: Se corrige: la Entrada ambiciosa anterior era $421-426; su fundamento ya no aplica y se recalcula desde cero.
""",
            authoritative_context=(
                "entrada_anterior: 447-451\n"
                "entrada_ambiciosa_anterior: 421-426"
            ),
        )
        self.assertTrue(result.ok, result.errors)

    def test_accepts_previous_prices_without_repeated_currency_sign(self) -> None:
        result = validate_markdown(
            """
Valoración: 4.9 / 10
Entrada: $14.95-$15.05
Motivo: Se corrige: la Entrada anterior tenía exactamente los precios 16 y 16.15; deja de actuar como soporte y se recalcula desde cero.
Entrada ambiciosa: $14-$14.2
Motivo: Se conserva: la Entrada ambiciosa anterior exacta de 14-14.2 sigue vigente.
""",
            authoritative_context=(
                "entrada_anterior: 16-16.15\n"
                "entrada_ambiciosa_anterior: 14-14.2"
            ),
        )

        self.assertTrue(result.ok, result.errors)

    def test_accepts_reprioritizing_a_distinct_stronger_support(self) -> None:
        result = validate_markdown(
            """
Valoración: 8.3 / 10
Entrada: $109.50-110.50
Motivo: Se reprioriza: la Entrada anterior de $99.50-100.50 sigue siendo soporte válido, pero la nueva zona es distinta y tiene mayor fortaleza, confluencia y proximidad operativa.
Entrada ambiciosa: Sin zona verificable
Motivo: Se retira: la Entrada ambiciosa anterior de $90-91 ya no tiene evidencia vigente.
""",
            authoritative_context=(
                "entrada_anterior: 99.5-100.5\n"
                "entrada_ambiciosa_anterior: 90-91"
            ),
        )
        self.assertTrue(result.ok, result.errors)

    def test_rejects_reprioritizing_an_overlapping_same_support(self) -> None:
        result = validate_markdown(
            """
Valoración: 8.3 / 10
Entrada: $100-101
Motivo: Se reprioriza: la Entrada anterior de $99.50-100.50 sigue vigente, pero ajusto el mismo soporte a los datos nuevos.
Entrada ambiciosa: Sin zona verificable
""",
            authoritative_context="entrada_anterior: 99.5-100.5",
        )
        self.assertFalse(result.ok)
        self.assertTrue(
            any("reprioritized_overlapping_level: Entrada" in error for error in result.errors)
        )

    def test_reprioritization_must_quote_the_previous_prices(self) -> None:
        result = validate_markdown(
            """
Valoración: 8.3 / 10
Entrada: $109.50-110.50
Motivo: Se reprioriza: el soporte anterior sigue vigente, pero la nueva zona es materialmente mejor.
Entrada ambiciosa: Sin zona verificable
""",
            authoritative_context="entrada_anterior: 99.5-100.5",
        )
        self.assertFalse(result.ok)
        self.assertTrue(
            any("previous_level_mismatch: Entrada" in error for error in result.errors)
        )

    def test_first_resistance_can_state_that_no_previous_level_was_published(self) -> None:
        motives = (
            "no había una Resistencia estructural anterior publicada",
            "no hubo una Resistencia estructural publicada en el informe anterior",
            "no había rango anterior extraído",
            "la Resistencia estructural anterior no estaba extraída",
            "no se extrajo una Resistencia estructural anterior",
            "el informe anterior no extrajo una Resistencia estructural",
            "no existía rango publicado anteriormente",
        )
        for motive in motives:
            with self.subTest(motive=motive):
                result = validate_markdown(
                    f"""
Valoración: 8.1 / 10
Entrada: $1695-1705
Entrada ambiciosa: $1585-1600
Resistencia estructural: $2240-2260
Motivo: Se corrige: {motive}. El gap pendiente con borde superior en $2251.28 define la nueva zona.
""",
                    authoritative_context="resistencia_anterior: no extraída",
                )

                self.assertTrue(result.ok, result.errors)

    def test_missing_previous_resistance_still_rejects_an_invented_price(self) -> None:
        result = validate_markdown(
            """
Valoración: 8.1 / 10
Entrada: $1695-1705
Entrada ambiciosa: $1585-1600
Resistencia estructural: $2240-2260
Motivo: Se corrige: la Resistencia estructural anterior era $2100-2120 y ahora el gap define una zona mejor.
""",
            authoritative_context="resistencia_anterior: no extraída",
        )

        self.assertFalse(result.ok)
        self.assertTrue(
            any("invented_previous_level: Resistencia estructural" in error for error in result.errors)
        )


if __name__ == "__main__":
    unittest.main()
