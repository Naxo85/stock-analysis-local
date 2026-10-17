from __future__ import annotations

import argparse
import json
import tempfile
import unittest
from datetime import date, datetime, timezone
from pathlib import Path
from unittest import mock

from src.local_runner.analysis_policy import (
    LUNA_MODEL,
    SOL_MODEL,
    TERRA_MODEL,
    ReferenceSummary,
    TickerRecord,
    resolve_tier,
    route_ticker,
)
from src.local_runner.run_one import (
    _apply_daily_candidate_policy,
    _analysis_policy_prompt,
    _confidence_audit_selected,
    _daily_confidence_decision,
    _daily_escalation_reasons,
    _parse_args,
    _replace_report_score,
    _should_save_authoritative_reference,
)
from src.local_runner.run_batch import (
    _consume_one_shot_analysis_mode,
    _load_ticker_records,
)
from src.local_runner.previous_analysis import PreviousAnalysisContext


def _confidence_marker(**overrides):
    marker = {
        "material_change": False,
        "candidate_applies_material_change": False,
        "reasons": [],
        "urgent_risk": False,
        "reference_invalidation_confidence": 0,
        "replacement_confidence": 0,
        "evidence_quality": "none",
        "independent_support": False,
        "previous_conclusion": "",
        "invalidation_evidence": "",
        "proposed_replacement": "",
        "strongest_counterargument": "",
        "evidence_to_keep_reference": "",
    }
    marker.update(overrides)
    return marker


class AuthoritativePersistenceTests(unittest.TestCase):
    def test_persists_authoritative_web_daily_result(self) -> None:
        self.assertTrue(
            _should_save_authoritative_reference(
                execution_context="batch",
                analysis_kind="daily",
                payload={
                    "analysis_workflow": {
                        "web_sol_authoritative": True,
                        "status": "published_web_sol_authoritative",
                    }
                },
            )
        )

    def test_does_not_promote_fallback_daily_result(self) -> None:
        self.assertFalse(
            _should_save_authoritative_reference(
                execution_context="batch",
                analysis_kind="daily",
                payload={
                    "analysis_workflow": {
                        "web_sol_authoritative": False,
                        "status": "published_high_confidence_score_locked",
                    }
                },
            )
        )


