"""Routing regression tests: no provider calls and no real publication."""
import json
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch
from src.local_runner import adaptive_policy as policy, adaptive_stage as stage
from src.local_runner.adaptive_budget import read_json, write_json
from test_adaptive_analysis import ROOT, POLICY, NOW, triage


class RoutingTests(unittest.TestCase):
    def context(self):
        old = {"level": 101, "type": "put_wall", "expiration": "2026-09-30", "oi": 1000,
               "gamma_share_pct": 25}
        new = {**old, "expiration": "2026-10-09", "oi": 1200}
        ref = {"analysis_status": "ok", "analysis_markdown": "Entrada: 100-102\nEntrada ambiciosa: Sin zona verificable",
               "generated_at": NOW.isoformat(), "generation_model": "gpt-6.1-sol", "reasoning_effort": "high",
               "latest_price": 105, "plan": {"management_stop": 95},
               "slim_snapshot": {"as_of": "2026-09-30T14:00:00Z", "latest_price": 105,
                                 "levels": {"supports": [], "put_walls_top": [old]}}}
        slim = {"as_of": NOW.isoformat(), "latest_price": 105,
                "levels": {"supports": [{"level": 101, "type": "sma20", "strength_score": 80}],
                           "put_walls_top": [new]}}
        return {"symbol": "CAT", "prepared_at": NOW.isoformat(), "reference": ref, "slim": slim,
                "owned": False, "tier": "tracking", "news": {}, "analyst_actions": {}}

    def test_same_strike_renewal_goes_to_luna_not_automatic_sol(self):
        c = self.context()
        result = policy.routing_precheck(c['reference'], c['slim'])
        self.assertEqual(result['guards'], [])
        self.assertIn('option_origin_renewed_requires_review', [f['code'] for f in result['review_flags']])
        self.assertIn('prior_ambitious_entry_explicitly_absent', [f['code'] for f in result['review_flags']])
        self.assertIn('prior_support_option_expired', policy.legacy_safeguards(c['reference'],c['slim']))

    def test_lost_expired_origin_still_forces_sol(self):
        c = self.context()
        c['slim']['levels']['put_walls_top'] = []
        guards = policy.safeguards(c['reference'],c['slim'])
        self.assertIn('prior_support_option_expired', guards)
        self.assertIn('prior_put_walls_top_origin_missing', guards)
        self.assertEqual(policy.triage_decision(triage(),guards), 'escalate')

    def test_replacement_must_be_same_strike_live_and_supported(self):
        for update in ({'level':101.4}, {'expiration':'2026-09-30'}, {'expiration':None},
                       {'oi':0,'gamma_share_pct':0}, {'type':'call_wall'}):
            c = self.context()
            c['slim']['levels']['put_walls_top'][0].update(update)
            with self.subTest(update=update):
                self.assertIn('prior_support_option_expired', policy.safeguards(c['reference'],c['slim']))

    def test_put_origin_moving_between_arrays_is_review_not_lost_support(self):
        c = self.context()
        c['slim']['levels']['supports'] = [{**c['slim']['levels']['put_walls_top'][0], 'type':'put_wall_gamma'}]
        c['slim']['levels']['put_walls_top'] = []
        r = policy.routing_precheck(c['reference'],c['slim'])
        self.assertEqual(r['guards'], [])
        self.assertIn('put_origin_moved_between_source_lists', [f['code'] for f in r['review_flags']])

    def test_ambitious_absence_does_not_hide_malformed_or_missing_entry(self):
        c = self.context()
        for text in ('Entrada: 100-102\nEntrada ambiciosa: Sin zona verificable',
                     'Entrada: 100-102\nEntrada ambiciosa: **No aplicable**'):
            c['reference']['analysis_markdown'] = text
            self.assertNotIn('unparseable_prior_entry', policy.safeguards(c['reference'],c['slim']))
        for text in ('Entrada: 100-102\nEntrada ambiciosa: raro', 'Entrada: 100-102',
                     'Entrada: Sin zona verificable\nEntrada ambiciosa: No aplicable'):
            c['reference']['analysis_markdown'] = text
            self.assertIn('unparseable_prior_entry', policy.safeguards(c['reference'],c['slim']))

    def test_new_stop_breach_forces_sol_but_already_assessed_breach_goes_to_luna(self):
        c = self.context()
        c['slim']['latest_price'] = 94
        self.assertIn('price_below_management_stop', policy.safeguards(c['reference'],c['slim']))
        c['reference']['latest_price'] = 94
        r = policy.routing_precheck(c['reference'],c['slim'])
        self.assertNotIn('price_below_management_stop', r['guards'])
        self.assertIn('price_already_below_stop_in_reference', [f['code'] for f in r['review_flags']])
        c['slim']['latest_price'] = 80
        self.assertIn('price_move_ge_8pct_since_report', policy.safeguards(c['reference'],c['slim']))

    def test_origin_type_change_and_strength_loss_still_force_sol(self):
        c = self.context()
        c['reference']['slim_snapshot']['levels']['supports'] = [{'level':101,'type':'sma20','strength_score':80}]
        c['slim']['levels']['supports'][0]['type'] = 'other'
        self.assertIn('prior_supports_origin_missing', policy.safeguards(c['reference'],c['slim']))
        c['slim']['levels']['supports'][0].update(type='sma20',strength_score=60)
        self.assertIn('support_strength_deteriorated_or_unknown',policy.safeguards(c['reference'],c['slim']))

    def test_review_flags_never_force_retain_and_itv_still_overrides(self):
        for decision in ('retain','escalate'):
            with self.subTest(decision=decision), tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp); c=self.context()
                write_json(root/'input.json',c); write_json(root/'policy.json',POLICY)
                def model(*args,**kw):
                    if args[5] == 'report': raise RuntimeError('SOL CALLED')
                    self.assertTrue(args[6]['review_flags'])
                    return {'text':json.dumps(triage(decision)), 'usage':{'output_tokens':5}}
                # This branch tests review flags, not the wall-clock age of the
                # archived fixture. ITV overriding is exercised below.
                with patch.object(stage,'data_ready'), patch.object(stage,'itv_state',return_value={'due':False}), \
                     patch.object(stage,'model_call',side_effect=model) as call:
                    if decision == 'escalate':
                        with self.assertRaisesRegex(RuntimeError,'SOL CALLED'): stage.analyze(root,root,'CAT',root/'budget.json',False)
                        self.assertEqual([a.args[5] for a in call.call_args_list],['triage','report'])
                    else:
                        self.assertEqual(stage.analyze(root,root,'CAT',root/'budget.json',False)['status'],'retained')
                        self.assertEqual(call.call_count,1)
        for force,itv in ((False,True),(True,False)):
            with tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp); write_json(root/'input.json',self.context()); write_json(root/'policy.json',POLICY)
                with patch.object(stage,'data_ready'), patch.object(stage,'itv_state',return_value={'due':itv}), \
                     patch.object(stage,'model_call',side_effect=RuntimeError('stop before generation')) as call:
                    with self.assertRaises(RuntimeError): stage.analyze(root,root,'CAT',root/'budget.json',force)
                    self.assertEqual(call.call_args.args[5],'report')

    def test_frozen_legacy_revision_keeps_original_guards_and_context(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); write_json(root/'input.json',self.context())
            old_policy={k:v for k,v in POLICY.items() if k!='routing_revision'}
            write_json(root/'policy.json',old_policy)
            with patch.object(stage,'data_ready'), patch.object(stage,'model_call',side_effect=RuntimeError('inspect')) as call:
                with self.assertRaises(RuntimeError): stage.analyze(root,root,'CAT',root/'budget.json',False)
                self.assertEqual(call.call_args.args[5],'report')
                context=call.call_args.args[6]
                self.assertNotIn('review_flags',context)
                self.assertEqual(context['guards'],policy.legacy_safeguards(context['reference'],context['slim']))

    def test_cache_contract_changes_with_routing_revision(self):
        from src.local_runner.adaptive_cache import triage_key
        c=self.context()
        a=triage_key(c,{**POLICY,'routing_revision':1},'same',{},NOW)
        b=triage_key(c,POLICY,'same',{},NOW)
        self.assertNotEqual(a,b)

    def test_known_batch_examples_enter_luna_without_forcing_retention(self):
        directory=ROOT/'logs/batch/2026-10-03/07-48-11/adaptive'
        if not directory.exists(): self.skipTest('local incident evidence unavailable')
        for symbol in ('NVDA','ORCL','PLTR','CIFR','OKLO','MP'):
            c=read_json(directory/symbol/'input.json')
            with self.subTest(symbol=symbol):
                self.assertEqual(policy.safeguards(c['reference'],c['slim']),[])
                self.assertTrue(policy.routing_precheck(c['reference'],c['slim'])['review_flags'])
        for symbol in ('APP','COIN','HOOD'):
            c=read_json(directory/symbol/'input.json')
            self.assertTrue(policy.safeguards(c['reference'],c['slim']),symbol)
