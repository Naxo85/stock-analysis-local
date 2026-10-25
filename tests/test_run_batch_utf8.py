"""Entry-point regression: captured source errors must survive Windows output."""
import io,json,os,subprocess,sys,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from src.local_runner import run_batch as batch
class StopBeforeBatchWork(Exception):pass
class BatchUtf8Tests(unittest.TestCase):
 def run_error(self,error):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);raw=io.BytesIO();stream=io.TextIOWrapper(raw,encoding='cp1252',errors='strict');answers=[]
   completed=subprocess.CompletedProcess([],1,stdout='',stderr=error)
   def exercise_actual_error_path(argv):
    answers.append(batch._run_non_blocking_prestep(config=SimpleNamespace(repo_root=root,log_dir=root),name='ibkr_news_update',log_name='result.json',command=['simulated-source']))
    raise StopBeforeBatchWork()
   with patch.dict(os.environ,{'PYTHONIOENCODING':'cp1252','PYTHONUTF8':'0'}),patch.object(batch,'_parse_args',side_effect=exercise_actual_error_path),patch.object(batch.subprocess,'run',return_value=completed),patch.object(sys,'stdout',stream),patch.object(sys,'stderr',stream):
    with self.assertRaises(StopBeforeBatchWork):batch.main([])
    stream.flush()
    self.assertEqual(os.environ['PYTHONIOENCODING'],'utf-8')
    self.assertEqual(os.environ['PYTHONUTF8'],'1')
   self.assertEqual(answers[0]['status'],'failed_non_blocking')
   self.assertEqual(answers[0]['stderr_tail'],error)
   saved=json.loads((root/'result.json').read_text(encoding='utf-8'))
   self.assertEqual(saved['stderr_tail'],error)
   self.assertIn(error,raw.getvalue().decode('utf-8'))
 def test_main_preserves_non_cp1252_source_error_and_failed_return(self):
  self.run_error('ibkr_historical_news_timeout: '+chr(0xfffd)+' no completed response')
 def test_main_preserves_ascii_source_failure_without_hiding_it(self):
  self.run_error('ibkr_historical_news_incomplete: provider_has_more')
if __name__=='__main__':unittest.main()
