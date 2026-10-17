"""Reader-only CAT refresh and revision17 presentation, no models/network."""
from copy import deepcopy
import json
from pathlib import Path
import unittest
from scripts.refresh_report_presentation import editorial_document
from src.local_runner.semantic_report import render_document, _reader_prose, reference_document
from src.local_runner.html_report import render_analysis_html
from src.local_runner.adaptive_policy import load_policy

ROOT = Path(__file__).resolve().parent


class ReaderTests(unittest.TestCase):
    def original(self):
        path = ROOT / 'logs/batch/2026-10-07/21-27-11/adaptive/CAT/publish/output/CAT/latest.json'
        if not path.exists(): self.skipTest('Optional immutable CAT fixture absent')
        return json.loads(path.read_text(encoding='utf8'))

    def overlay(self):
        return json.loads((ROOT / 'config/report_presentation_CAT_20261007.json').read_text(encoding='utf8'))

    def test_editorial_preserves_financial_numbers_dates_and_original(self):
        payload = self.original(); before = deepcopy(payload)
        old = reference_document(payload, verify_projection=True)
        doc = editorial_document(payload, self.overlay())
        self.assertEqual(doc['metadata'], old['metadata'])
        for field in ('thesis_score', 'setup_score'):
            self.assertEqual(doc['summary'][field], old['summary'][field])
        for key in old['plan']:
            for field in ('range', 'strength', 'resolved_facts'):
                self.assertEqual(doc['plan'][key].get(field), old['plan'][key].get(field))
        for new, original in zip(doc['catalysts'], old['catalysts']):
            self.assertEqual({k:v for k,v in new.items() if k != 'description'},
                             {k:v for k,v in original.items() if k != 'description'})
        self.assertEqual(payload, before)
        md = render_document(doc, reader=True)
        self.assertLess(len(md), len(payload['analysis_markdown']) * .5)
        for noise in ('adv20', 'Desglose de', 'Factores de', 'Corrijo'):
            self.assertNotIn(noise, md)
        for warning in ('0,84:1', 'no sirve para entrar aquí', 'información incompleta'):
            self.assertIn(warning, md)
        html = render_analysis_html(md, symbol='CAT')
        self.assertIn('>Resultados de Caterpillar</a>', html)
        self.assertNotIn('[Resultados', html)

    def test_overlay_cannot_change_scores_prices_dates_or_other_report(self):
        payload = self.original(); overlay = self.overlay()
        for field in ('/summary/thesis_score', '/plan/entry/range', '/metadata/analysis_date'):
            bad = deepcopy(overlay); bad['text'][field] = 'different'
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, 'not_a_text_field'):
                editorial_document(payload, bad)
        overlay['source_markdown_sha256'] = 'different'
        with self.assertRaisesRegex(ValueError, 'source_changed'): editorial_document(payload, overlay)

    def test_links_named_once_and_unsafe_markup_inert(self):
        prose = _reader_prose('Ver [Fuente](https://example.test/a_b.pdf). <script>alert(1)</script>')
        self.assertEqual(prose.count('https://example.test/a_b.pdf'), 1)
        html = render_analysis_html(prose, symbol='CAT')
        self.assertIn('href="https://example.test/a_b.pdf"', html)
        self.assertNotIn('<script>', html)
        bad = render_analysis_html(_reader_prose('[X](javascript:alert(1))'), symbol='CAT')
        self.assertNotIn('href="javascript:', bad)

    def test_reader17_does_not_change_legacy_render(self):
        payload = self.original(); doc = reference_document(payload, verify_projection=True)
        self.assertEqual(render_document(doc), payload['analysis_markdown'])
        doc['metadata']['source_contract_revision'] = 17
        readable = render_document(doc)
        self.assertNotIn('Cotización congelada', readable)
        self.assertNotIn('Desglose de', readable)
        self.assertIn('Fortaleza de Entrada: 61/100', readable)
        self.assertEqual(load_policy(ROOT)['routing_revision'], 23)


if __name__ == '__main__': unittest.main()
