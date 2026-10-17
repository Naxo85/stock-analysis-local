"""Original evidence + non-regression invariants, offline; no model quality claim."""
from copy import deepcopy
from contextlib import ExitStack
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import test_maintenance_text_v20 as v20
from src.local_runner.adaptive_context import model_context, serialize_model_input, unpack_model_context
from src.local_runner.adaptive_maintenance import maintenance_schema
from src.local_runner.adaptive_policy import daily_decision
from src.local_runner.semantic_report import check_schema, reference_document, render_document
from src.local_runner.text_provenance import origins, texts, frame
from src.local_runner.ownership import recorded_ownership
from src.local_runner.adaptive_repair import repair_context

ROOT = Path(__file__).resolve().parent
ARCHIVE = v20.ARCHIVE


def upgrade(value):
    value = deepcopy(value)
    change = value.get('update')
    if change and change.get('plan_explanation'):
        review = change['change_review']['plan_explanation']
        explanation = change['plan_explanation']
        for key in ('setup_reason', 'conclusion'):
            text = explanation[key]
            explanation[key] = {'text': text, 'review': deepcopy(review)} if text else None
        for key, text in explanation['reasons'].items():
            explanation['reasons'][key] = {'text': text, 'review': deepcopy(review)} if text else None
        change['change_review']['plan_explanation'] = None
    return value


def context():
    data = v20.context(); data['routing_revision'] = 21
    return model_context(data)


def candidate(data, decision='update'):
    return upgrade(v20.candidate(data, decision))


def correction(data):
    return upgrade(v20.correction(data))


def document(data, value):
    return v20.v14.v3.document(data, value)


