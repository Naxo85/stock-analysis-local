"""Individual preflight failures retain operational status without financial output."""
import contextlib,io,json,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from src.local_runner import adaptive_stage as stage
from src.local_runner.analysis_attempt import record_attempt
from src.local_runner.publication_contract import attempt_notice

class MemoryStore:
    def __init__(self, fail_failed=False):self.objects={};self.writes=[];self.fail_failed=fail_failed
    def read(self,name):return self.objects.get(name,(None,0))
    def write(self,name,body,generation):
        value=json.loads(body)
        if self.fail_failed and value['status']=='failed':raise RuntimeError('secondary_status_transport_error')
        assert self.read(name)[1]==generation
        self.objects[name]=(body,generation+1);self.writes.append(value)

class IndividualAttemptLifecycle(unittest.TestCase):
    def invoke(self, *, fail_phase=None, enabled=True, fail_notice=False, owned=None):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup);root=Path(temporary.name)
        policy=json.loads((Path(__file__).resolve().parents[1]/'config/codex_analysis.json').read_text())
        policy.update(routing_revision=40,publication_protocol='manifest-v1',latest_attempt_publication_enabled=enabled)
        (root/'config').mkdir();(root/'config/codex_analysis.json').write_text(json.dumps(policy))
        store=MemoryStore(fail_failed=fail_notice)
        args=SimpleNamespace(owned=owned,skip_ibkr_gateway_ensure=False,skip_preflight_updates=False)
        with contextlib.ExitStack() as stack:
            mocks={}
            mocks['ownership']=stack.enter_context(patch('src.local_runner.ownership.recorded_ownership',return_value=(False,{'source':'recorded_test'})))
            mocks['reference']=stack.enter_context(patch.object(stage,'load_reference_payload',return_value={}))
            mocks['codex_preflight']=stack.enter_context(patch('src.local_runner.adaptive_preflight.check',return_value={}))
            mocks['gateway']=stack.enter_context(patch.object(stage.one,'ensure_gateway'))
            mocks['source_update']=stack.enter_context(patch.object(stage.one,'_run_preflight_updates',return_value=0))
            mocks['prepare']=stack.enter_context(patch.object(stage,'prepare'))
            mocks['analyze']=stack.enter_context(patch.object(stage,'analyze'))
            def published(actual_root,work,symbol):return record_attempt(actual_root,work,symbol,'publish','succeeded')
            mocks['publish']=stack.enter_context(patch.object(stage,'publish',side_effect=published))
            factory=stack.enter_context(patch('src.local_runner.publication_store.GcsStore',return_value=store))
            if fail_phase:mocks[fail_phase].side_effect=RuntimeError('original_'+fail_phase+'_failure')
            output=io.StringIO()
            with contextlib.redirect_stdout(output):rc=stage.run_individual(root,'CAT',args)
        work=next((root/'logs/adaptive_individual').glob('*/CAT'))
        return root,work,store,mocks,factory,rc,output.getvalue()

    def test_each_preflight_failure_is_visible_without_financial_output(self):
        for phase in ('ownership','reference','codex_preflight','gateway','source_update'):
            with self.subTest(phase=phase):
                root,work,store,mocks,factory,rc,text=self.invoke(fail_phase=phase)
                self.assertEqual(rc,1)
                failure=json.loads((work/'failure.json').read_text());attempt=json.loads((work/'attempt.json').read_text())
                self.assertEqual(failure['error_message'],'original_'+phase+'_failure')
                self.assertEqual(failure['stage'],phase);self.assertEqual(failure['error_type'],'RuntimeError')
                self.assertEqual(attempt['status'],'failed');self.assertEqual(attempt['stage'],phase)
                self.assertIn('Todavía no hay un informe válido',attempt_notice(attempt,has_report=False))
                self.assertTrue(attempt['started_at']);self.assertGreaterEqual(attempt['at'],attempt['started_at'])
                self.assertEqual(store.writes[-1]['status'],'failed')
                self.assertEqual(set(p.name for p in (root/'output/CAT').iterdir()),{'latest_attempt.json'})
                self.assertFalse((work/'input.json').exists());self.assertFalse((work/'review.json').exists())
                for later in ('prepare','analyze','publish'):mocks[later].assert_not_called()
                self.assertIn(failure['error_message'],text)

    def test_flag_off_retains_local_failure_without_storage_client(self):
        root,work,store,mocks,factory,rc,text=self.invoke(fail_phase='gateway',enabled=False)
        self.assertEqual(rc,1);factory.assert_not_called();self.assertEqual(store.writes,[])
        self.assertEqual(json.loads((work/'attempt.json').read_text())['status'],'failed')

    def test_failed_notice_upload_preserves_primary_cause(self):
        root,work,store,mocks,factory,rc,text=self.invoke(fail_phase='source_update',fail_notice=True)
        self.assertEqual(rc,1)
        failure=json.loads((work/'failure.json').read_text())
        self.assertEqual(failure['error_message'],'original_source_update_failure')
        secondary=json.loads((work/'attempt_publication_failure.json').read_text())
        self.assertEqual(secondary['original_error'],'original_source_update_failure')
        self.assertEqual(secondary['error'],'secondary_status_transport_error')
        self.assertIn('original_source_update_failure',text)

    def test_success_keeps_explicit_ownership_and_full_individual_route(self):
        for owned in (True,False,None):
            with self.subTest(owned=owned):
                root,work,store,mocks,factory,rc,text=self.invoke(owned=owned)
                self.assertEqual(rc,0);self.assertEqual(store.writes[-1]['status'],'succeeded')
                if owned is None:mocks['ownership'].assert_called_once_with('CAT')
                else:mocks['ownership'].assert_not_called()
                self.assertEqual(mocks['prepare'].call_args.args[3],bool(owned))
                self.assertIs(mocks['analyze'].call_args.args[4],True)
                self.assertFalse((work/'failure.json').exists())

    def test_later_stage_failure_names_preserve_phase(self):
        for phase in ('prepare','analyze','publish'):
            with self.subTest(phase=phase):
                root,work,store,mocks,factory,rc,text=self.invoke(fail_phase=phase)
                self.assertEqual(rc,1);self.assertEqual(json.loads((work/'failure.json').read_text())['stage'],phase)
                self.assertEqual(store.writes[-1]['status'],'failed')

if __name__=='__main__':unittest.main()
