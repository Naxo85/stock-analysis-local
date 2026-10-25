"""Run old revision-3 fixture suites in their historical offline environment.

Their policies inherit today's manifest/attempt flags and one recovery assertion
escapes its frozen clock. Normalize only test globals; production is untouched.
"""
from contextlib import ExitStack
from pathlib import Path
import json, sys, unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[3]
sys.path[:0]=[str(ROOT),str(ROOT/'tests')]
import test_adaptive_maintenance_stage as maintenance
import test_adaptive_luna_repair as repair
from src.local_runner import adaptive_stage as stage

for module in (maintenance,repair.base):
    module.POLICY.update(publication_protocol='legacy',latest_attempt_publication_enabled=False)
    # A historical policy must not inherit a newly activated transport option.
    module.POLICY.pop('maintenance_output_schema',None)

suite=unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromModule(module)
                         for module in (maintenance,repair))
with ExitStack() as stack:
    stack.enter_context(patch.object(stage,'datetime',maintenance.FrozenClock))
    stack.enter_context(patch('src.local_runner.publication_store.GcsStore',
        side_effect=AssertionError('NO REAL GCS IN OFFLINE REGRESSIONS')))
    result=unittest.TextTestRunner(verbosity=1).run(suite)
out={'tests':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),
    'fixture_adjustments':['revision3 legacy publication, no remote attempt publication',
        'no new maintenance schema option inherited by old policy','clock frozen to original03Oct fixture'],
    'limits':'Tests use their own mocked model/upload functions. No production clock/publication rule changed.'}
Path(__file__).with_name('legacy_regressions.json').write_text(json.dumps(out,indent=2),encoding='utf-8')
raise SystemExit(not result.wasSuccessful())