class ChainTests(unittest.TestCase):
    def test_partial_correction_preserves_every_other_text_number_and_origin(self):
        data = context(); value = correction(data); frozen = deepcopy(data); response = deepcopy(value)
        old = reference_document(data['reference']); prior = origins(data)
        doc = document(data, value)
        for field, text in texts(old).items():
            if field != 'target':
                self.assertEqual(texts(doc)[field], text)
                self.assertEqual(doc['text_provenance'][field], prior[field])
        for key in old['plan']:
            for field in ('range', 'strength'):
                self.assertEqual(doc['plan'][key][field], old['plan'][key][field])
        for key in ('fundamental_markdown', 'catalysts', 'next_event'):
            self.assertEqual(doc[key], old[key])
        self.assertEqual(doc['summary'], old['summary'])
        self.assertEqual(doc['text_provenance']['target'], frame(doc))
        self.assertEqual(data, frozen); self.assertEqual(value, response)

    def test_unrelated_reason_cannot_piggyback_on_entry_review(self):
        data = context(); value = correction(data)
        explanation = value['update']['plan_explanation']
        explanation['reasons']['management_stop'] = {'text': 'Se conserva.', 'review': None}
        with self.assertRaises(ValueError): document(data, value)
        explanation['reasons']['management_stop'] = None
        explanation['reasons']['structural_stop'] = {'text': 'Se conserva.', 'review': v20.historical_review()}
        with self.assertRaises(ValueError): document(data, value)
        explanation['reasons']['structural_stop'] = None
        value['update']['change_review']['plan_explanation'] = v20.historical_review()
        with self.assertRaises(ValueError): document(data, value)

    def test_critical_scope_cannot_hide_in_one_text_edit(self):
        data = context(); value = correction(data)
        value['update']['plan_explanation']['reasons']['target']['review']['scope'] = 'fundamental_or_structural'
        self.assertEqual(daily_decision(value, [], data), 'escalate')
        with self.assertRaises(ValueError): document(data, value)

    def test_exact_copy_is_retain_not_new_publication_but_risk_still_escalates(self):
        data = context(); value = correction(data)
        value['update']['plan_explanation']['reasons']['target']['text'] = reference_document(data['reference'])['plan']['target']['reason']
        self.assertEqual(daily_decision(value, [], data), 'retain')
        value['risk']['critical_catalyst'] = True
        self.assertEqual(daily_decision(value, [], data), 'escalate')

    def test_dates_survive_two_updates_and_model_transport(self):
        data = context(); first = document(data, correction(data)); old_date = first['text_provenance']['target']
        for at in ('2026-10-04T12:00:00Z', '2026-10-05T12:00:00Z'):
            data['reference'] = v20.v16.published(data, first); data['slim']['as_of'] = at
            data = model_context(data)
            value = candidate(data)
            value['update']['public_note'] = dict(text='Clarification ' + at, review=v20.historical_review())
            first = document(data, value)
            self.assertEqual(first['text_provenance']['target'], old_date)
            self.assertEqual(first['plan']['target']['reason'], reference_document(data['reference'])['plan']['target']['reason'])
            sent = unpack_model_context(json.loads(serialize_model_input(data)))
            self.assertEqual(sent['comparison']['text_origins']['target'], old_date)
            from src.local_runner.text_provenance import label
            self.assertIn(label(first, 'target'), render_document(first))

    def test_original_usar_conclusion_is_dated_inside_not_current_below(self):
        data = v20.read('USAR'); data['routing_revision'] = 21
        old = reference_document(data['reference']); origin = origins(data)['conclusion']
        zone = old['plan']['entry']['range']
        self.assertLessEqual(zone['lower'], origin['reference_price'])
        self.assertLessEqual(origin['reference_price'], zone['upper'])
        self.assertLess(old['metadata']['reference_price'], zone['lower'])
        self.assertNotEqual(origin['snapshot_at'], old['metadata']['snapshot_at'])
        self.assertEqual(model_context(data)['comparison']['text_origins']['conclusion'], origin)

    def test_mu_valid_original_reason_gets_anchor_date_not_later_container_date(self):
        data = v20.read('MU'); data['routing_revision'] = 21
        old = reference_document(data['reference']); anchor = reference_document(data['sol_reference'])
        self.assertEqual(old['plan']['entry']['reason'], anchor['plan']['entry']['reason'])
        self.assertEqual(origins(data)['entry']['snapshot_at'], anchor['metadata']['snapshot_at'])
        self.assertNotEqual(origins(data)['entry']['snapshot_at'], old['metadata']['snapshot_at'])

    def test_mu_authored_scoped_correction_preserves_five_actual_rationales(self):
        data = v20.read('MU'); data['routing_revision'] = 21; data = model_context(data)
        value = upgrade(v20.upgrade(v20.read('MU', 'triage.json')))
        edit = value['update']['plan_explanation']
        edit['setup_reason'] = edit['conclusion'] = None
        for key in edit['reasons']:
            if key != 'entry': edit['reasons'][key] = None
        doc = document(data, value); old = reference_document(data['reference'])
        for key in old['plan']:
            self.assertEqual(doc['plan'][key]['range'], old['plan'][key]['range'])
            self.assertEqual(doc['plan'][key]['strength'], old['plan'][key]['strength'])
            if key != 'entry': self.assertEqual(doc['plan'][key]['reason'], old['plan'][key]['reason'])
        self.assertEqual(doc['conclusion'], old['conclusion'])
        self.assertEqual(doc['summary'], old['summary'])
        self.assertEqual(doc['text_provenance']['conclusion'], origins(data)['conclusion'])

    def test_legacy_copy_timestamp_cannot_redate_identical_anchor_words(self):
        data = v20.read('MU'); data['routing_revision'] = 21
        old = reference_document(data['reference'])
        old['plan']['entry']['reason_reviewed_at'] = old['metadata']['snapshot_at']
        data['reference'] = v20.v16.published(data, old)
        anchor = reference_document(data['sol_reference'])
        self.assertEqual(origins(data)['entry']['snapshot_at'], anchor['metadata']['snapshot_at'])

    def test_wdc_nbis_spcx_valid_update_paths_keep_financial_results(self):
        for symbol in ('WDC', 'NBIS', 'SPCX'):
            raw = v20.read(symbol); proposal = v20.read(symbol, 'triage.json')
            from src.local_runner.adaptive_news_research import attach_news_research
            receipt = json.loads((ARCHIVE / symbol / 'triage.receipt.json').read_bytes())
            attach_news_research(raw, ARCHIVE / symbol, 'triage', receipt, proposal)
            old_doc = document(model_context(raw), proposal)
            raw['routing_revision'] = 21; data = model_context(raw)
            converted = upgrade(v20.upgrade(proposal))
            with self.subTest(symbol=symbol):
                doc = document(data, converted)
                self.assertEqual(texts(doc), texts(old_doc))
                self.assertEqual(doc['summary'], old_doc['summary'])
                # v19 erased an unedited note. v20/21 intentionally preserve it.
                expected_note = proposal.get('routine_note') or reference_document(data['reference']).get('routine_note', '')
                self.assertEqual(doc['routine_note'], expected_note)
                for key in doc['plan']:
                    for field in ('range', 'strength'):
                        self.assertEqual(doc['plan'][key][field], old_doc['plan'][key][field])

    def test_every_original_retain_stays_retain_with_same_source_data(self):
        count = 0
        for path in ARCHIVE.glob('*/triage.json'):
            review_path = path.with_name('review.json')
            if not review_path.exists() or json.loads(review_path.read_bytes()).get('status') != 'retained': continue
            repaired = path.with_name('triage_repair.json')
            value = json.loads((repaired if repaired.exists() else path).read_bytes())
            raw = v20.read(path.parent.name); original = deepcopy(raw)
            raw['routing_revision'] = 21
            self.assertEqual(daily_decision(v20.upgrade(value), raw.get('guards', []), model_context(raw)), 'retain')
            self.assertEqual(raw['reference'], original['reference'])
            self.assertEqual(raw['slim'], original['slim'])
            count += 1
        self.assertGreaterEqual(count, 37)

    def test_legacy19_receipts_still_exact(self):
        v20.IncidentTests().test_all_original19_receipts_are_byte_exact()

    def test_original_published_content_survives_model_projection(self):
        from src.local_runner.financial_projection import model_input_view
        count = 0
        for path in ARCHIVE.glob('*/publish/output/*/latest.json'):
            raw = path.read_bytes(); payload = json.loads(raw)
            if not payload.get('semantic_report'): continue
            with self.subTest(symbol=path.parent.name):
                doc = reference_document(payload, verify_projection=True)
                # Published Markdown includes a separate maintenance banner and
                # may use an older renderer. Never re-render retained archives.
                view = model_input_view({'routing_revision': 21, 'reference': payload})['reference']
                self.assertEqual(view['analysis_markdown'], payload['analysis_markdown'])
                self.assertEqual(doc, payload['semantic_report']['data'])
                self.assertEqual(view['semantic_data']['summary'], doc['summary'])
                self.assertEqual(view['semantic_data']['conclusion'], doc['conclusion'])
                for key, level in doc['plan'].items():
                    for field in ('range', 'reason', 'strength'):
                        self.assertEqual(view['semantic_data']['plan'][key][field], level[field])
                self.assertEqual(path.read_bytes(), raw)
            count += 1
        self.assertGreater(count, 30)

    def test_schema_is_static_across_tickers_for_prefix_reuse(self):
        data = context(); other = deepcopy(data); other['symbol'] = 'OTHER'
        other['slim']['as_of'] = '2026-10-08T12:00:00Z'
        self.assertEqual(maintenance_schema(data), maintenance_schema(other))

    def test_amat_scoped_repair_keeps_valid_history_and_all_other_financials(self):
        data = v20.read('AMAT'); data['routing_revision'] = 21; data = model_context(data)
        value = upgrade(v20.upgrade(v20.read('AMAT', 'triage.json')))
        change = value['update']; change['public_note'] = None
        explanation = change['plan_explanation']
        explanation['setup_reason'] = explanation['conclusion'] = None
        for key in explanation['reasons']:
            if key != 'entry': explanation['reasons'][key] = None
        doc = document(data, value); old = reference_document(data['reference'])
        self.assertEqual(doc['routine_note'], old['routine_note'])
        self.assertIn('520.08', doc['routine_note'])
        self.assertEqual(doc['summary'], old['summary'])
        self.assertEqual(doc['conclusion'], old['conclusion'])
        for key in old['plan']:
            for field in ('range', 'strength'):
                self.assertEqual(doc['plan'][key][field], old['plan'][key][field])
            if key != 'entry': self.assertEqual(doc['plan'][key]['reason'], old['plan'][key]['reason'])

    def test_unknown_origin_is_not_invented_from_latest_metadata(self):
        data = context(); doc = document(data, correction(data))
        doc['plan']['entry']['reason'] = 'Distinct inherited reason with no original date.'
        doc['plan']['entry'].pop('reason_reviewed_at', None)
        doc['text_provenance'].pop('entry', None)
        data['reference'] = v20.v16.published(data, doc)
        self.assertEqual(origins(data)['entry']['status'], 'unknown')
        self.assertIsNone(origins(data)['entry']['reference_price'])


