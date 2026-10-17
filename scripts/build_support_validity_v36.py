"""Build a function-scoped patch on the active immutable controller image.

No extraction/export of the deployed source; unrelated local constants and
functions (including pending strength policy work) are never copied.
"""
import ast
import hashlib
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / 'logs/support_validity36/build'
SOURCE = ROOT / 'gcp_services/stock_controller'
BASE = 'europe-southwest1-docker.pkg.dev/recipe-generator-429817/cloud-run-source-deploy/stock-controller@sha256:570316a1f4c4442e705b047a2921d33bd535c78aa95d7b87efe3524b03e7b4fd'
FUNCTIONS = {
    'contracts/analysis.py': ['support_validity_floor'],
    'controller/analysis_sheet.py': ['build_analysis_value_requests', 'build_live_proximity_background_requests',
        '_bound_live_range', '_visible_level_cell', '_level_cell', '_proximity_background', '_level_note'],
    'analysis_worker/reports.py': ['parse_analysis_report', '_support_validity', 'load_support_validity'],
    'analysis_worker/run_sync.py': ['effective_sync_version', 'run'],
    'market_worker/run_refresh.py': ['run'],
}


def build_sources():
    DEST.mkdir(parents=True, exist_ok=True)
    payload = {}
    for relative, names in FUNCTIONS.items():
        text = (SOURCE/'src/stock_analysis'/relative).read_text(encoding='utf-8')
        lines = text.splitlines(keepends=True)
        nodes = {n.name: n for n in ast.parse(text).body if isinstance(n, ast.FunctionDef)}
        payload[relative] = {name: ''.join(lines[nodes[name].lineno-1:nodes[name].end_lineno]) for name in names}
    (DEST/'functions.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf-8')
    shutil.copy2(ROOT/'scripts/patch_support_validity_image.py',DEST/'patch.py')
    tests = DEST/'tests'; tests.mkdir(exist_ok=True)
    for name in ('test_support_validity.py','test_analysis_sheet.py','test_analysis_reports.py',
                 'test_support_only_sheet.py','test_report_link_persistence.py','test_analysis_sync_version.py'):
        content = (SOURCE/'tests'/name).read_text(encoding='utf-8')
        # The local tree also contains pending solid65 work. This deployment
        # preserves the ACTIVE 70 threshold; characterize that existing policy
        # without changing the original local tests or shipping the other work.
        if name == 'test_analysis_sheet.py':
            content = content.replace('strength >= 65', 'strength >= 70')
            content = content.replace('washout_strength=65', 'washout_strength=70')
            content = content.replace('Fortaleza: 65/100', 'Fortaleza: 70/100')
        if name == 'test_analysis_reports.py':
            content = content.replace('self.assertEqual(record.washout_strength_category, "sólido")',
                                      'self.assertEqual(record.washout_strength_category, "moderado")')
        (tests/name).write_text(content, encoding='utf-8')
    manifest = {p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in DEST.glob('*') if p.is_file()}
    (DEST/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    print('Prepared five modules as explicit function patches; no whole-repository deployment.')


if __name__ == '__main__':
    build_sources()
