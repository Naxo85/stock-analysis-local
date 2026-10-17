"""The public plan is financial prose; complete source audit stays in typed JSON."""
from copy import deepcopy
import hashlib
from pathlib import Path
import unittest

import test_semantic_report as prior
from src.local_runner.adaptive_budget import read_json
from src.local_runner.adaptive_context import model_context
from src.local_runner.html_report import render_analysis_html
from src.local_runner.semantic_report import (
    LABELS, maintenance_document, full_document, render_document,
    reference_document, publication_fields, validation_result,
)

ROOT = Path(__file__).resolve().parents[1]


class PublicPresentationTests(unittest.TestCase):
    def documents(self):
        data = prior.data(); data['slim']['levels']['put_walls_top'] = [
            {'type': 'put_wall', 'level': 90, 'expiration': '2026-10-16', 'oi': 12345}]
        data['reference']['slim_snapshot'] = deepcopy(data['slim'])
        for full in (False, True):
            payload = prior.full(data) if full else prior.verdict(data)
            entry = payload['plan']['entry'] if full else payload['update']['plan']['entry']
            entry['facts'] = ['/slim/levels/put_walls_top/0/oi',
                              '/reference/slim_snapshot/levels/put_walls_top/0/oi']
            yield (full_document if full else maintenance_document)(payload, model_context(data)), data

    def test_both_models_keep_full_provenance_in_json_not_public_markdown_or_html(self):
        for doc, data in self.documents():
            before = deepcopy(doc); md = render_document(doc)
            html = render_analysis_html(md, symbol=data['symbol'])
            self.assertEqual(doc, before)
            for public in (md, html):
                for internal in ('Evidencia actual', 'Evidencia histórica', 'Antecedente del informe',
                                 '/slim/levels/', '/reference/slim_snapshot/', 'options_record', '12345'):
                    self.assertNotIn(internal, public)
            persisted = publication_fields(doc, md, data['reference'], prior.base.COMPLETED)
            self.assertEqual(persisted['semantic_report']['data'], before)
            self.assertEqual(persisted['semantic_report']['markdown_sha256'], hashlib.sha256(md.encode()).hexdigest())
            facts = persisted['semantic_report']['data']['plan']['entry']['resolved_facts']
            self.assertEqual(len(facts), 2)
            self.assertEqual([fact['historical'] for fact in facts], [False, True])
            self.assertTrue(all(fact['value'] == 12345 and fact['options_record']['oi'] == 12345 for fact in facts))

    def test_plan_fields_are_separate_human_blocks_in_real_html(self):
        for doc, data in self.documents():
            md = render_document(doc); html = render_analysis_html(md, symbol=data['symbol'])
            for label in LABELS.values():
                self.assertIn('### ' + label + '\n\n' + label + ': ', md)
                self.assertIn('<h3>' + label + '</h3>', html)
            self.assertIn('<p>Estado actual:', html)
            self.assertIn('<p>Motivo:', html)
            self.assertIn('<p>Fortaleza de Entrada:', html)
            self.assertIn('<p>Desglose de Entrada:', html)
            self.assertIn('<p>Factores de Entrada:', html)
            self.assertNotRegex(html, r'<p>Entrada: [^<]*Motivo:')

    def test_source_audit_cannot_change_presentation_but_remains_available(self):
        for doc, _ in self.documents():
            original = render_document(doc)
            changed = deepcopy(doc)
            for block in changed['plan'].values():
                block['resolved_facts'] = [{'source_kind': 'historical_report', 'value': 'INTERNAL_ONLY',
                    'pointer': '/reference/plan/structural_stop', 'as_of': '2026-10-01',
                    'historical': True, 'options_record': {'very_large_internal_record': 'INTERNAL_ONLY'}}] * 100
            self.assertEqual(render_document(changed), original)
            self.assertEqual(len(changed['plan']['entry']['resolved_facts']), 100)

    def test_numerical_mirrors_scores_reasons_and_validation_are_unchanged(self):
        for doc, data in self.documents():
            before = deepcopy(doc); result = validation_result(doc)
            fields = publication_fields(doc, render_document(doc), data['reference'], prior.base.COMPLETED)
            self.assertTrue(result.ok)
            for key, level in before['plan'].items():
                zone = level['range']
                expected = zone['lower'] if zone and key in ('management_stop', 'structural_stop', 'target') else zone
                self.assertEqual(fields['plan'][key], expected)
                self.assertEqual(fields['plan'][key + '_reason'], level['reason'])
            self.assertEqual(fields['decision']['thesis_score'], before['summary']['thesis_score'])
            self.assertEqual(fields['decision']['setup_score'], before['summary']['setup_score'])

    def test_original_INTC_re_render_cleans_plan_without_rewriting_its_artifacts(self):
        work = ROOT/'logs/batch/2026-10-07/09-12-17/adaptive/INTC/publish/output/INTC'
        if not work.exists(): self.skipTest('Original incident artifacts absent')
        files = [work/name for name in ('latest.json', 'latest.md', 'latest.html')]
        before = {file: file.read_bytes() for file in files}
        payload = read_json(work/'latest.json')
        doc = reference_document(payload, verify_projection=True); original = deepcopy(doc)
        md = render_document(doc); html = render_analysis_html(md, symbol='INTC')
        old_plan = payload['analysis_markdown'].split('## 3) Plan', 1)[1].split('## 4)', 1)[0]
        plan = md.split('## 3) Plan', 1)[1].split('## 4)', 1)[0]
        self.assertIn('Evidencia actual', old_plan)
        self.assertNotIn('Evidencia actual', plan)
        self.assertNotIn('/slim/', plan)
        self.assertLess(len(plan), len(old_plan) / 2)
        self.assertEqual(html.count('<h3>'), 6)
        self.assertEqual(doc, original)
        self.assertEqual({file: file.read_bytes() for file in files}, before)


if __name__ == '__main__': unittest.main()
