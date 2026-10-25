"""Small offline build check, executed inside the exact deployed base image."""
import ast
import json
from pathlib import Path
import sys

kind = sys.argv[1]
root = Path(__file__).resolve().parent
main = root/'main.py'
tree = ast.parse(main.read_text(encoding='utf-8'))
if kind == 'raw':
    import support_origins as origins
    revision = next(ast.literal_eval(node.value) for node in tree.body
                    if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name)
                    and target.id == 'DATA_CONTRACT_REVISION' for target in node.targets))
    assert revision == 41
    rows = [
        {'date': '2026-10-01', 'open': 99., 'high': 100., 'low': 98., 'close': 99., 'volume': 1000},
        {'date': '2026-10-02', 'open': 102., 'high': 104., 'low': 101., 'close': 103., 'volume': 1200},
    ]
    requested = {'type': 'gap_up_lower', 'level': 100., 'date': '2026-10-02'}
    pool = origins.build_pool(rows, [], [{'date': '2026-10-02', 'lower': 100., 'upper': 101., 'size': 1.}])
    result = origins.observe_support_origins([requested], rows, pool, '2026-10-03T12:00:00+00:00')
    assert result[0]['status'] == 'available'
    assert result[0]['source_record']['meta']['origin_identity']['formation_dates'] == ['2026-10-01', '2026-10-02']
    assert origins.observe_support_origins([dict(requested, level=100.001)], rows, pool, '2026-10-03T12:00:00+00:00')[0]['status'] == 'not_observed'
else:
    import main as slim
    marker = {'schema_version': 1, 'origin_type': 'gap_up_lower', 'method': 'strict_bullish_gap_dated_bars_v1',
              'formation_dates': ['2026-10-01', '2026-10-02'], 'confirmation_dates': ['2026-10-02'],
              'availability_date': '2026-10-02'}
    observation = {'type': 'support_origin_observation', 'origin_type': 'gap_up_lower', 'status': 'available',
        'level': 100., 'source_record': {'type': 'gap_up_lower', 'level': 100.,
            'meta': {'gap_date': '2026-10-02', 'origin_identity': marker}}}
    projected = slim._build_slim({'data_contract_revision': 41, 'latest_price': 102., 'support_origins': [observation]})
    row = projected['levels']['support_origins'][0]
    assert row['source_record']['date'] == '2026-10-02'
    assert row['source_record']['origin_identity'] == marker
    assert row['evidence'] == row['source_record']['evidence']
    assert 'support_origins' not in slim._build_slim({})['levels']
print(json.dumps({'kind': kind, 'offline_image_check': 'passed', 'source_revision': 41}))