class OwnershipTests(unittest.TestCase):
    def test_explicit_ticker_batch_uses_same_portfolio_in_one_read(self):
        from src.local_runner import run_batch
        args = SimpleNamespace(from_gcs=False, config_gcs=None, tickers='IREN,MU',
                               generation_provider='codex', legacy_codex=False)
        payload = {'ticker_records': [{'ticker': 'IREN', 'owned': True}, {'ticker': 'MU', 'owned': False}]}
        with patch.object(run_batch, '_read_gcs_text', return_value=json.dumps(payload)) as read:
            records, _ = run_batch._load_ticker_records(args)
        self.assertEqual([(row.ticker, row.owned) for row in records], [('IREN', True), ('MU', False)])
        read.assert_called_once()

    def test_individual_freezes_same_owned_as_market_without_model_or_gateway(self):
        stage = v20.v16.stage
        args = SimpleNamespace(owned=None, reference_tier='tracking',
                               skip_ibkr_gateway_ensure=True, skip_preflight_updates=True)
        with tempfile.TemporaryDirectory() as directory, ExitStack() as stack:
            root = Path(directory)
            stack.enter_context(patch.object(stage, 'load_policy', return_value={'production_enabled': True}))
            stack.enter_context(patch('src.local_runner.adaptive_preflight.check'))
            lookup = stack.enter_context(patch('src.local_runner.ownership.recorded_ownership', return_value=(True, {'source': 'market_config'})))
            stack.enter_context(patch.object(stage, 'load_reference_payload', return_value={}))
            prepared = stack.enter_context(patch.object(stage, 'prepare'))
            stack.enter_context(patch.object(stage, 'analyze'))
            stack.enter_context(patch.object(stage, 'publish'))
            stack.enter_context(patch('builtins.print'))
            self.assertEqual(stage.run_individual(root, 'IREN', args), 0)
            lookup.assert_called_once_with('IREN')
            self.assertEqual(prepared.call_args.args[2:], ('IREN', True, 'priority'))
            self.assertEqual(prepared.call_args.kwargs['ownership'], {'source': 'market_config'})

    def test_cli_distinguishes_unknown_true_and_false(self):
        from src.local_runner.run_one import _parse_args
        self.assertIsNone(_parse_args(['IREN', '--run-full']).owned)
        self.assertIs(_parse_args(['IREN', '--run-full', '--owned']).owned, True)
        self.assertIs(_parse_args(['IREN', '--run-full', '--no-owned']).owned, False)

    def test_explicit_true_false_from_market_source(self):
        for owned in (True, False):
            payload = {'ticker_records': [{'ticker': 'IREN', 'owned': owned, 'ownership_source': 'portfolio.positions'}]}
            result, audit = recorded_ownership('iren', lambda uri: json.dumps(payload))
            self.assertIs(result, owned)
            self.assertIn('config/tickers.json', audit['source'])

    def test_missing_malformed_duplicate_or_network_error_never_means_no_position(self):
        for rows in (None, [], [{'ticker': 'IREN'}], [{'ticker': 'IREN', 'owned': 'false'}],
                     [{'ticker': 'IREN', 'owned': True}, {'ticker': 'IREN', 'owned': False}]):
            with self.subTest(rows=rows), self.assertRaises(RuntimeError):
                recorded_ownership('IREN', lambda uri: json.dumps({'ticker_records': rows}))
        with self.assertRaises(OSError):
            recorded_ownership('IREN', lambda uri: (_ for _ in ()).throw(OSError('offline')))


