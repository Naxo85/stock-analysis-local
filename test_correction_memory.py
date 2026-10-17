from copy import deepcopy
from datetime import datetime
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from src.local_runner import adaptive_stage as stage
from src.local_runner.correct_volume_arithmetic import build
from src.local_runner.repair_correction_memory import reconstruct, repair
from src.local_runner.review_memory import read_memory, rebind_memory
from src.local_runner.adaptive_context import model_context, serialize_model_input

ROOT = Path(__file__).resolve().parent
CORRECTION = ROOT / 'logs/corrections/20261009T110021146213/AUR'
BATCH = ROOT / 'logs/batch/2026-10-09/15-39-36/adaptive'


class CorrectionMemoryTests(unittest.TestCase):
    def setUp(self):
        self.symbol, self.bad, self.good, self.anchor = reconstruct(CORRECTION)
        self.context = stage.read_json(CORRECTION / 'input.json')
        self.previous = stage.read_json(ROOT / 'logs/batch/2026-10-09/10-10-37/adaptive/AUR/publish/output/AUR/latest.json')

    def test_original_defect_and_next_cycle_with_no_financial_or_date_changes(self):
        with self.assertRaisesRegex(ValueError, 'invalid_published_review_memory'):
            read_memory(self.bad, self.anchor)
        expected = deepcopy(self.bad)
        expected['review_memory'] = rebind_memory(self.previous, expected, self.anchor)
        self.assertEqual(self.good, expected)
        self.assertEqual(read_memory(self.good, self.anchor), read_memory(self.previous, self.anchor))
        frozen = stage.read_json(BATCH / 'AUR/input.json')
        frozen['reference'] = self.good
        with patch.object(stage, 'call_codex', side_effect=AssertionError('NO MODEL')):
            self.assertTrue(serialize_model_input(model_context(frozen)))

    def test_future_builder_produces_readable_next_cycle(self):
        original = deepcopy((self.previous, self.anchor, self.context))
        payload, review, md = build(self.previous, self.anchor, self.context, 's13',
                                   datetime.fromisoformat(self.bad['generated_at']))
        self.assertEqual(payload, self.good)
        self.assertEqual((self.previous, self.anchor, self.context), original)
        self.assertEqual(review['model_calls'], [])
        self.assertEqual(payload['review_memory']['data'], self.previous['review_memory']['data'])

    def test_rebinding_rejects_invalid_old_memory_or_changed_anchor(self):
        for change in ('binding', 'data', 'anchor'):
            prior, anchor = deepcopy(self.previous), deepcopy(self.anchor)
            if change == 'binding': prior['review_memory']['report_key'] = 'bad'
            if change == 'data': prior['review_memory']['data']['articles']['invented'] = {}
            if change == 'anchor': anchor['generated_at'] = '2099-01-01'
            with self.subTest(change=change), self.assertRaises(ValueError):
                rebind_memory(prior, self.good, anchor)

    def test_publication_rejects_stale_memory_before_any_write(self):
        for candidate, message in ((self.bad, 'invalid_published_review_memory'),
                                   (self.good, 'REACHED_VALID_UPLOAD')):
            with self.subTest(valid=candidate == self.good), tempfile.TemporaryDirectory() as d:
                root = Path(d); work = root / 'stage'
                review = deepcopy(candidate['daily_review']); review.pop('published_at', None)
                stage.write_json(work / 'review.json', review)
                stage.write_json(work / 'publish/output/AUR/latest.json', candidate)
                with patch.object(stage, '_read_json_gcs', side_effect=[self.previous, self.anchor]), \
                     patch.object(stage.one, '_upload', side_effect=RuntimeError('REACHED_VALID_UPLOAD')) as upload, \
                     patch.object(stage, '_copy_json') as copy, \
                     self.assertRaisesRegex((RuntimeError, ValueError), message):
                    stage._publish_locked(root, work, 'AUR')
                self.assertEqual(upload.call_count, int(candidate == self.good))
                copy.assert_not_called()

    def test_all_other_published_reports_remain_readable(self):
        count = 0
        for path in BATCH.glob('*/publish/output/*/latest.json'):
            payload = stage.read_json(path)
            context = stage.read_json(BATCH / payload['symbol'] / 'input.json')
            review = payload['daily_review']
            anchor = payload if review['status'] == 'regenerated' else context['sol_reference']
            before = deepcopy(payload)
            read_memory(payload, anchor)
            self.assertEqual(payload, before)
            count += 1
        self.assertEqual(count, 45)

    def remote_fixture(self):
        state = deepcopy(self.bad)
        state.update(sol_anchor_sha256=stage.reference_key(self.anchor), last_full_report_at=self.anchor['generated_at'])
        return {f'gs://{stage.TEST_BUCKET}/AUR/latest.json': deepcopy(self.bad),
                f'gs://{stage.SHEET_REPORT_MIRROR_BUCKET}/{stage.SHEET_REPORT_MIRROR_PREFIX}/AUR.json': deepcopy(self.bad),
                stage.current_uri('AUR'): state,
                f'gs://{stage.TEST_BUCKET}/_analysis_state/AUR/reference.json': deepcopy(self.anchor)}

    def test_repair_roundtrip_all_copies_and_idempotence(self):
        remote = self.remote_fixture()
        remote[f'gs://{stage.TEST_BUCKET}/AUR/latest.json']['analyst_ratings_summary']['as_of'] = '2026-10-09T15:48:55.622591+00:00'
        before = deepcopy(remote)
        def copy(path, uri): remote[uri] = stage.read_json(path)
        with tempfile.TemporaryDirectory() as d, \
             patch.object(stage, '_read_json_gcs', side_effect=lambda uri: deepcopy(remote[uri])), \
             patch.object(stage, '_copy_json', side_effect=copy), \
             patch.object(stage, 'call_codex', side_effect=AssertionError('NO MODEL')):
            root = Path(d); (root / 'output/AUR').mkdir(parents=True)
            for _ in range(2):
                _, audit = repair(root, CORRECTION, execute=True)
                self.assertEqual(audit['status'], 'repaired')
            for uri, payload in remote.items():
                expected = deepcopy(before[uri])
                if not uri.endswith('/reference.json'):
                    expected['review_memory'] = self.good['review_memory']
                    read_memory(payload, self.anchor)
                self.assertEqual(payload, expected)

    def test_repair_rejects_changed_report_memory_or_anchor_without_writes(self):
        for mutation in ('report', 'memory', 'anchor'):
            remote = self.remote_fixture()
            uri = f'gs://{stage.TEST_BUCKET}/AUR/latest.json'
            if mutation == 'report': remote[uri]['generated_at'] = '2099-01-01'
            if mutation == 'memory': remote[uri]['review_memory']['data']['articles']['fake'] = {}
            if mutation == 'anchor': remote[f'gs://{stage.TEST_BUCKET}/_analysis_state/AUR/reference.json']['generated_at'] = '2099-01-01'
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as d, \
                 patch.object(stage, '_read_json_gcs', side_effect=lambda uri: deepcopy(remote[uri])), \
                 patch.object(stage, '_copy_json') as copy:
                root = Path(d); (root / 'output/AUR').mkdir(parents=True)
                with self.assertRaisesRegex(RuntimeError, 'repair_'):
                    repair(root, CORRECTION, execute=True)
                copy.assert_not_called()


if __name__ == '__main__': unittest.main()
