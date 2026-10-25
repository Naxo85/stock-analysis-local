import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from google.api_core.exceptions import PreconditionFailed
from src.local_runner import manage_market_tracking as tracking, tracking_store as state

LAYOUT = json.loads(tracking.LAYOUT_PATH.read_text(encoding='utf-8'))


class Store:
    def __init__(self, portfolio):
        self.values = {state.LAYOUT_OBJECT: copy.deepcopy(LAYOUT), state.PORTFOLIO_OBJECT: copy.deepcopy(portfolio)}
        self.generations = {key: 1 for key in self.values}
        self.before_write = None
    def read(self, name):
        return json.dumps(self.values[name]), self.generations[name]
    def write(self, name, body, generation):
        if self.before_write:
            callback, self.before_write = self.before_write, None
            callback(self)
        if self.generations[name] != generation:
            raise PreconditionFailed('newer writer')
        self.values[name] = json.loads(body)
        self.generations[name] += 1


class RuntimeTrackingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.store = Store({'positions':{}, 'applied_tracking_commands':[]})
        for owner, name, value in [
            (tracking, 'REPO_ROOT', self.root),
            (tracking, 'LAYOUT_PATH', self.root/'layout.json'),
            (tracking, 'PORTFOLIO_PATH', self.root/'portfolio.json'),
        ]:
            p=patch.object(owner,name,value);p.start();self.addCleanup(p.stop)
        for owner, name, kwargs in [
            (state,'runtime_store',{'return_value':self.store}),
            (tracking,'_upload_runtime_state',{}),
            (tracking,'_publish_portfolio',{}),
            (tracking,'_reconcile_structure',{}),
        ]:
            p=patch.object(owner,name,**kwargs);p.start();self.addCleanup(p.stop)

    def apply(self, command='one'):
        return tracking.apply_tracking_change(action='buy',ticker='AMD',group_id=None,
            observed_shots=0,portfolio_snapshot={},command_id=command,
            snapshot_at='2026-10-21T06:00:00Z',publish=True)

    def test_menu_commit_is_acknowledged_without_repeating_delta(self):
        self.store.values[state.PORTFOLIO_OBJECT] = {'positions':{'AMD':3},'applied_tracking_commands':[
            {'command_id':'one','action':'buy','ticker':'AMD','applied_at':'2026-10-21T06:10:00Z',
             'publication_pending':True,'result':{'ticker':'AMD','shots':3,'structure_changed':False}}]}
        self.assertEqual(self.apply()['shots'],3)
        final=self.store.values[state.PORTFOLIO_OBJECT]
        self.assertEqual(final['positions'],{'AMD':3})
        self.assertFalse(final['applied_tracking_commands'][0]['publication_pending'])

    def test_compare_and_set_rebases_delta_onto_newer_portfolio(self):
        def concurrent(store):
            store.values[state.PORTFOLIO_OBJECT]['positions']['TSM']=2
            store.generations[state.PORTFOLIO_OBJECT]+=1
        self.store.before_write=concurrent
        self.apply()
        self.assertEqual(self.store.values[state.PORTFOLIO_OBJECT]['positions'],{'AMD':1,'TSM':2})

    def test_finish_does_not_overwrite_newer_menu_click(self):
        def concurrent_menu(*args):
            self.store.values[state.PORTFOLIO_OBJECT]['positions']['AMD']=2
            self.store.values[state.PORTFOLIO_OBJECT]['applied_tracking_commands'].append(
                {'command_id':'two','ticker':'AMD','publication_pending':True})
            self.store.generations[state.PORTFOLIO_OBJECT]+=1
        with patch.object(tracking,'_publish_portfolio',side_effect=concurrent_menu):
            self.apply()
        final=self.store.values[state.PORTFOLIO_OBJECT]
        self.assertEqual(final['positions']['AMD'],2)
        self.assertTrue(final['applied_tracking_commands'][1]['publication_pending'])

    def test_worker_projects_newest_state_after_uploads(self):
        def concurrent_menu(*args):
            self.store.values[state.PORTFOLIO_OBJECT]['positions']['TSM']=1
            self.store.generations[state.PORTFOLIO_OBJECT]+=1
        with patch.object(tracking,'_upload_runtime_state',side_effect=concurrent_menu), \
             patch.object(tracking,'_publish_portfolio') as publish:
            self.apply()
        self.assertEqual(publish.call_args.args[1],{'AMD':1,'TSM':1})

    def test_existing_command_id_cannot_authorize_a_different_operation(self):
        self.store.values[state.PORTFOLIO_OBJECT]['applied_tracking_commands']=[
            {'command_id':'one','ticker':'TSM','action':'buy','result':{}}]
        with self.assertRaisesRegex(ValueError,'identity_conflict'):
            self.apply()


if __name__ == '__main__':
    unittest.main()
