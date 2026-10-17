'''General and production replay regressions; no models, network or publication.'''
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import unittest
import os
import tempfile
from unittest.mock import patch

import test_adaptive_maintenance as fixture
from src.common.analysis_validator import (
    _declares_level_change, _declares_level_continuity,
    _declares_level_reprioritization, _validate_previous_level_references,
    validate_markdown,
    extract_range, _to_number, format_exact_price,
)
from src.local_runner.adaptive_context import model_context, validation_context
from src.local_runner.adaptive_maintenance import (
    apply_update, maintenance_schema, maintenance_decision, _refresh_wall_facts, LEVEL_LABELS,
)
from src.local_runner.adaptive_news_research import collect_news_research, attach_news_research
from src.local_runner.adaptive_patch_normalization import refresh_level_percentages
from src.local_runner.adaptive_policy import maintenance_precheck, load_policy
from src.local_runner.adaptive_repair import repair_context
from src.local_runner.source_urls import cited_urls
from src.local_runner import adaptive_capacity as capacity
from src.local_runner.adaptive_cache import reference_key

ROOT = Path(__file__).resolve().parents[1]
BATCH = ROOT/'logs/batch/2026-10-06/09-24-30/adaptive'


class Oct6GeneralTests(unittest.TestCase):
    def test_reference_mirrors_reparsed_without_mutating_anchor_hash_or_legacy(self):
        data, _ = self.example(fixture.MD.replace('$110-112','$110-112.9032'))
        data['reference']['plan']={'resistance':{'lower':110,'upper':112903}}
        data['reference']['validation']={'resistance_range':{'lower':110,'upper':112903}}
        data['sol_reference']=deepcopy(data['reference'])
        frozen=deepcopy(data)
        view=model_context(data)
        self.assertEqual(view['reference']['plan']['resistance']['upper'],112.9032)
        self.assertTrue(view['comparison']['reference_numeric_projection'])
        self.assertEqual(reference_key(view['sol_reference']),reference_key(data['sol_reference']))
        self.assertIn('resistencia_anterior: 110-112.9032',validation_context(data))
        self.assertEqual(data,frozen)
        data['routing_revision']=7
        self.assertEqual(model_context(data)['reference']['plan']['resistance']['upper'],112903)

    @unittest.skipUnless(os.name=='nt','Windows sharing semantics')
    def test_atomic_capacity_save_retries_only_sharing_violation_and_preserves_old_state(self):
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory)
            (folder/'state.json').write_text('old',encoding='utf-8')
            real_replace=Path.replace
            count=[]
            busy=PermissionError('reader holds DELETE sharing'); busy.winerror=32
            def replace(source,destination):
                count.append(1)
                if len(count)==1: raise busy
                return real_replace(source,destination)
            with patch.object(Path,'replace',replace), patch.object(capacity.time,'sleep'):
                capacity._save(folder,{'active':{}})
            self.assertEqual(len(count),2)
            self.assertEqual(json.loads((folder/'state.json').read_text()),{'active':{}})
            old=(folder/'state.json').read_bytes()
            with patch.object(Path,'replace',side_effect=busy), patch.object(capacity.time,'monotonic',side_effect=[0,0,3]), patch.object(capacity.time,'sleep'):
                with self.assertRaises(PermissionError): capacity._save(folder,{'active':{'new':1}})
            self.assertEqual((folder/'state.json').read_bytes(),old)
            unrelated=PermissionError('not a sharing error')
            with patch.object(Path,'replace',side_effect=unrelated) as operation:
                with self.assertRaises(PermissionError): capacity._save(folder,{'active':{}})
                self.assertEqual(operation.call_count,1)

    def test_full_precision_price_token_not_split_into_thousands_and_remainder(self):
        for text, upper in (('207.5-208.9032',208.9032), ('207,5-208,9032',208.9032),
                            ('1,207.5-1,208.9032',1208.9032), ('1.207,5-1.208,9032',1208.9032)):
            with self.subTest(text=text):
                zone=extract_range('Resistencia estructural: $'+text+' (+1% a +2%)','Resistencia estructural')
                self.assertAlmostEqual(zone.upper,upper)
        self.assertEqual(_to_number('16,099'),16099)
        self.assertEqual(_to_number('16.099'),16099)
        for number in (208.9032,208.903,16099,1691.335,0.0000012345678):
            self.assertEqual(_to_number(format_exact_price(number)),number)

    def example(self, markdown=None):
        data, value = fixture.context(), fixture.payload()
        data.update(routing_revision=8)
        data['reference']['slim_snapshot'] = {'latest_price': 100, 'as_of': '2026-10-02T09:00:00Z'}
        data['slim']['as_of'] = '2026-10-03T10:00:00Z'
        if markdown is not None:
            data['reference']['analysis_markdown'] = markdown
        value['base_markdown_sha256'] = hashlib.sha256(data['reference']['analysis_markdown'].encode()).hexdigest()
        value['evidence_gap'] = 'none'
        return data, value

    def test_bare_sentence_punctuation_not_part_of_source_identity(self):
        url = 'https://example.test/news?id=42'
        for ending in ('.', ';', ',', ':', '!', '?'):
            with self.subTest(ending=ending):
                self.assertEqual(cited_urls('Fuente: '+url+ending), {url})
        self.assertEqual(cited_urls('[Fuente](https://example.test/path.)'), {'https://example.test/path.'})
        self.assertEqual(cited_urls('<https://example.test/path;>'), {'https://example.test/path;'})
        self.assertEqual(cited_urls('[Fuente](https://example.test/a_(b))'), {'https://example.test/a_(b)'})

    def test_discovery_still_requires_exact_observed_url_not_snippet_or_query_alias(self):
        url = 'https://example.test/news?id=42'
        raw = json.dumps({'type':'item.completed','item':{'id':'w','type':'web_search','results':[
            {'url':url,'snippet':'https://invented.test/fake'}, {'url':'https://example.test/unused'}]}})+'\n'
        receipt = {'web_search_count':1,'luna_news_events_sha256':hashlib.sha256(raw.encode()).hexdigest()}
        for text, wanted in ((url+'.', [url]), (url+';', [url]),
                             ('https://example.test/news?id=43.', []), ('https://invented.test/fake.', [])):
            value = {'news':{'assessment':text}}
            self.assertEqual([row['url'] for row in collect_news_research(raw,receipt,value)['sources']], wanted)

    def test_absent_percentages_render_arithmetic_only_and_keep_selected_levels(self):
        data, _ = self.example()
        md = fixture.MD.replace(' (-10,00% a -8,00% vs precio actual)', '')
        frozen = deepcopy(data)
        result, audit = refresh_level_percentages(md, data, LEVEL_LABELS)
        self.assertIn('Entrada: $90-92 (-10.00% a -8.00%)', result)
        self.assertIn('Motivo: Se conserva el soporte.', result)
        self.assertEqual(data, frozen)
        self.assertIn('render_missing_derived_level_percentages', [row['method'] for row in audit])
        data['routing_revision'] = 7
        with self.assertRaisesRegex(ValueError, 'missing_level_percentages'):
            refresh_level_percentages(md, data, LEVEL_LABELS)

    def test_partial_or_extra_percentages_not_guessed(self):
        data, _ = self.example()
        for value in ('-10.00%', '-10% a -8% y 99%'):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, 'missing_level_percentages'):
                refresh_level_percentages(fixture.MD.replace('-10,00% a -8,00%', value), data, LEVEL_LABELS)
        raw = fixture.MD.replace('$90-92 (-10,00% a -8,00% vs precio actual)', 'Sin zona verificable')
        result, _ = refresh_level_percentages(raw, data, LEVEL_LABELS)
        self.assertIn('Entrada: Sin zona verificable', result)

    def test_inherited_price_and_state_are_derived_but_stops_unchanged(self):
        data, value = self.example()
        data['slim']['latest_price'] = 88
        frozen, original = deepcopy(data), deepcopy(value)
        result = apply_update(value, data)
        self.assertIn('Precio de referencia: $88', result)
        self.assertIn('Estado actual: por debajo de la zona', result)
        self.assertIn('Stop de gestión: $85', result)
        self.assertIn('Stop estructural: $70', result)
        self.assertIn('Tesis: 8 / 10', result)
        self.assertEqual(data, frozen)
        self.assertEqual(value, original)
        data['routing_revision'] = 7
        with self.assertRaisesRegex(ValueError, 'stale_reference_price'):
            apply_update(value, data)

    def test_explicit_false_price_and_unproven_old_price_still_rejected(self):
        data, value = self.example()
        value['edits'].append(fixture.edit('Precio de referencia: $100', 'Precio de referencia: $999'))
        with self.assertRaisesRegex(ValueError, 'stale_reference_price'):
            apply_update(value, data)
        data, value = self.example()
        data['reference']['slim_snapshot']['latest_price'] = 50
        data['slim']['latest_price'] = 101
        with self.assertRaisesRegex(ValueError, 'stale_reference_price'):
            apply_update(value, data)

    def test_all_typed_snapshot_labels_editable_but_dates_proven(self):
        for label in ('Snapshot técnico', 'Snapshot técnico congelado', 'Instantánea técnica'):
            md = fixture.MD.replace('Precio de referencia: $100\n', 'Precio de referencia: $100\n'+
                label+': 02-10-2026, 09:00 UTC. Sin precios web.\n')
            data, value = self.example(md)
            with self.subTest(label=label):
                result = apply_update(value, data)
                self.assertIn(label+': 03-10-2026, 10:00 UTC.', result)
                bad = deepcopy(data)
                bad['reference']['slim_snapshot']['as_of'] = '2026-10-02T09:01:00Z'
                with self.assertRaisesRegex(ValueError, 'stale_snapshot_banner'):
                    apply_update(value, bad)
                offset = deepcopy(data)
                offset['slim']['as_of'] = '2026-10-03T12:00:00+02:00'
                self.assertIn(label+': 03-10-2026, 10:00 UTC.',apply_update(value,offset))
                explicit = deepcopy(value)
                before = label+': 02-10-2026, 09:00 UTC. Sin precios web.'
                after = label+': 03-10-2026, 10:00 UTC; también 11:00 UTC. Sin precios web.'
                explicit['edits'].append(fixture.edit(before,after))
                with self.assertRaisesRegex(ValueError,'ambiguous_snapshot_banner'):
                    apply_update(explicit,data)

    def test_inherited_quote_banner_refreshes_all_values_not_only_timestamp(self):
        banner = '*Snapshot: 02-10-2026, 09:00 UTC. Mid indicativo; bid $99.00, ask $101.00 y spread 2.000%. No se utilizan precios web.*\n'
        data, value = self.example(fixture.MD.replace('Precio de referencia: $100\n', 'Precio de referencia: $100\n'+banner))
        data['reference']['slim_snapshot']['market_state'] = {'bid':99,'ask':101,'spread_pct':2}
        data['slim']['market_state'] = {'bid':99.5,'ask':100.5,'spread_pct':1}
        result = apply_update(value,data)
        self.assertIn('03-10-2026, 10:00 UTC. Mid indicativo; bid $99.50, ask $100.50 y spread 1.000%',result)
        for mutation in ('old_quote','new_quote','explicit'):
            bad, change = deepcopy(data), deepcopy(value)
            if mutation == 'old_quote': bad['reference']['slim_snapshot']['market_state']['bid'] = 98
            elif mutation == 'new_quote': bad['slim']['market_state']['bid'] = None
            else: change['edits'].append(fixture.edit(banner, banner.replace('$99.00','$88.00')))
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                apply_update(change,bad)

    def test_qualified_wall_price_not_zone_guess_and_metrics_still_strict(self):
        wall = {'type':'put_wall','level':175,'expiration':'2026-10-16','oi':15631,'oi_share_pct':9.8,'gamma_share_pct':11.1}
        data = {'slim':{'as_of':'2026-10-06T09:00:00Z','levels':{'put_walls_top':[wall]}}}
        for qualifier in ('vecino ', 'adyacente ', 'situado en ', ''):
            text = 'Entrada ambiciosa: $173.3-174\nFactores de Entrada ambiciosa: put wall '+qualifier+'$175, 15.631 contratos, 9.8% del OI put y 11.1% del gamma put, vence 16-Oct.\n'
            with self.subTest(qualifier=qualifier):
                self.assertEqual(_refresh_wall_facts('',text,data),(text,[]))
                for before, after in (('$175','$176'), ('11.1%','12.1%'), ('16-Oct','09-Oct')):
                    with self.assertRaises(ValueError): _refresh_wall_facts('',text.replace(before,after),data)

    def test_continuity_accepts_grammar_not_wrong_prior_prices_or_overlap(self):
        for wording in ('Se reprioriza:', 'Se reprioriza desde', 'Se reprioriza —', 'Se reprioriza,'):
            block = 'Salida / objetivo principal: $240\nMotivo: '+wording+' el objetivo anterior de $250 por wall actual $240.'
            self.assertTrue(_declares_level_continuity(block))
            self.assertTrue(_declares_level_change(block))
            self.assertTrue(_declares_level_reprioritization(block))
            self.assertEqual(_validate_previous_level_references(block,'salida_anterior: $250'), [])
            self.assertTrue(_validate_previous_level_references(block.replace('$250','$251'),'salida_anterior: $250'))
            overlap = 'Entrada: $241-242\nMotivo: '+wording+' el bloque anterior $240-250.'
            self.assertTrue(_validate_previous_level_references(overlap,'entrada_anterior: $240-250'))

    def test_revision8_keeps_schema_risks_and_one_repair(self):
        self.assertEqual(maintenance_schema({'routing_revision':8}), maintenance_schema({'routing_revision':7}))
        data,value = self.example()
        for flag in value['risk']:
            bad = deepcopy(value); bad['risk'][flag] = True
            self.assertEqual(maintenance_decision(bad,[],data),'escalate')
        policy=load_policy(ROOT)
        self.assertEqual(policy['luna_repair_version'],1)
        self.assertEqual(policy['priority_itv_sessions'],5)
        self.assertEqual(policy['watchlist_itv_sessions'],5)
        self.assertEqual(policy['max_model_parallel'],6)
        self.assertEqual(policy['triage_model'],'gpt-6-luna')
        self.assertEqual(policy['report_model'],'gpt-6.1-sol')


