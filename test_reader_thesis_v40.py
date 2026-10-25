import unittest
from copy import deepcopy
from src.local_runner.reader_report import thesis_lines

class ReaderThesisTests(unittest.TestCase):
    def doc(self, revision=40):
        return {'metadata':{'source_contract_revision':revision,'snapshot_at':'2026-10-17T15:00:00Z'},'thesis_state':{'status':'deteriorada','premise':'Entrega de productos.','assessment':'Incumplimiento material, pendiente de resolver.','assessed_at':'2026-10-14T15:00:00Z','evidence':[{'source':'/news/items/0','observation':'Privada'}],'evidence_audit':{'hash':'secreto'}}}
    def test_inherited_date_and_no_internal_audit(self):
        d=self.doc(); old=deepcopy(d); text='\n'.join(thesis_lines(d)); self.assertIn('2026-10-14',text);self.assertNotIn('2026-10-17',text);self.assertNotIn('/news',text);self.assertNotIn('secreto',text);self.assertEqual(d,old)
    def test_old_contract_unchanged(self):
        self.assertEqual(thesis_lines(self.doc(39)),[])
    def test_absence_never_defaults_to_healthy(self):
        d=self.doc();d['thesis_state']=None;self.assertEqual(thesis_lines(d),[])
    def test_uncertainty_is_distinct(self):
        d=self.doc();d['thesis_state']['status']='no_determinable';self.assertIn('No determinable',thesis_lines(d)[0])
if __name__=='__main__':unittest.main()
