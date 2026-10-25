"""Offline reproduction of remaining entry-point CP1252 behavior."""
import io,json,subprocess,sys,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
from src.local_runner import run_batch as batch,update_analysis_sources_pipeline as pipeline
from src.local_runner.process_control import configure_utf8_output
ERROR='ibkr_historical_news_timeout: '+chr(0xfffd)+' no completed response'
class RemainingEncodingTests(unittest.TestCase):
 def test_batch_nonblocking_failure_print_reproduces_cp1252_exception(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);buffer=io.BytesIO();stream=io.TextIOWrapper(buffer,encoding='cp1252',errors='strict')
   result=subprocess.CompletedProcess([],1,stdout='',stderr=ERROR)
   with patch.object(batch.subprocess,'run',return_value=result),patch.object(sys,'stdout',stream):
    with self.assertRaises(UnicodeEncodeError):batch._run_non_blocking_prestep(config=SimpleNamespace(repo_root=root,log_dir=root),name='ibkr_news_update',log_name='result.json',command=['mock'])
   saved=json.loads((root/'result.json').read_text(encoding='utf-8'))
   self.assertEqual(saved['stderr_tail'],ERROR)
   self.assertEqual(saved['status'],'failed_non_blocking')
 def test_shared_utf8_configuration_preserves_batch_result(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);buffer=io.BytesIO();stream=io.TextIOWrapper(buffer,encoding='cp1252',errors='strict')
   result=subprocess.CompletedProcess([],1,stdout='',stderr=ERROR)
   with patch.object(batch.subprocess,'run',return_value=result),patch.object(sys,'stdout',stream),patch.object(sys,'stderr',stream):
    configure_utf8_output()
    answer=batch._run_non_blocking_prestep(config=SimpleNamespace(repo_root=root,log_dir=root),name='ibkr_news_update',log_name='result.json',command=['mock'])
    stream.flush()
   self.assertEqual(answer['stderr_tail'],ERROR)
   self.assertEqual(answer['status'],'failed_non_blocking')
   self.assertIn(ERROR,buffer.getvalue().decode('utf-8'))
 def test_source_pipeline_preserves_error_without_printing_it(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);buffer=io.BytesIO();stream=io.TextIOWrapper(buffer,encoding='cp1252',errors='strict')
   result={'ticker':'NVDA','status':'failed','error':ERROR,'news':{'status':'failed','error':ERROR},'analysts':{'status':'skipped'}}
   with patch.object(pipeline,'_find_repo_root',return_value=root),patch.object(pipeline,'_run_ticker_source_update',return_value=result),patch.object(sys,'stdout',stream):
    code=pipeline.main(['--tickers','NVDA','--progress-dir',str(root/'progress'),'--update-news','--sleep-seconds','0','--deferred-retries','0'])
    stream.flush()
   self.assertEqual(code,1)
   self.assertNotIn(chr(0xfffd),buffer.getvalue().decode('cp1252'))
   saved=json.loads((root/'progress/NVDA.json').read_text(encoding='utf-8'))
   self.assertEqual(saved['error'],ERROR)
if __name__=='__main__':unittest.main(verbosity=2)