class Oct6OriginalReplayTests(unittest.TestCase):
    def sources(self,ticker,kind):
        work=BATCH/ticker
        if not work.exists(): self.skipTest('Optional incident artifacts unavailable')
        protected={p:hashlib.sha256(p.read_bytes()).hexdigest() for p in work.iterdir() if p.is_file()}
        raw=json.loads((work/'input.json').read_text(encoding='utf-8'))
        raw['routing_revision']=8  # Evaluation copy ONLY, not a migrated checkpoint.
        raw.update(maintenance_precheck(raw['reference'],raw['slim'],raw['sol_reference'],owned=raw['owned']))
        for call in ('triage','triage_repair'):
            value=json.loads((work/(call+'.response')).read_text(encoding='utf-8'))
            receipt=json.loads((work/(call+'.receipt.json')).read_text(encoding='utf-8'))
            attach_news_research(raw,work,call,receipt,value)
            if call==kind: break
        return work,model_context(raw),value,protected

    def test_six_original_proposals_pass_full_validation_without_rewriting_receipts(self):
        for ticker,kind in (('AMAT','triage_repair'),('SNDK','triage'),('PLTR','triage'),
                            ('TLN','triage'),('NBIS','triage'),('CIFR','triage_repair')):
            with self.subTest(ticker=ticker):
                work,data,value,protected=self.sources(ticker,kind)
                frozen, response=deepcopy(data),deepcopy(value)
                result=validate_markdown(apply_update(value,data),authoritative_context=validation_context(data),
                    require_support_strengths=True,require_resistance=True,require_separate_scores=True)
                self.assertTrue(result.ok,result.errors)
                self.assertEqual(data,frozen)
                self.assertEqual(value,response)
                self.assertEqual(protected,{p:hashlib.sha256(p.read_bytes()).hexdigest() for p in protected})

    def test_CCJ_real_arithmetic_error_remains_visible_with_actionable_repair(self):
        work,data,value,protected=self.sources('CCJ','triage')
        candidate=apply_update(value,data)
        result=validate_markdown(candidate,authoritative_context=validation_context(data),
            require_support_strengths=True,require_resistance=True,require_separate_scores=True)
        self.assertFalse(result.ok)
        feedback=repair_context(data,value,'update_not_allowed_validation',candidate_markdown=candidate)
        check=next(row for row in feedback['maintenance_repair']['strength_checks'] if row['label']=='Entrada')
        self.assertEqual(check['declared_total'],80)
        self.assertEqual(check['component_sum'],78)
        self.assertEqual(check['components']['volumen'],16)
        self.assertIn('2+5+4+4+3=18',check['factors'])
        self.assertEqual(feedback['maintenance_repair']['attempt'],1)
        self.assertEqual(protected,{p:hashlib.sha256(p.read_bytes()).hexdigest() for p in protected})

    def test_SNDK_incorrect_repair_still_not_fuzzy_applied(self):
        _,data,value,_=self.sources('SNDK','triage_repair')
        with self.assertRaisesRegex(ValueError,'ambiguous_or_missing_match'):
            apply_update(value,data)
        feedback=repair_context(data,value,'invalid_update_ambiguous_or_missing_match')
        self.assertTrue(any(row['occurrences']==0 for row in feedback['maintenance_repair']['patch_source_check']))


if __name__=='__main__':
    unittest.main()
