"""Inspect local protocol metadata only; never starts a thread or model turn."""
from pathlib import Path
import json, os, subprocess, sys, tempfile

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from src.local_runner.codex_generator import require_codex

HERE = Path(__file__).resolve().parent
cli = require_codex()
def run(*args):
    p = subprocess.run([cli, *args], capture_output=True, text=True, encoding='utf-8',
        errors='replace', timeout=60,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
    assert p.returncode == 0, (args, p.stderr)
    return p.stdout.strip()

result = {'version': run('--version'), 'binary': cli, 'schemas': {}, 'cache_fields': []}
names = ('ThreadInjectItemsParams', 'TurnStartParams', 'ThreadStartParams',
         'ResponseItem', 'UserInput', 'ContentItem', 'DynamicToolSpec')
with tempfile.TemporaryDirectory(prefix='stock-sol-protocol-') as folder:
    run('app-server', 'generate-json-schema', '--experimental', '--out', folder)
    files = list(Path(folder).rglob('*.json'))
    result['file_count'] = len(files)
    def walk(v, path, file):
        if isinstance(v, dict):
            for key, value in v.items():
                normalized = key.lower().replace('_', '').replace('-', '')
                if any(s in normalized for s in ('promptcache', 'cachettl', 'cacheretention')):
                    result['cache_fields'].append({'file': file, 'path': path+'/'+key, 'value': value})
                walk(value, path+'/'+key, file)
        elif isinstance(v, list):
            for i, child in enumerate(v): walk(child, path+'/'+str(i), file)
    for file in files:
        value = json.loads(file.read_text(encoding='utf-8'))
        relative = str(file.relative_to(folder))
        walk(value, '', relative)
        if file.stem in names:
            result['schemas'][file.stem] = value
        for name in names:
            node = value.get('definitions', {}).get(name) or value.get('$defs', {}).get(name)
            if node is not None: result['schemas'].setdefault(name, node)

result['limits'] = 'Generated protocol schema is metadata, not a live admission, cache-hit or retention test.'
(HERE/'protocol.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
for name, schema in result['schemas'].items():
    print(name, json.dumps(schema, ensure_ascii=True)[:12500])
print(json.dumps({k:v for k,v in result.items() if k!='schemas'}, ensure_ascii=True, indent=2))
