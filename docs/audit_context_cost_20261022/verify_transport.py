"""Run transport regressions without models or publication tests."""
import contextlib
import io
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
import pytest

args=['tests/test_diff_transport.py','tests/test_diff_transport_binding.py','tests/test_adaptive_delta.py',
      'tests/test_stable_maintenance.py','tests/test_adaptive_capacity.py',
      '-k','not live_policy and not completed_report_reused and not retain_cannot_overwrite',
      '-q','-p','no:cacheprovider']
buffer=io.StringIO()
with contextlib.redirect_stdout(buffer),contextlib.redirect_stderr(buffer):
    code=pytest.main(args)
text=buffer.getvalue()
Path(__file__).with_name('transport_test_results.txt').write_text(text,encoding='utf-8')
print(text[-12000:])
raise SystemExit(code)
