import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT))
from src.local_runner.publication_auth import storage_client
p=json.loads((ROOT/'config/codex_analysis.json').read_text(encoding='utf-8'));c=storage_client(p['publication_auth']);v=json.loads(c.bucket('stock-analysis-system-naxo85').blob('runtime/config/market_sheet_layout.json').download_as_bytes(timeout=30));print(json.dumps({'spreadsheet_id':v['spreadsheet']['spreadsheet_id'],'sheet':v['sheet'],'format_rules':v['format_rules'],'links':v['links'],'groups':v['groups'],'table_template':v['table_template'],'blocks':[{'palette':b['palette'],'start_column':b['start_column'],'end_column':b['end_column'],'header_row':b['header_row'],'tickers':b.get('tickers',[])} for b in v['blocks']]}))
