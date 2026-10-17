"""Refresh only a report's HTML reader view; never rebind financial authority."""
import argparse
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import os

from src.local_runner.semantic_report import reference_document, render_document
from src.local_runner.html_report import write_analysis_html
from src.local_runner.analysis_state import _exclusive_read_lock
from src.local_runner.gcs_uploader import require_gcloud, TEST_BUCKET


def editorial_document(payload, overlay):
    expected = hashlib.sha256(payload['analysis_markdown'].encode()).hexdigest()
    if overlay['source_markdown_sha256'] != expected:
        raise ValueError('presentation_source_changed')
    doc = reference_document(payload, verify_projection=True)
    # Text-only allowlist: no prices/scores/dates/events/metadata or authority edits.
    allowed = {('summary', k) for k in ('thesis_reason', 'setup_reason', 'narrative')}
    allowed |= {('plan', k, 'reason') for k in doc['plan']}
    allowed |= {('catalysts', str(i), 'description') for i in range(len(doc['catalysts']))}
    allowed |= {('next_event', 'description'), ('conclusion',)}
    for pointer, text in overlay['text'].items():
        parts = tuple(pointer.strip('/').split('/'))
        if parts not in allowed or not isinstance(text, str) or not text.strip():
            raise ValueError('presentation_not_a_text_field: ' + pointer)
        node = doc
        for part in parts[:-1]:
            node = node[int(part)] if isinstance(node, list) else node[part]
        node[parts[-1]] = text
    return doc


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--symbol', required=True)
    parser.add_argument('--overlay', type=Path, required=True)
    parser.add_argument('--publish-html', action='store_true')
    args = parser.parse_args()
    if not args.symbol.isalnum(): raise ValueError('invalid_symbol')
    root = Path(__file__).resolve().parents[1]
    folder = root / 'output' / args.symbol.upper()
    with _exclusive_read_lock(folder / 'adaptive_publish.lock'):
        payload = json.loads((folder / 'latest.json').read_text(encoding='utf8'))
        overlay = json.loads(args.overlay.read_text(encoding='utf8'))
        doc = editorial_document(payload, overlay)
        markdown = render_document(doc, reader=True)
        (folder / 'reader.md').write_text(markdown, encoding='utf8')
        write_analysis_html(markdown, folder / 'reader.html', symbol=args.symbol)
        if args.publish_html:
            def cloud(*parts):
                return subprocess.run([require_gcloud(), 'storage', *parts], check=True,
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf8',
                    timeout=120, creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0).stdout
            uri = f'gs://{TEST_BUCKET}/{args.symbol.upper()}/latest'
            generation = cloud('objects', 'describe', uri + '.html', '--format=value(generation)').strip()
            if not generation.isdigit(): raise ValueError('missing_html_generation')
            remote = json.loads(cloud('cat', uri + '.json'))
            if (remote.get('analysis_markdown') != payload['analysis_markdown']
                    or remote.get('generated_at') != payload.get('generated_at')):
                raise ValueError('remote_report_changed')
            previous = cloud('cat', uri + '.html')
            local_html = (folder / 'latest.html').read_text(encoding='utf8')
            if previous.replace('\r\n', '\n') != local_html.replace('\r\n', '\n'):
                raise ValueError('remote_html_differs_from_local_snapshot')
            stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%f')
            backup = folder / 'presentation-backups' / stamp
            backup.mkdir(parents=True)
            (backup / 'latest.html').write_text(previous, encoding='utf8')
            cloud('cp', str(folder / 'reader.html'), uri + '.html',
                  '--content-type=text/html; charset=utf-8', '--cache-control=no-cache',
                  '--if-generation-match=' + generation)
            actual = cloud('cat', uri + '.html')
            expected = (folder / 'reader.html').read_text(encoding='utf8')
            if actual.replace('\r\n', '\n') != expected.replace('\r\n', '\n'):
                raise RuntimeError('html_readback_mismatch')
            shutil.copy2(folder / 'reader.html', folder / 'latest.html')
            print('Published and verified HTML only; financial JSON/Markdown/anchors unchanged.')
        print('Reader:', folder / 'reader.html')


if __name__ == '__main__': main()
