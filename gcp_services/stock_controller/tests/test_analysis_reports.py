from __future__ import annotations

import unittest

from stock_analysis.analysis_worker.reports import parse_analysis_report


def report_payload() -> dict:
    return {
        "symbol": "RKLB",
        "generated_at": "2026-09-05T12:00:00Z",
        "analysis_status": "ok",
        "validation": {"ok": True},
        "decision": {"score": 8.2},
        "plan": {
            "entry": {"lower": 100.0, "upper": 102.0},
            "ambitious_entry": {"lower": 80.0, "upper": 82.0},
            "management_stop": 101.0,
            "structural_stop": 75.0,
            "target": 120.0,
        },
        "changes": {"previous_score": 7.4},
    }


class AnalysisReportTest(unittest.TestCase):
    def test_explicit_absent_main_entry_is_supported_only_by_new_contract(self):
        from copy import deepcopy
        payload = report_payload()
        payload['report_schema_version'] = 5
        for key, level in (('entry', 'entry'), ('ambitious_entry', 'washout')):
            payload['plan'][key] = None
            payload['plan'].update({f'{level}_strength_score': None,
                f'{level}_strength_category': 'no_aplica',
                f'{level}_strength_factors': 'Sin soporte defendible.',
                f'{level}_strength_breakdown': None})
        payload['semantic_report'] = {'data': {
            'metadata': {'source_contract_revision': 22},
            'plan': {'entry': {'range': None, 'strength': None,
                              'reason': 'Sin soporte defendible.'}}}}
        record = parse_analysis_report('RKLB', payload, report_url_template='{ticker}')
        self.assertIsNone(record.entry)
        self.assertIsNone(record.entry_stop)
        self.assertIsNone(record.entry_strength)
        self.assertIsNone(record.washout)
        for defect in ('old_revision', 'missing_range', 'missing_reason', 'missing_semantic', 'bad_projection'):
            bad = deepcopy(payload)
            if defect == 'old_revision': bad['semantic_report']['data']['metadata']['source_contract_revision'] = 21
            elif defect == 'missing_range': del bad['semantic_report']['data']['plan']['entry']['range']
            elif defect == 'missing_reason': bad['semantic_report']['data']['plan']['entry']['reason'] = ''
            elif defect == 'missing_semantic': del bad['semantic_report']
            else: bad['plan']['entry'] = {'lower': -1, 'upper': 0}
            with self.subTest(defect=defect), self.assertRaises(ValueError):
                parse_analysis_report('RKLB', bad, report_url_template='{ticker}')

    def test_uses_only_structured_valid_report_fields(self):
        record = parse_analysis_report(
            "RKLB",
            report_payload(),
            report_url_template="https://reports.example/?symbol={ticker}",
        )

        self.assertEqual((record.entry.lower, record.entry.upper), (100.0, 102.0))
        self.assertEqual((record.washout.lower, record.washout.upper), (80.0, 82.0))
        self.assertEqual(record.entry_stop, 75.0)
        self.assertEqual(record.washout_stop, 75.0)
        self.assertIsNone(record.resistance)
        self.assertIsNone(record.entry_strength)
        self.assertIsNone(record.washout_strength)
        self.assertIsNone(record.resistance_strength)
        self.assertEqual(record.score_background, "#D9EAD3")
        self.assertIn("7,4", record.score_note)
        self.assertIn("+0,8", record.score_note)

    def test_reads_strength_only_when_the_report_explicitly_provides_it(self):
        payload = report_payload()
        payload["report_schema_version"] = 5
        payload["plan"].update(
            {
                "entry_strength_score": 86,
                "entry_strength_category": "fuerte",
                "entry_strength_factors": "EMA20; HVN; put wall mensual",
                "entry_strength_breakdown": {
                    "estructura": 22,
                    "volumen": 17,
                    "opciones": 21,
                    "confluencia": 13,
                    "durabilidad": 13,
                },
                "washout_strength_score": 96,
                "washout_strength_category": "excepcional",
                "washout_strength_factors": "SMA200; mínimo histórico",
                "washout_strength_breakdown": {
                    "estructura": 24,
                    "volumen": 19,
                    "opciones": 25,
                    "confluencia": 14,
                    "durabilidad": 14,
                },
            }
        )

        record = parse_analysis_report(
            "RKLB",
            payload,
            report_url_template="https://reports.example/?symbol={ticker}",
        )

        self.assertEqual(record.entry_strength, 86)
        self.assertEqual(record.washout_strength, 96)
        self.assertEqual(record.entry_strength_category, "fuerte")
        self.assertIn("put wall", record.entry_strength_factors)

    def test_normalizes_derived_strength_category_from_score(self):
        payload = report_payload()
        payload["report_schema_version"] = 3
        payload["plan"].update(
            {
                "entry_strength_score": 86,
                "entry_strength_category": "sólido",
                "entry_strength_factors": "EMA20; HVN",
                "washout_strength_score": 68,
                "washout_strength_category": "moderado",
                "washout_strength_factors": "SMA200; mínimo histórico",
            }
        )

        record = parse_analysis_report(
            "RKLB",
            payload,
            report_url_template="https://reports.example/?symbol={ticker}",
        )
        self.assertEqual(record.entry_strength_category, "fuerte")
        self.assertEqual(record.washout_strength, 68)
        self.assertEqual(record.washout_strength_category, "moderado")

    def test_schema_six_requires_and_reads_structural_resistance_strength(self):
        payload = report_payload()
        payload["report_schema_version"] = 6
        payload["plan"].update(
            {
                "entry_strength_score": 86,
                "entry_strength_category": "fuerte",
                "entry_strength_factors": "EMA20; HVN; put wall mensual",
                "entry_strength_breakdown": {
                    "estructura": 22,
                    "volumen": 17,
                    "opciones": 21,
                    "confluencia": 13,
                    "durabilidad": 13,
                },
                "washout_strength_score": 72,
                "washout_strength_category": "sólido",
                "washout_strength_factors": "SMA200; mínimo previo",
                "washout_strength_breakdown": {
                    "estructura": 18,
                    "volumen": 14,
                    "opciones": 17,
                    "confluencia": 11,
                    "durabilidad": 12,
                },
                "resistance": {"lower": 120.0, "upper": 122.0},
                "resistance_strength_score": 88,
                "resistance_strength_category": "fuerte",
                "resistance_strength_factors": (
                    "máximo semanal; rechazos con volumen; call wall mensual"
                ),
                "resistance_strength_breakdown": {
                    "estructura": 22,
                    "volumen": 17,
                    "opciones": 22,
                    "confluencia": 14,
                    "durabilidad": 13,
                },
            }
        )

        record = parse_analysis_report(
            "RKLB",
            payload,
            report_url_template="https://reports.example/?symbol={ticker}",
        )

        self.assertEqual(
            (record.resistance.lower, record.resistance.upper),
            (120.0, 122.0),
        )
        self.assertEqual(record.resistance_strength, 88)
        self.assertEqual(record.resistance_strength_category, "fuerte")
        self.assertEqual(record.resistance_strength_breakdown["opciones"], 22)

    def test_rejects_schema_four_breakdown_that_does_not_sum_to_score(self):
        payload = report_payload()
        payload["report_schema_version"] = 4
        payload["plan"].update(
            {
                "entry_strength_score": 86,
                "entry_strength_category": "fuerte",
                "entry_strength_factors": "EMA20; HVN",
                "entry_strength_breakdown": {
                    "estructura": 20,
                    "volumen": 15,
                    "opciones": 20,
                    "confluencia": 10,
                    "durabilidad": 10,
                },
            }
        )

        with self.assertRaisesRegex(ValueError, "invalid entry strength"):
            parse_analysis_report(
                "RKLB",
                payload,
                report_url_template="https://reports.example/?symbol={ticker}",
            )

    def test_rejects_schema_five_solid_without_minimum_structure(self):
        payload = report_payload()
        payload["report_schema_version"] = 5
        payload["plan"].update(
            {
                "entry_strength_score": 70,
                "entry_strength_category": "sólido",
                "entry_strength_factors": "HVN; put wall; rango poco definido",
                "entry_strength_breakdown": {
                    "estructura": 12,
                    "volumen": 14,
                    "opciones": 18,
                    "confluencia": 13,
                    "durabilidad": 13,
                },
            }
        )

        with self.assertRaisesRegex(ValueError, "invalid entry strength"):
            parse_analysis_report(
                "RKLB",
                payload,
                report_url_template="https://reports.example/?symbol={ticker}",
            )

    def test_visible_sheet_score_overrides_intermediate_report_history(self):
        payload = report_payload()
        payload["decision"]["score"] = 6.1
        payload["changes"]["previous_score"] = 6.1

        record = parse_analysis_report(
            "RKLB",
            payload,
            report_url_template="https://reports.example/?symbol={ticker}",
            previous_score_override=5.4,
        )

        self.assertEqual(record.score_background, "#D9EAD3")
        self.assertIn("5,4", record.score_note)
        self.assertIn("+0,7", record.score_note)

    def test_exactly_half_a_point_triggers_visual_alert(self):
        payload = report_payload()
        payload["decision"]["score"] = 7.9

        record = parse_analysis_report(
            "RKLB",
            payload,
            report_url_template="https://reports.example/?symbol={ticker}",
            previous_score_override=7.4,
        )

        self.assertEqual(record.score_background, "#D9EAD3")
        self.assertIn("+0,5", record.score_note)

    def test_repairs_legacy_thousands_separator_scale(self):
        payload = report_payload()
        payload["latest_price"] = 1676.02
        payload["decision"]["reference_price"] = 1676.02
        payload["plan"].update(
            {
                "entry": {"lower": 1.45, "upper": 1.46},
                "ambitious_entry": {"lower": 1.355, "upper": 1.365},
                "management_stop": 1.49,
                "structural_stop": 990.0,
                "target": 1.7,
                "resistance": {"lower": 1.7, "upper": 1.72},
            }
        )

        record = parse_analysis_report(
            "RKLB",
            payload,
            report_url_template="https://reports.example/?symbol={ticker}",
        )

        self.assertEqual((record.entry.lower, record.entry.upper), (1450.0, 1460.0))
        self.assertEqual(
            (record.washout.lower, record.washout.upper),
            (1355.0, 1365.0),
        )
        self.assertEqual(
            (record.resistance.lower, record.resistance.upper),
            (1700.0, 1720.0),
        )

    def test_rejects_failed_or_invalid_analysis(self):
        for status, validation_ok in (("failed", True), ("ok", False)):
            payload = report_payload()
            payload["analysis_status"] = status
            payload["validation"]["ok"] = validation_ok
            with self.assertRaises(ValueError):
                parse_analysis_report(
                    "RKLB",
                    payload,
                    report_url_template="https://reports.example/?symbol={ticker}",
                )


if __name__ == "__main__":
    unittest.main()
