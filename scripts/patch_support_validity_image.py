"""Execute only within the private derived image; never export its code."""
import ast
import json
from pathlib import Path

PACKAGE=Path('/usr/local/lib/python3.12/site-packages/stock_analysis')
FUNCTIONS=json.loads(Path('/tmp/support36/functions.json').read_text(encoding='utf-8'))

def replace_once(text, old, new):
    if text.count(old)!=1:
        raise RuntimeError('Unexpected deployed contract: '+old[:80])
    return text.replace(old,new,1)

for relative, functions in FUNCTIONS.items():
    path=PACKAGE/relative
    text=path.read_text(encoding='utf-8')
    if relative=='contracts/analysis.py':
        text=replace_once(text,'from datetime import datetime','from datetime import datetime\nimport math\nfrom typing import Any')
        text=replace_once(text,'    setup_reason: str = ""','    setup_reason: str = ""\n    entry_support_validity: dict[str, Any] | None = None\n    washout_support_validity: dict[str, Any] | None = None')
    elif relative=='controller/analysis_sheet.py':
        text=replace_once(text,'from stock_analysis.contracts.analysis import AnalysisSheetRecord, PriceRange',
            'from stock_analysis.contracts.analysis import AnalysisSheetRecord, PriceRange, support_validity_floor')
    elif relative=='analysis_worker/reports.py':
        text=replace_once(text,'from stock_analysis.contracts.analysis import AnalysisSheetRecord, PriceRange',
            'from stock_analysis.contracts.analysis import AnalysisSheetRecord, PriceRange, support_validity_floor')
        text=replace_once(text,'        score_presentations: dict[str, dict[str, str | None]] | None = None,',
            '        score_presentations: dict[str, dict[str, str | None]] | None = None,\n        support_validity: dict[str, Any] | None = None,')
        text=replace_once(text,'            "score_presentation_version": 2,',
            '            "score_presentation_version": 2,\n            "support_validity": support_validity or {},')
    lines=text.splitlines(keepends=True)
    tree=ast.parse(text)
    nodes={n.name:n for n in tree.body if isinstance(n,ast.FunctionDef)}
    # Preserve every unselected function, constant, class, import and setting.
    existing=[(nodes[name],body) for name,body in functions.items() if name in nodes]
    for node,body in sorted(existing,key=lambda pair:pair[0].lineno,reverse=True):
        lines[node.lineno-1:node.end_lineno]=[body+'\n']
    output=''.join(lines)
    for name,body in functions.items():
        if name not in nodes:
            output+='\n\n'+body+'\n'
    ast.parse(output)
    path.write_text(output,encoding='utf-8')
    print('PATCH',relative,','.join(functions))
