"""Batch provenance accompanies the resolved bool without another holdings read."""
import argparse
import contextlib
import io
import json
import subprocess
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from src.local_runner import adaptive_stage as stage, run_batch as batch
from src.local_runner.ownership import MARKET_OWNERSHIP_GCS_URI
from test_run_batch_pipeline import _config


def args():
    return argparse.Namespace(from_gcs=True, config_gcs=None, tickers=None,
                              generation_provider='codex', legacy_codex=False)


class BatchOwnershipProvenance(unittest.TestCase):
    def test_selected_explicit_bool_and_fallback_provenance_remain_distinct(self):
        selected = {'ticker_records': [{'ticker': 'CAT', 'owned': False,
                    'ownership_source': 'explicit:selected-row'}, {'ticker': 'TLN'}]}
        market = {'ticker_records': [{'ticker': 'CAT', 'owned': True},
                                    {'ticker': 'TLN', 'owned': True}]}
        with patch.object(batch, '_read_gcs_text', side_effect=[json.dumps(selected), json.dumps(market)]) as read:
            records, source = batch._load_ticker_records(args())
            contexts = batch._batch_ownership_context(records, source)
        self.assertEqual(read.call_count, 2)
        self.assertEqual(contexts['CAT'], {'symbol': 'CAT', 'owned': False,
            'selection_source': batch.TICKERS_GCS_URI, 'ownership_source': 'explicit:selected-row'})
        self.assertEqual(contexts['TLN'], {'symbol': 'TLN', 'owned': True,
            'selection_source': batch.TICKERS_GCS_URI, 'ownership_source': MARKET_OWNERSHIP_GCS_URI})

    def test_batch_stage_passes_provenance_only_to_prepare_and_cli_keeps_exact_values(self):
        for owned in (False, True):
            with self.subTest(owned=owned), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                record = batch.TickerRecord('CAT', owned, MARKET_OWNERSHIP_GCS_URI)
                expected = batch._batch_ownership_context([record], batch.CORE_TICKERS_GCS_URI)
                config = _config(root, ('CAT',))
                config = replace(config, adaptive_codex=True, ownership_context=expected,
                                 routes=(replace(config.routes[0], owned=owned),))
                commands = []
                def execute(command, **kwargs):
                    commands.append(command)
                    return subprocess.CompletedProcess(command, 0)
                with patch.object(batch, 'run_bounded', side_effect=execute), patch.object(batch, '_read_gcs_text') as read:
                    for phase in ('prepare', 'analyze', 'publish'):
                        self.assertEqual(batch._run_pipeline_stage(config, batch.PipelineTask('CAT', 1), phase)['status'], 'ok')
                    read.assert_not_called()
                self.assertIn('--ownership-json', commands[0])
                for command in commands[1:]:
                    self.assertNotIn('--ownership-json', command)
                with patch.object(stage.one, '_find_repo_root', return_value=root), patch.object(stage, 'load_policy', return_value={}), patch.object(stage, 'require_activation'), patch('src.local_runner.analysis_attempt.record_attempt'), patch.object(stage, 'prepare') as prepare, contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(stage.main(commands[0][3:]), 0)
                self.assertEqual(prepare.call_args.kwargs['ownership'], expected['CAT'])
                self.assertIs(prepare.call_args.args[3], owned)

    def test_new_batch_config_contains_selected_record_provenance(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            record = batch.TickerRecord('CAT', False, 'record-source')
            route = _config(root, ('CAT',)).routes[0]
            with patch.object(batch, '_find_repo_root', return_value=root), patch.object(batch, '_load_ticker_records', return_value=([record], batch.CORE_TICKERS_GCS_URI)), patch('src.local_runner.adaptive_preflight.check'), patch('src.local_runner.adaptive_policy.load_policy', return_value={}), patch('src.local_runner.adaptive_policy.require_activation'), patch('src.local_runner.adaptive_policy.routes_for', return_value=(route,)), patch.object(batch, 'ensure_gateway'), patch.object(batch, '_run_batch', return_value=0) as execute:
                self.assertEqual(batch.main(['--from-gcs', '--upload-real']), 0)
            self.assertEqual(execute.call_args.args[0].ownership_context['CAT']['ownership_source'], 'record-source')

    def test_invalid_cli_context_fails_before_prepare(self):
        valid = {'symbol': 'CAT', 'owned': False, 'selection_source': batch.TICKERS_GCS_URI,
                 'ownership_source': None}
        variants = [dict(valid, symbol='TLN'), dict(valid, owned='false'), dict(valid, owned=0),
                    dict(valid, owned=True), dict(valid, selection_source=''),
                    dict(valid, ownership_source=[]), dict(valid, extra='unexpected'),
                    {'symbol': 'CAT'}, [], None]
        for value in variants:
            with self.subTest(value=value):
                with self.assertRaisesRegex(RuntimeError, 'invalid_batch_ownership_context'):
                    stage._batch_ownership(json.dumps(value), 'CAT', False)
        for raw in ('broken json', 'x' * 8193):
            with self.subTest(raw=raw[:12]), self.assertRaisesRegex(RuntimeError, 'invalid_batch_ownership_context'):
                stage._batch_ownership(raw, 'CAT', False)
        self.assertIsNone(stage._batch_ownership(None, 'CAT', False))

    def test_legacy_stage_without_optional_argument_preserves_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with patch.object(stage.one, '_find_repo_root', return_value=root), patch.object(stage, 'load_policy', return_value={}), patch.object(stage, 'require_activation'), patch('src.local_runner.analysis_attempt.record_attempt'), patch.object(stage, 'prepare') as prepare, contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(stage.main(['CAT', '--stage', 'prepare', '--batch-dir', str(root)]), 0)
            self.assertIsNone(prepare.call_args.kwargs['ownership'])

    def test_prepare_persists_provenance_but_never_rewrites_frozen_input(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            work = root / 'adaptive' / 'CAT'
            work.mkdir(parents=True)
            expected = {'symbol': 'CAT', 'owned': False, 'selection_source': batch.TICKERS_GCS_URI,
                        'ownership_source': 'explicit:record'}
            with contextlib.ExitStack() as stack:
                stack.enter_context(patch.object(stage, 'load_policy', return_value={'routing_revision': 1}))
                stack.enter_context(patch.object(stage, 'load_reference_payload', return_value={}))
                stack.enter_context(patch.object(stage.one, '_fetch_slim', return_value={}))
                for name in ('_load_analyst_quality', 'load_compact_analyst_summary', 'load_recent_analyst_actions', 'load_recent_news'):
                    stack.enter_context(patch.object(stage.one, name, return_value={}))
                stack.enter_context(patch.object(stage.one, '_load_system_prompt', return_value='fixture'))
                stack.enter_context(patch.object(stage, 'data_ready'))
                stack.enter_context(patch.object(stage, 'load_research', return_value={}))
                stage.prepare(root, work, 'CAT', False, 'tracking', ownership=expected)
            context = json.loads((work / 'input.json').read_text())
            self.assertEqual(context['ownership'], expected)
            before = {p.name: p.read_bytes() for p in work.iterdir() if p.is_file()}
            with patch.object(stage, 'load_policy') as policy, patch.object(stage.one, '_fetch_slim') as fetch:
                stage.prepare(root, work, 'CAT', True, 'priority', ownership={'changed': True})
                policy.assert_not_called(); fetch.assert_not_called()
            self.assertEqual({p.name: p.read_bytes() for p in work.iterdir() if p.is_file()}, before)


if __name__ == '__main__':
    unittest.main()
