"""Presentation must not reject valid scores; no paid calls or publications."""
from itertools import permutations
from pathlib import Path
import unittest
from src.common import analysis_validator as validator

ROOT = Path(__file__).resolve().parents[1]
COMPONENTS = ("estructura 19/25", "volumen 15/20", "opciones 18/25", "confluencia 12/15", "durabilidad 10/15")
CLS_FACTORS = (
    "HVN aproximado **$359.3128**, a **0.51%** del centro; en $355, "
    "**12 defensas/23 tests**, tasa **52.2%**, mediana **6.76%** frente al "
    "mínimo **2.76%**, último test **30-Sep**; volumen **3+5+2+3+3=16**, "
    "limitado a **15** por tasa inferior al 60%; puts **$355 y $360 del 09-Oct**, "
    "gamma **23.3% y 13.4%**, OI **1,048 y 519**. Fortaleza **79→74**: "
    "el $360 antes correspondía al **16-Oct**; ahora ambos walls destacados "
    "vencen el **09-Oct**, reduciendo persistencia y durabilidad."
)

def markdown(factors=CLS_FACTORS, label="Entrada ambiciosa", separator="; ", strength="74/100 · sólido"):
    return (f"Fortaleza de {label}: **{strength}**\n"
            f"Desglose de {label}: {separator.join(COMPONENTS)}\n"
            f"Factores de {label}: {factors}\n")

class StrengthFormatToleranceTests(unittest.TestCase):
    def test_exact_cls_evidence_preserved(self):
        result = validator.extract_support_strength(markdown(), "Entrada ambiciosa")
        self.assertIsNotNone(result)
        self.assertEqual(result.score, 74)
        self.assertEqual(result.factors, validator._clean_line(CLS_FACTORS))

    def test_no_hard_factor_count_or_separator_for_any_level(self):
        evidence = ["HVN $359", "12 defensas/23 tests", "volumen limitado a 15", "puts $355 y $360", "SMA200 $350", "AVWAP $355"]
        for label in ("Entrada", "Entrada ambiciosa", "Resistencia"):
            for count in (1, 2, 3, 4, 5, 6):
                for separator in ("; ", ", ", ". ", " · ", " y "):
                    with self.subTest(label=label, count=count, separator=separator):
                        factors = separator.join(evidence[:count]) + "; explicación histórica; limitaciones."
                        result = validator.extract_support_strength(markdown(factors, label), label)
                        self.assertIsNotNone(result)
                        self.assertEqual(result.factors, factors)

    def test_missing_evidence_still_fails(self):
        for factors in ("", " ", "... ; ;"):
            self.assertIsNone(validator.extract_support_strength(markdown(factors), "Entrada ambiciosa"))

    def test_component_order_and_punctuation_do_not_matter(self):
        expected = dict(estructura=19, volumen=15, opciones=18, confluencia=12, durabilidad=10)
        for components in permutations(COMPONENTS):
            for separator in ("; ", ", ", " · ", " | ", " — ", ". ", " "):
                self.assertEqual(validator._parse_strength_breakdown(separator.join(components) + "."), expected)
        self.assertEqual(validator._parse_strength_breakdown("; ".join(c.replace(" ", ": ", 1) for c in COMPONENTS)), expected)

    def test_score_presentation_tolerated(self):
        for value in ("74/100 · sólido.", "74/100: sólido", "74/100, sólido", "74/100 sólido", "74/100 — SÓLIDO!"):
            self.assertIsNotNone(validator.extract_support_strength(markdown(strength=value), "Entrada ambiciosa"))
        self.assertEqual(validator.extract_dimension_score("Tesis: 7.2 / 10.\n", "Tesis"), 7.2)

    def test_real_score_errors_still_fail(self):
        md = markdown()
        for bad in (md.replace("74/100", "75/100"), md.replace("sólido", "fuerte"),
                    md.replace("19/25", "26/25"), md.replace("10/15", "10/20"),
                    md.replace("15/20", "14/20"), md.replace("estructura 19/25; ", ""),
                    md.replace("estructura 19/25", "estructura 19/25; estructura 19/25")):
            self.assertIsNone(validator.extract_support_strength(bad, "Entrada ambiciosa"))

    def test_unavailable_zone_punctuation_is_cosmetic_not_a_new_absence(self):
        for punctuation in ("", ".", "..", ";", "!"):
            md = ("Valoración: 7 / 10\nEntrada: $59.70 - $60.20\n" + markdown(label="Entrada")
                  + f"Entrada ambiciosa: Sin zona verificable{punctuation}\n"
                  + f"Fortaleza de Entrada ambiciosa: No aplicable{punctuation}\n"
                  + f"Desglose de Entrada ambiciosa: No aplicable{punctuation}\n"
                  + "Factores de Entrada ambiciosa: No existe zona inferior defendible.\n")
            self.assertTrue(validator.validate_markdown(md, require_support_strengths=True).ok)
            # A real zone must not be hidden by saying its strength is N/A.
            bad = md.replace(f"Sin zona verificable{punctuation}", "$55 - $55.50")
            self.assertFalse(validator.validate_markdown(bad, require_support_strengths=True).ok)

    def test_no_extra_numeric_or_unknown_components(self):
        baseline = "; ".join(COMPONENTS)
        for value in (baseline + " 12/15.", baseline + "; otro 1/10", baseline + "; durabilidad 10/15",
                      baseline.replace("19/25", "19.5/25"), baseline.replace("19/25", "-19/25"),
                      baseline.replace("19/25", "19/25 inventado")):
            self.assertIsNone(validator._parse_strength_breakdown(value), value)

    def test_original_latest_sol_reports_full_validation_read_only(self):
        from src.local_runner.adaptive_context import validation_context
        from src.local_runner.adaptive_budget import read_json
        from src.local_runner.report_dates import normalize_report_dates
        work = ROOT / "logs/batch/2026-10-05/12-38-33/adaptive"
        if not work.exists():
            self.skipTest("local natural-batch artifacts unavailable")
        reports = sorted(work.glob("*/report.response"))
        self.assertTrue(any(path.parent.name == "CLS" for path in reports))
        for path in reports:
            with self.subTest(ticker=path.parent.name):
                original = path.read_bytes()
                result = validator.validate_markdown(normalize_report_dates(original.decode("utf-8")),
                    authoritative_context=validation_context(read_json(path.parent / "input.json")),
                    require_support_strengths=True, require_resistance=True, require_separate_scores=True)
                self.assertTrue(result.ok, result.errors)
                self.assertEqual(original, path.read_bytes())

    def test_original_inod_update_full_validation_read_only(self):
        from src.local_runner.adaptive_context import model_context, validation_context
        from src.local_runner.adaptive_budget import read_json
        from src.local_runner.adaptive_maintenance import apply_update
        from src.local_runner.report_dates import normalize_report_dates
        work = ROOT / "logs/batch/2026-10-05/12-38-33/adaptive/INOD"
        if not work.exists():
            self.skipTest("local INOD artifacts unavailable")
        response_path, context_path = work / "triage.response", work / "input.json"
        original_response, original_context = response_path.read_bytes(), context_path.read_bytes()
        context = read_json(context_path)
        candidate = apply_update(read_json(response_path), model_context(context))
        result = validator.validate_markdown(normalize_report_dates(candidate),
            authoritative_context=validation_context(context), require_support_strengths=True,
            require_resistance=True, require_separate_scores=True)
        self.assertTrue(result.ok, result.errors)
        self.assertEqual(original_response, response_path.read_bytes())
        self.assertEqual(original_context, context_path.read_bytes())

if __name__ == "__main__":
    unittest.main()