class AnalysisPolicyTests(unittest.TestCase):
    def test_individual_run_is_sol_even_with_model_override(self) -> None:
        args = _parse_args(["RKLB", "--run-full", "--model", LUNA_MODEL])
        self.assertEqual(args.execution_context, "individual")
        self.assertEqual(args.analysis_kind, "reference")
        from src.local_runner.run_one import DEFAULT_CODEX_MODEL
        self.assertEqual(args.model, DEFAULT_CODEX_MODEL)

    def test_owned_routes_sol_reference_and_terra_daily(self) -> None:
        record = TickerRecord("RKLB", owned=True, ownership_source="trading:C")
        reference = ReferenceSummary(
            found=True,
            generated_at=datetime(2026, 8, 16, tzinfo=timezone.utc),
            score=4.0,
            tier="priority",
            model=SOL_MODEL,
        )
        sunday = route_ticker(record, reference, on_date=date(2026, 8, 16))
        monday = route_ticker(record, reference, on_date=date(2026, 8, 17))
        self.assertEqual(sunday.model, SOL_MODEL)
        self.assertEqual(sunday.analysis_kind, "reference")
        self.assertEqual(monday.model, TERRA_MODEL)
        self.assertEqual(monday.reviewer_model, SOL_MODEL)

    def test_tracking_routes_terra_reference_and_luna_daily(self) -> None:
        record = TickerRecord("APP")
        reference = ReferenceSummary(
            found=True,
            generated_at=datetime(2026, 8, 16, tzinfo=timezone.utc),
            score=4.0,
            tier="tracking",
            model=TERRA_MODEL,
        )
        sunday = route_ticker(record, reference, on_date=date(2026, 8, 16))
        monday = route_ticker(record, reference, on_date=date(2026, 8, 17))
        self.assertEqual(sunday.model, TERRA_MODEL)
        self.assertEqual(monday.model, LUNA_MODEL)
        self.assertEqual(monday.reviewer_model, TERRA_MODEL)

    def test_luna_prompt_preserves_low_confidence_conclusion(self) -> None:
        prompt = _analysis_policy_prompt(
            execution_context="batch",
            analysis_kind="daily",
            reference_tier="tracking",
            owned=False,
            reference_found=True,
            generation_model=LUNA_MODEL,
        )
        self.assertIn("Luna nunca confirma por sí sola un cambio", prompt)
        self.assertIn("candidate_applies_material_change=false", prompt)
        self.assertIn("actualiza\n  normalmente el resto del informe", prompt)

    def test_web_sol_prompt_does_not_request_escalation_metadata(self) -> None:
        prompt = _analysis_policy_prompt(
            execution_context="batch",
            analysis_kind="daily",
            reference_tier="priority",
            owned=True,
            reference_found=True,
            generation_model=SOL_MODEL,
            web_sol_authoritative=True,
        )

        self.assertIn("CHATGPT WEB SOL ALTO", prompt)
        self.assertIn("revisión de otro modelo", prompt)
        self.assertNotIn("ANALYSIS_ESCALATION", prompt)

    def test_hysteresis_and_owned_override(self) -> None:
        self.assertEqual(
            resolve_tier(owned=False, reference_score=6.7, previous_tier="priority"),
            "priority",
        )
        self.assertEqual(
            resolve_tier(owned=False, reference_score=6.7, previous_tier="tracking"),
            "tracking",
        )
        self.assertEqual(
            resolve_tier(owned=True, reference_score=2.0, previous_tier="tracking"),
            "priority",
        )

    def test_friday_and_saturday_skip(self) -> None:
        record = TickerRecord("RKLB", owned=True)
        reference = ReferenceSummary()
        self.assertEqual(
            route_ticker(record, reference, on_date=date(2026, 8, 14)).action,
            "skip",
        )
        self.assertEqual(
            route_ticker(record, reference, on_date=date(2026, 8, 15)).action,
            "skip",
        )

    def test_stale_reference_forces_reference_on_monday(self) -> None:
        record = TickerRecord("RKLB", owned=True)
        stale = ReferenceSummary(
            found=True,
            generated_at=datetime(2026, 8, 1, tzinfo=timezone.utc),
            score=8.0,
            tier="priority",
        )
        route = route_ticker(record, stale, on_date=date(2026, 8, 17))
        self.assertEqual(route.analysis_kind, "reference")
        self.assertEqual(route.model, SOL_MODEL)
        self.assertEqual(route.reason, "missing_or_stale_reference")

    def test_daily_score_is_replaced_with_official_score(self) -> None:
        markdown = "Valoración: 8.3 / 10\n\nEntrada: $1 - $2"
        locked = _replace_report_score(markdown, 7.1)
        self.assertIn("Valoración: 7.1 / 10", locked)

    def test_daily_score_lock_accepts_real_bold_and_decimal_variants(self) -> None:
        variants = (
            "**Valoración: 8.1 / 10**",
            "Valoración: **8.0 / 10**",
            "Valoración: **7,1 / 10**",
        )
        for markdown in variants:
            with self.subTest(markdown=markdown):
                locked = _replace_report_score(markdown, 6.4)
                self.assertIn("6.4 / 10", locked)

    def test_escalation_obeys_model_and_ignores_mechanical_alerts(self) -> None:
        payload = {
            "changes": {"score_delta": 1.0},
            "alerts": [
                {"type": "new_catalyst", "severity": "high"},
            ],
        }
        marker = _confidence_marker(
            material_change=True,
            candidate_applies_material_change=True,
            reasons=["thesis_narrative", "structural_technical"],
            reference_invalidation_confidence=75,
            replacement_confidence=80,
            evidence_quality="strong",
            independent_support=True,
            previous_conclusion="tesis anterior",
            invalidation_evidence="hecho nuevo verificable",
            proposed_replacement="tesis nueva",
            strongest_counterargument="puede ser transitorio",
            evidence_to_keep_reference="confirmación contraria",
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "candidate.md"
            path.write_text(
                "x\n<!-- ANALYSIS_ESCALATION " + json.dumps(marker) + " -->\n",
                encoding="utf-8",
            )
            reasons = _daily_escalation_reasons(payload, path)
        self.assertEqual(
            reasons,
            [
                "structural_technical",
                "thesis_narrative",
            ],
        )

        marker = _confidence_marker()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "candidate.md"
            path.write_text(
                "x\n<!-- ANALYSIS_ESCALATION " + json.dumps(marker) + " -->\n",
                encoding="utf-8",
            )
            reasons = _daily_escalation_reasons(payload, path)
        self.assertEqual(reasons, [])

    def test_confidence_bands_and_evidence_caps(self) -> None:
        base = _confidence_marker(
            material_change=True,
            candidate_applies_material_change=True,
            reasons=["thesis_narrative"],
            reference_invalidation_confidence=90,
            replacement_confidence=88,
            evidence_quality="strong",
            independent_support=True,
            previous_conclusion="tesis anterior",
            invalidation_evidence="evidencia nueva",
            proposed_replacement="tesis nueva",
            strongest_counterargument="explicación alternativa",
            evidence_to_keep_reference="dato contrario",
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "candidate.md"
            path.write_text(
                "x\n<!-- ANALYSIS_ESCALATION " + json.dumps(base) + " -->\n",
                encoding="utf-8",
            )
            decision = _daily_confidence_decision(path)
            self.assertEqual(decision["decision"], "direct_publish")
            self.assertEqual(decision["effective_confidence"], 88)

            base["independent_support"] = False
            path.write_text(
                "x\n<!-- ANALYSIS_ESCALATION " + json.dumps(base) + " -->\n",
                encoding="utf-8",
            )
            decision = _daily_confidence_decision(path)
            self.assertEqual(decision["decision"], "review")
            self.assertEqual(decision["effective_confidence"], 84)
            self.assertEqual(decision["confidence_cap_applied"], 84)

            base["evidence_quality"] = "none"
            path.write_text(
                "x\n<!-- ANALYSIS_ESCALATION " + json.dumps(base) + " -->\n",
                encoding="utf-8",
            )
            decision = _daily_confidence_decision(path)
            self.assertEqual(decision["decision"], "retain_reference")
            self.assertEqual(decision["effective_confidence"], 64)

    def test_urgent_material_change_always_requests_review(self) -> None:
        marker = _confidence_marker(
            material_change=True,
            candidate_applies_material_change=True,
            reasons=["high_impact_catalyst"],
            urgent_risk=True,
            reference_invalidation_confidence=30,
            replacement_confidence=25,
            evidence_quality="weak",
            independent_support=False,
            previous_conclusion="sin riesgo inmediato",
            invalidation_evidence="evento urgente",
            proposed_replacement="riesgo elevado",
            strongest_counterargument="impacto incierto",
            evidence_to_keep_reference="evento desmentido",
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "candidate.md"
            path.write_text(
                "x\n<!-- ANALYSIS_ESCALATION " + json.dumps(marker) + " -->\n",
                encoding="utf-8",
            )
            decision = _daily_confidence_decision(path)
        self.assertEqual(decision["decision"], "review")

    def test_confidence_audit_sampling_is_deterministic(self) -> None:
        first = _confidence_audit_selected(
            "RKLB", on_date="2026-08-17", rate=0.10
        )
        second = _confidence_audit_selected(
            "RKLB", on_date="2026-08-17", rate=0.10
        )
        self.assertEqual(first, second)
        self.assertFalse(
            _confidence_audit_selected("RKLB", on_date="2026-08-17", rate=0)
        )
        self.assertTrue(
            _confidence_audit_selected("RKLB", on_date="2026-08-17", rate=1)
        )

    def test_batch_reads_owned_metadata_and_keeps_legacy_tickers(self) -> None:
        args = argparse.Namespace(from_gcs=True, config_gcs=None, tickers=None)
        payload = {
            "tickers": ["RKLB", "APP"],
            "ticker_records": [
                {
                    "ticker": "RKLB",
                    "owned": True,
                    "ownership_source": "trading:C",
                },
                {"ticker": "APP", "owned": False},
            ],
        }
        with mock.patch(
            "src.local_runner.run_batch._read_gcs_text",
            return_value=json.dumps(payload),
        ):
            records, _ = _load_ticker_records(args)
        self.assertEqual([record.ticker for record in records], ["RKLB", "APP"])
        self.assertTrue(records[0].owned)
        self.assertEqual(records[0].ownership_source, "trading:C")

    def test_non_escalated_daily_candidate_publishes_with_locked_score(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            output = root / "output" / "RKLB"
            output.mkdir(parents=True)
            candidate = (
                "Valoración: 8.3 / 10\nEntrada: $1 - $2\n"
                "Entrada ambiciosa: $0.5 - $0.8\n"
                "<!-- ANALYSIS_ESCALATION "
                + json.dumps(_confidence_marker())
                + " -->\n"
            )
            (output / "latest.md").write_text(candidate, encoding="utf-8")
            (output / "latest.html").write_text("candidate", encoding="utf-8")
            (output / "latest.json").write_text(
                json.dumps(
                    {
                        "analysis_status": "ok",
                        "changes": {"score_delta": 0.2},
                        "alerts": [],
                    }
                ),
                encoding="utf-8",
            )
            reference = PreviousAnalysisContext(
                found=True,
                source_uri="state",
                analysis_markdown="Valoración: 7.1 / 10",
            )

            def fake_validate(*_args, **_kwargs):
                locked = (output / "latest.md").read_text(encoding="utf-8")
                (output / "latest.json").write_text(
                    json.dumps({"analysis_status": "ok", "analysis_markdown": locked}),
                    encoding="utf-8",
                )
                return 0

            with mock.patch(
                "src.local_runner.run_one.load_authoritative_reference_context",
                return_value=reference,
            ), mock.patch(
                "src.local_runner.run_one._validate", side_effect=fake_validate
            ):
                status = _apply_daily_candidate_policy(
                    repo_root=root,
                    symbol="RKLB",
                    generation_model=TERRA_MODEL,
                    reasoning_effort="medium",
                    reference_tier="priority",
                    owned=True,
                )

            self.assertEqual(status, 0)
            self.assertIn("Valoración: 8.3 / 10", (output / "candidate.md").read_text(encoding="utf-8"))
            published = (output / "latest.md").read_text(encoding="utf-8")
            self.assertIn("Valoración: 7.1 / 10", published)
            self.assertNotIn("ANALYSIS_ESCALATION", published)
            payload = json.loads((output / "latest.json").read_text(encoding="utf-8"))
            self.assertEqual(payload["analysis_workflow"]["proposed_score"], 8.3)
            self.assertEqual(payload["analysis_workflow"]["published_score"], 7.1)

    def test_low_confidence_material_change_retains_current_canonical(self) -> None:
        marker = _confidence_marker(
            material_change=True,
            candidate_applies_material_change=True,
            reasons=["thesis_narrative"],
            reference_invalidation_confidence=55,
            replacement_confidence=70,
            evidence_quality="weak",
            independent_support=False,
            previous_conclusion="tesis anterior",
            invalidation_evidence="señal todavía ambigua",
            proposed_replacement="tesis alternativa",
            strongest_counterargument="la referencia sigue explicando los datos",
            evidence_to_keep_reference="falta confirmación independiente",
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            output = root / "output" / "RKLB"
            output.mkdir(parents=True)
            (output / "latest.md").write_text(
                "Valoración: 8.3 / 10\n<!-- ANALYSIS_ESCALATION "
                + json.dumps(marker)
                + " -->\n",
                encoding="utf-8",
            )
            (output / "latest.json").write_text(
                json.dumps({"analysis_status": "ok"}), encoding="utf-8"
            )
            reference = PreviousAnalysisContext(
                found=True,
                source_uri="state",
                generated_at="2026-08-27T07:40:56+00:00",
                analysis_markdown="Valoración: 7.1 / 10",
            )

            def fake_validate(*_args, **_kwargs):
                markdown = (output / "latest.md").read_text(encoding="utf-8")
                (output / "latest.json").write_text(
                    json.dumps(
                        {
                            "analysis_status": "ok",
                            "analysis_markdown": markdown,
                            "generated_at": "2026-08-31T21:00:00+00:00",
                        }
                    ),
                    encoding="utf-8",
                )
                return 0

            with mock.patch(
                "src.local_runner.run_one.load_authoritative_reference_context",
                return_value=reference,
            ), mock.patch(
                "src.local_runner.run_one._validate", side_effect=fake_validate
            ) as validate:
                status = _apply_daily_candidate_policy(
                    repo_root=root,
                    symbol="RKLB",
                    generation_model=TERRA_MODEL,
                    reasoning_effort="medium",
                    reference_tier="priority",
                    owned=True,
                )

            self.assertEqual(status, 0)
            validate.assert_called_once()
            published = (output / "latest.md").read_text(encoding="utf-8")
            self.assertIn("Seguimiento actualizado", published)
            self.assertIn("Referencia oficial vigente", published)
            payload = json.loads((output / "latest.json").read_text(encoding="utf-8"))
            workflow = payload["analysis_workflow"]
            self.assertEqual(workflow["decision"], "retain_reference")
            self.assertEqual(
                workflow["status"], "reference_retained_low_confidence"
            )
            self.assertEqual(workflow["effective_confidence"], 55)
            self.assertEqual(workflow["sheet_warning"], "reference_retained")

    def test_strong_structural_change_reviews_from_sixty_percent(self) -> None:
        marker = _confidence_marker(
            material_change=True,
            candidate_applies_material_change=True,
            reasons=["structural_technical"],
            reference_invalidation_confidence=62,
            replacement_confidence=62,
            evidence_quality="strong",
            independent_support=False,
            previous_conclusion="estructura anterior",
            invalidation_evidence="ruptura verificable del escenario anterior",
            proposed_replacement="estructura nueva",
            strongest_counterargument="posible falsa ruptura",
            evidence_to_keep_reference="la tesis fundamental no ha cambiado",
        )
        with tempfile.TemporaryDirectory() as tmp:
            candidate = Path(tmp) / "candidate.md"
            candidate.write_text(
                "Valoración: 5.2 / 10\n<!-- ANALYSIS_ESCALATION "
                + json.dumps(marker)
                + " -->\n",
                encoding="utf-8",
            )
            decision = _daily_confidence_decision(candidate)

        self.assertEqual(decision["decision"], "review")
        self.assertTrue(decision["structural_review_threshold_applied"])

    def test_luna_low_confidence_publishes_reference_aligned_update(self) -> None:
        marker = _confidence_marker(
            material_change=True,
            candidate_applies_material_change=False,
            reasons=["thesis_narrative"],
            reference_invalidation_confidence=55,
            replacement_confidence=70,
            evidence_quality="weak",
            independent_support=False,
            previous_conclusion="tesis anterior",
            invalidation_evidence="señal todavía ambigua",
            proposed_replacement="tesis alternativa",
            strongest_counterargument="la referencia sigue explicando los datos",
            evidence_to_keep_reference="falta confirmación independiente",
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            output = root / "output" / "APP"
            output.mkdir(parents=True)
            (output / "latest.md").write_text(
                "Valoración: 4.0 / 10\nNarrativa actual: tesis anterior\n"
                "<!-- ANALYSIS_ESCALATION " + json.dumps(marker) + " -->\n",
                encoding="utf-8",
            )
            (output / "latest.json").write_text(
                json.dumps({"analysis_status": "ok"}), encoding="utf-8"
            )
            reference = PreviousAnalysisContext(
                found=True,
                source_uri="state",
                analysis_markdown="Valoración: 4.0 / 10",
            )

            def fake_validate(*_args, **_kwargs):
                markdown = (output / "latest.md").read_text(encoding="utf-8")
                (output / "latest.json").write_text(
                    json.dumps({"analysis_status": "ok", "analysis_markdown": markdown}),
                    encoding="utf-8",
                )
                return 0

            with mock.patch(
                "src.local_runner.run_one.load_authoritative_reference_context",
                return_value=reference,
            ), mock.patch(
                "src.local_runner.run_one._validate", side_effect=fake_validate
            ) as validate:
                _apply_daily_candidate_policy(
                    repo_root=root,
                    symbol="APP",
                    generation_model=LUNA_MODEL,
                    reasoning_effort="medium",
                    reference_tier="tracking",
                    owned=False,
                )

            validate.assert_called_once()
            published = (output / "latest.md").read_text(encoding="utf-8")
            self.assertIn("Narrativa actual: tesis anterior", published)
            self.assertNotIn("ANALYSIS_ESCALATION", published)
            payload = json.loads((output / "latest.json").read_text(encoding="utf-8"))
            workflow = payload["analysis_workflow"]
            self.assertEqual(workflow["decision"], "publish_reference_aligned")
            self.assertEqual(
                workflow["status"], "published_reference_aligned_low_confidence"
            )

    def test_luna_high_confidence_material_change_still_uses_terra(self) -> None:
        marker = _confidence_marker(
            material_change=True,
            candidate_applies_material_change=True,
            reasons=["structural_technical"],
            reference_invalidation_confidence=95,
            replacement_confidence=92,
            evidence_quality="strong",
            independent_support=True,
            previous_conclusion="estructura anterior",
            invalidation_evidence="ruptura confirmada",
            proposed_replacement="estructura nueva",
            strongest_counterargument="posible falsa ruptura",
            evidence_to_keep_reference="recuperación del nivel",
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            output = root / "output" / "APP"
            output.mkdir(parents=True)
            (output / "latest.md").write_text(
                "Valoración: 4.0 / 10\n<!-- ANALYSIS_ESCALATION "
                + json.dumps(marker)
                + " -->\n",
                encoding="utf-8",
            )
            (output / "latest.json").write_text(
                json.dumps({"analysis_status": "ok"}), encoding="utf-8"
            )
            reference = PreviousAnalysisContext(
                found=True,
                source_uri="state",
                analysis_markdown="Valoración: 4.0 / 10",
            )
            with mock.patch(
                "src.local_runner.run_one.load_authoritative_reference_context",
                return_value=reference,
            ), mock.patch(
                "src.local_runner.run_one._confidence_audit_selected"
            ) as audit, mock.patch("src.local_runner.run_one._validate") as validate:
                _apply_daily_candidate_policy(
                    repo_root=root,
                    symbol="APP",
                    generation_model=LUNA_MODEL,
                    reasoning_effort="medium",
                    reference_tier="tracking",
                    owned=False,
                )

            audit.assert_not_called()
            validate.assert_not_called()
            payload = json.loads((output / "latest.json").read_text(encoding="utf-8"))
            workflow = payload["analysis_workflow"]
            self.assertEqual(workflow["confidence_gate_decision"], "review")
            self.assertEqual(workflow["decision"], "review")
            self.assertEqual(workflow["status"], "escalation_required")

    def test_high_confidence_audit_is_sent_to_reviewer(self) -> None:
        marker = _confidence_marker(
            material_change=True,
            candidate_applies_material_change=True,
            reasons=["structural_technical"],
            reference_invalidation_confidence=92,
            replacement_confidence=90,
            evidence_quality="strong",
            independent_support=True,
            previous_conclusion="estructura anterior",
            invalidation_evidence="ruptura confirmada",
            proposed_replacement="estructura nueva",
            strongest_counterargument="posible falsa ruptura",
            evidence_to_keep_reference="recuperación del nivel invalidado",
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            output = root / "output" / "RKLB"
            output.mkdir(parents=True)
            (output / "latest.md").write_text(
                "Valoración: 8.3 / 10\n<!-- ANALYSIS_ESCALATION "
                + json.dumps(marker)
                + " -->\n",
                encoding="utf-8",
            )
            (output / "latest.json").write_text(
                json.dumps({"analysis_status": "ok"}), encoding="utf-8"
            )
            reference = PreviousAnalysisContext(
                found=True,
                source_uri="state",
                analysis_markdown="Valoración: 7.1 / 10",
            )
            with mock.patch(
                "src.local_runner.run_one.load_authoritative_reference_context",
                return_value=reference,
            ), mock.patch(
                "src.local_runner.run_one._confidence_audit_selected",
                return_value=True,
            ), mock.patch("src.local_runner.run_one._validate") as validate:
                _apply_daily_candidate_policy(
                    repo_root=root,
                    symbol="RKLB",
                    generation_model=TERRA_MODEL,
                    reasoning_effort="medium",
                    reference_tier="priority",
                    owned=True,
                )

            validate.assert_not_called()
            payload = json.loads((output / "latest.json").read_text(encoding="utf-8"))
            workflow = payload["analysis_workflow"]
            self.assertEqual(workflow["confidence_gate_decision"], "direct_publish")
            self.assertEqual(workflow["decision"], "confidence_audit")
            self.assertEqual(workflow["status"], "escalation_required")

    def test_web_sol_authority_skips_equivalent_confidence_audit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            output = root / "output" / "RKLB"
            output.mkdir(parents=True)
            (output / "latest.md").write_text(
                "Valoración: 8.3 / 10\n",
                encoding="utf-8",
            )
            (output / "latest.json").write_text(
                json.dumps(
                    {
                        "analysis_status": "ok",
                        "generation_provider": "chatgpt-browser",
                    }
                ),
                encoding="utf-8",
            )
            reference = PreviousAnalysisContext(
                found=True,
                source_uri="state",
                analysis_markdown="Valoración: 7.1 / 10",
            )

            def fake_validate(*_args, **_kwargs):
                markdown = (output / "latest.md").read_text(encoding="utf-8")
                (output / "latest.json").write_text(
                    json.dumps(
                        {
                            "analysis_status": "ok",
                            "analysis_markdown": markdown,
                            "generation_provider": "chatgpt-browser",
                        }
                    ),
                    encoding="utf-8",
                )
                return 0

            with mock.patch(
                "src.local_runner.run_one.load_authoritative_reference_context",
                return_value=reference,
            ), mock.patch(
                "src.local_runner.run_one._confidence_audit_selected",
                return_value=True,
            ) as audit, mock.patch(
                "src.local_runner.run_one._validate",
                side_effect=fake_validate,
            ):
                _apply_daily_candidate_policy(
                    repo_root=root,
                    symbol="RKLB",
                    generation_model=TERRA_MODEL,
                    reasoning_effort="medium",
                    reference_tier="priority",
                    owned=True,
                )

            audit.assert_not_called()
            payload = json.loads((output / "latest.json").read_text(encoding="utf-8"))
            workflow = payload["analysis_workflow"]
            self.assertEqual(workflow["decision"], "direct_publish")
            self.assertEqual(
                workflow["status"],
                "published_web_sol_authoritative",
            )
            self.assertTrue(workflow["web_sol_authoritative"])
            self.assertEqual(workflow["model_policy"], "web_sol_authoritative")
            self.assertEqual(workflow["candidate_model"], SOL_MODEL)
            self.assertIsNone(workflow["reference_invalidation_confidence"])
            self.assertEqual(workflow["proposed_score"], 8.3)
            self.assertEqual(workflow["published_score"], 8.3)
            self.assertFalse(workflow["official_score_locked"])
            self.assertIn(
                "Valoración: 8.3 / 10",
                (output / "latest.md").read_text(encoding="utf-8"),
            )

    def test_one_shot_mode_is_consumed_only_by_matching_profile(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            marker = root / ".local" / "analysis_mode_once.json"
            marker.parent.mkdir()
            marker.write_text(
                json.dumps(
                    {
                        "analysis_mode": "daily",
                        "expires_on": "2026-08-14",
                        "profile": "trading",
                    }
                ),
                encoding="utf-8",
            )
            self.assertIsNone(
                _consume_one_shot_analysis_mode(
                    root,
                    on_date=date(2026, 8, 14),
                    analysis_profile="core",
                )
            )
            self.assertTrue(marker.exists())
            self.assertEqual(
                _consume_one_shot_analysis_mode(
                    root,
                    on_date=date(2026, 8, 14),
                    analysis_profile="trading",
                ),
                "daily",
            )
            self.assertFalse(marker.exists())


if __name__ == "__main__":
    unittest.main()