class PipelineTests(v20.PipelineTests):
    def run_case(self, choices=('retain',), *, due=False, empty=False):
        prior = v20.prior
        original_verdict, original_full = prior.verdict, prior.full
        actions = iter(choices)
        def verdict(data, decision='update'):
            choice = next(actions)
            with patch.object(prior, 'verdict', original_verdict):
                value = candidate(data, 'retain')
                if choice in ('correction', 'badsource', 'badshape'):
                    value = correction(data)
                    if choice == 'badsource':
                        value['update']['plan_explanation']['reasons']['target']['review']['current_evidence'] = ['/reference/missing']
                    if choice == 'badshape':
                        value['update']['plan_explanation']['reasons']['target'] = 'Old unscoped string'
                if choice == 'news':
                    value = candidate(data)
                    value['update']['public_note'] = dict(text='Factual clarification.', review=v20.historical_review())
            if choice == 'missing' or empty: value['news_review'] = []
            return value
        def full(data):
            value = original_full(data)
            for level in value['plan'].values():
                level['evidence'] = [v20.v14.handle(model_context(data), '/slim/levels/supports/0')]
            return value
        raw = prior.data(); raw['news']['items'] = [] if empty else [{'articleId': 'one', 'headline': 'Results'}]
        with patch.object(prior, 'data', return_value=raw), patch.object(prior, 'verdict', side_effect=verdict), patch.object(prior, 'full', side_effect=full):
            return prior.SemanticPipelineTests().run_case(revision=21, due=due)

    def test_repair_uses_current_publication_contract(self):
        data = context(); instruction = repair_context(data, correction(data), 'bad')['maintenance_repair']['instruction']
        self.assertIn('schema21', instruction); self.assertIn('text_origins', instruction)
        self.assertIn('{text, review}', instruction)

    def test_bad_shape_gets_one_repair_not_paid_sol(self):
        result, _, calls = self.run_case(('badshape', 'retain'))
        self.assertEqual(result['status'], 'retained')
        self.assertEqual([kind for kind, _ in calls], ['triage', 'triage_repair'])
        with self.assertRaisesRegex(RuntimeError, 'review_contract_failed_no_sol'):
            self.run_case(('badshape', 'badshape'))

    def test_preparation21_has_one_consistent_contract_for_both_models(self):
        data = context(); stage = v20.v16.stage; prior = v20.prior
        with tempfile.TemporaryDirectory() as directory, ExitStack() as stack:
            work = Path(directory) / 'CAT'; work.mkdir()
            stack.enter_context(patch.object(stage, 'datetime', prior.base.FrozenClock))
            for name, value in {'load_policy': {**prior.base.POLICY, 'routing_revision': 21},
                'load_reference_payload': data['sol_reference'], 'load_current_report': data['reference'],
                'load_research': None}.items(): stack.enter_context(patch.object(stage, name, return_value=value))
            for name, value in {'_fetch_slim': data['slim'], '_load_analyst_quality': {},
                'load_compact_analyst_summary': {}, 'load_recent_analyst_actions': data['analyst_actions'],
                'load_recent_news': data['news'], '_load_system_prompt': 'legacy'}.items():
                stack.enter_context(patch.object(stage.one, name, return_value=value))
            stack.enter_context(patch.object(stage, 'call_codex', side_effect=AssertionError('NO MODEL')))
            stage.prepare(ROOT, work, 'CAT', False, 'tracking')
            for name in ('instructions.md', 'triage_instructions.md'):
                prompt = (work / name).read_text(encoding='utf8')
                self.assertIn('REVISION21', prompt)
                self.assertIn('comparison.text_origins', prompt)
                self.assertIn('{text, review}', prompt)
                for obsolete in ('REVISION20', 'REVISION19', 'REVISION15 OVERRIDE', 'string or null'):
                    self.assertNotIn(obsolete, prompt)


if __name__ == '__main__': unittest.main()
