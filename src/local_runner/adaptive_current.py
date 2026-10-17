"""Last valid maintained report, separate from the immutable full Sol anchor."""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from src.local_runner.adaptive_cache import reference_key
from src.local_runner.analysis_state import read_text_gcs
from src.local_runner.gcs_uploader import TEST_BUCKET
from src.local_runner.adaptive_policy import timestamp


def current_uri(symbol: str) -> str:
    return f"gs://{TEST_BUCKET}/_analysis_state/{symbol.strip().upper()}/current.json"


def load_current_report(root: Path, symbol: str, anchor: dict) -> dict:
    """Do not quietly lose a Luna update on unavailable/corrupt current state."""
    try:
        raw = read_text_gcs(current_uri(symbol))
        current = json.loads(raw) if raw is not None else None
    except RuntimeError:
        local = root / "data" / "analysis_state" / symbol.strip().upper() / "current.json"
        if not local.exists():
            raise
        current = json.loads(local.read_text(encoding="utf-8"))
    if current is None:
        return anchor
    if not isinstance(current, dict) or current.get("analysis_status") != "ok":
        raise RuntimeError("invalid_maintained_current_state")
    if current.get("sol_anchor_sha256") != reference_key(anchor):
        # A newer full Sol report supersedes any maintenance of an older one.
        a, c = timestamp(anchor.get("generated_at")), timestamp(current.get("last_full_report_at"))
        if a and c and a > c:
            return anchor
        raise RuntimeError("maintained_report_anchor_mismatch")
    if current.get("symbol") != symbol.strip().upper() or not current.get("analysis_markdown"):
        raise RuntimeError("invalid_maintained_current_identity")
    generated = timestamp(current.get("generated_at"))
    full = timestamp(anchor.get("generated_at"))
    if generated is None:
        raise RuntimeError("invalid_maintained_current_timestamp")
    if (generated-datetime.now(timezone.utc)).total_seconds() > 300:
        raise RuntimeError("maintained_current_timestamp_in_future")
    if (timestamp(current.get("last_full_report_at")) != full or full is None
            or generated < full):
        raise RuntimeError("maintained_current_chronology_mismatch")
    return current
