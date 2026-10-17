"""Offline routing and historical-measurement regressions; no model or network."""
import copy
import json
from pathlib import Path
import sys
import pytest

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'tests'))
from test_support_resistances_slim_evidence import raw, slim, _daily_bars
from src.local_runner.adaptive_policy import maintenance_precheck
from src.local_runner.reaction_comparison import observations


def measured(bars, atr=2, tolerance=.5):
    supports = [{'type': 'support', 'level': 98., 'meta': {'tolerance': tolerance}}]
    raw._annotate_support_evidence(supports, [], bars, atr, {})
    return supports[0]


def test_today_atr_and_live_tolerance_do_not_rewrite_history():
    bars = _daily_bars()
    today = dict(bars[-1], date=raw.datetime.now(raw.timezone.utc).date().isoformat())
    a = measured(bars + [today])
    today.update(high=200, low=50, close=75)
    b = measured(bars + [today], atr=30, tolerance=15)
    assert a['meta']['historical_reaction'] == b['meta']['historical_reaction']
    assert (a['meta']['tolerance'], b['meta']['tolerance']) == (.5, 15)
    result = slim._build_slim({'supports': [a], 'latest_price': 105})
    assert result['levels']['supports'][0]['evidence']['historical_reaction']['measurement_basis'] == a['meta']['historical_reaction']['measurement_basis']


def test_completed_or_corrected_history_remains_visible():
    bars = _daily_bars()
    basis = measured(bars)['meta']['historical_reaction']['measurement_basis']
    added = bars + [dict(bars[-1], date='2026-09-01')]
    assert measured(added)['meta']['historical_reaction']['measurement_basis']['history_sha256'] != basis['history_sha256']
    bars[40]['high'] += 10
    assert measured(bars)['meta']['historical_reaction']['measurement_basis']['history_sha256'] != basis['history_sha256']
    assert measured([])['meta']['historical_reaction']['status'] == 'unavailable'


@pytest.mark.parametrize('owned', [False, True, None])
@pytest.mark.parametrize('ticker', ['QBTS', 'ASTS'])
def test_original_routing_preserves_active_owned_unknown_and_legacy(ticker, owned):
    p = ROOT / 'logs/batch/2026-10-09/15-39-36/adaptive' / ticker / 'input.json'
    data = json.loads(p.read_text(encoding='utf-8'))
    before = copy.deepcopy(data)
    def check(rev):
        return maintenance_precheck(data['reference'], data['slim'], data['sol_reference'], owned=owned, revision=rev)
    assert 'price_below_structural_stop' in check(25)['guards']
    new = check(26)
    exempt = ticker == 'QBTS' and owned is False
    assert ('price_below_structural_stop' not in new['guards']) == exempt
    assert any(f['code'] == 'historical_structural_stop_on_suspended_plan' for f in new['review_flags']) == exempt
    assert data == before


def test_comparison_is_exact_scoped_and_not_a_materiality_gate():
    raw_row = measured(_daily_bars())
    row = slim._build_slim({'supports': [raw_row], 'latest_price': 105})['levels']['supports'][0]
    context = {'routing_revision': 26, 'slim': {'levels': {'supports': [row]}},
               'reference': {'slim_snapshot': {'levels': {'supports': [copy.deepcopy(row)]}}}}
    previous = context['reference']['slim_snapshot']['levels']['supports'][0]
    def classification():
        return observations(context)['comparisons'][0]['classification']
    assert classification() == 'same_history_same_measurement'
    previous['evidence']['historical_reaction']['measurement_basis']['history_sha256'] = 'older'
    assert classification() == 'completed_history_changed'
    previous['evidence']['historical_reaction'].pop('measurement_basis')
    assert classification() == 'legacy_basis_not_comparable'
    previous['level'] += .01
    assert observations(context)['comparisons'] == []
    previous['level'] = row['level']
    context['reference']['slim_snapshot']['levels'] = {'put_walls_top': [previous]}
    assert observations(context)['comparisons'] == []


def test_context_revision25_unchanged_and26_provenance_only():
    from src.local_runner.adaptive_context import model_context
    p = ROOT / 'logs/batch/2026-10-09/15-39-36/adaptive/MRVL/input.json'
    data = json.loads(p.read_text(encoding='utf-8'))
    old = model_context(dict(data, routing_revision=25))
    new = model_context(dict(data, routing_revision=26))
    assert 'historical_measurements' not in old['comparison']
    rows = new['comparison']['historical_measurements']['comparisons']
    assert rows and all(r['classification'] == 'legacy_basis_not_comparable' for r in rows)
    new['comparison'].pop('historical_measurements')
    new['comparison']['contract'] = old['comparison']['contract']
    new['routing_revision'] = old['routing_revision']
    assert new == old


@pytest.mark.parametrize('revision', [26,27])
def test_new_preparation_freezes_both_prompts_and_preserves25(revision):
    import tempfile
    from contextlib import ExitStack
    from unittest.mock import patch
    from src.local_runner import adaptive_stage as stage
    from src.local_runner.adaptive_repair import repair_context
    folder = ROOT / 'logs/batch/2026-10-09/15-39-36/adaptive/QBTS'
    data = json.loads((folder/'input.json').read_text(encoding='utf-8'))
    files = ['input.json', 'instructions.md', 'triage_instructions.md', 'policy.json']
    original = {n: (folder/n).read_bytes() for n in files}
    policy = json.loads((ROOT/'config/codex_analysis.json').read_text(encoding='utf-8'))
    policy['routing_revision'] = revision
    with tempfile.TemporaryDirectory() as directory, ExitStack() as stack:
        from datetime import datetime, timezone
        clock = stack.enter_context(patch.object(stage, 'datetime', wraps=datetime))
        clock.now.return_value = datetime(2026,10,9,16,tzinfo=timezone.utc)
        work = Path(directory)
        for name, result in [('load_policy', policy), ('load_reference_payload', data['sol_reference']),
                             ('load_current_report', data['reference']), ('load_research', None)]:
            stack.enter_context(patch.object(stage, name, return_value=result))
        for name, result in [('_fetch_slim', data['slim']), ('_load_analyst_quality', {}),
            ('load_compact_analyst_summary', {}), ('load_recent_analyst_actions', data['analyst_actions']),
            ('load_recent_news', data['news']), ('_load_system_prompt', 'legacy')]:
            stack.enter_context(patch.object(stage.one, name, return_value=result))
        stack.enter_context(patch.object(stage, 'call_codex', side_effect=AssertionError('NO MODEL')))
        stage.prepare(ROOT, work, 'QBTS', False, data['tier'])
        for name in ('instructions.md', 'triage_instructions.md'):
            assert 'Revision 26:' in (work/name).read_text(encoding='utf-8')
            assert ('Revision27:' in (work/name).read_text(encoding='utf-8')) == (revision == 27)
        assert stage.read_json(work/'policy.json')['routing_revision'] == revision
    assert original == {n: (folder/n).read_bytes() for n in files}
    assert 'Revision26:' in repair_context({'routing_revision':26}, {}, 'test')['maintenance_repair']['instruction']
    assert 'Revision26:' not in repair_context({'routing_revision':25}, {}, 'test')['maintenance_repair']['instruction']
