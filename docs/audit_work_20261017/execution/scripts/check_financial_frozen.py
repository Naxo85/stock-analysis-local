import importlib.util,json
from pathlib import Path
from src.local_runner import semantic_report as current,adaptive_repair as repair
root=Path.cwd();base=root/'.tmp/audit_execution_20261017/baseline/src/local_runner'
def load(name):
 spec=importlib.util.spec_from_file_location('audit_baseline_'+name,base/(name+'.py'))
 module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module
old=load('semantic_report');old_repair=load('adaptive_repair')
results=[]
for revision in range(9,40):
 assert current.report_schema(revision)==old.report_schema(revision),('report',revision)
 assert current.update_schema(revision)==old.update_schema(revision),('update',revision)
 context={'routing_revision':revision}
 assert repair.repair_context(context,{},'update_not_allowed_plan_coherence')==old_repair.repair_context(context,{},'update_not_allowed_plan_coherence'),('repair',revision)
 results.append({'revision':revision,'report_schema':'exact','update_schema':'exact','repair_context':'exact'})
(root/'.tmp/audit_execution_20261017/financial_frozen_contracts.json').write_text(json.dumps(results,indent=2))
print(f'{len(results)} revisions exact: schemas and repair_context9..39')
