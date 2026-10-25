"""Resolve runner authority from a confirmed publication when available."""
import json
from src.local_runner.publication_contract import read_committed
from src.local_runner.gcs_uploader import TEST_BUCKET


def committed_payload(symbol, kind):
    from src.local_runner.analysis_state import read_text_gcs
    body, manifest = read_committed(lambda name: read_text_gcs(f'gs://{TEST_BUCKET}/{name}'),
                                    symbol.strip().upper(), kind)
    return (json.loads(body), manifest) if manifest else (None, None)
