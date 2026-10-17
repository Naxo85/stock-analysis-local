"""Apply portfolio and Mercado-universe changes requested from Google Sheets."""

from __future__ import annotations

import argparse
import copy
import json
import os
import subprocess
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
CONTROLLER_ROOT = REPO_ROOT / "gcp_services" / "stock_controller"
CONTROLLER_SRC = CONTROLLER_ROOT / "src"
if str(CONTROLLER_SRC) not in sys.path:
    sys.path.insert(0, str(CONTROLLER_SRC))

from stock_analysis.controller.market_sheet import GoogleSheetsRestClient
from stock_analysis.controller.portfolio_sheet import (
    build_group_shot_strip_requests,
    build_group_summary_position_requests,
    build_portfolio_format_requests,
)
from stock_analysis.controller.sheet_layout import (
    resolve_balanced_table_geometry,
    validate_market_sheet_layout,
)
from stock_analysis.controller.sheet_structure import (
    build_structure_requests,
    plan_structure_changes,
)
from stock_analysis.controller.sheet_tickers import (
    resolve_ticker_rows,
    ticker_read_ranges,
)

from src.local_runner.gcs_uploader import CONTENT_TYPE_JSON, require_gcloud


LAYOUT_PATH = CONTROLLER_ROOT / "config" / "market_sheet_layout.json"
PORTFOLIO_PATH = CONTROLLER_ROOT / "config" / "portfolio.json"
SYSTEM_BUCKET = "stock-analysis-system-naxo85"
REPORTS_BUCKET = "stock-analysis-reports-naxo85"
RUNTIME_LAYOUT_URI = (
    f"gs://{SYSTEM_BUCKET}/runtime/config/market_sheet_layout.json"
)
RUNTIME_PORTFOLIO_URI = (
    f"gs://{SYSTEM_BUCKET}/runtime/config/portfolio.json"
)
MARKET_TICKERS_URI = f"gs://{REPORTS_BUCKET}/config/tickers_market.json"
MAX_OPERATION_HISTORY = 100

ACTION_BUY = "buy"
ACTION_SELL = "sell"
ACTION_REMOVE = "remove"


def reconcile_portfolio_snapshot(
    layout_payload: dict[str, Any],
    portfolio_payload: dict[str, Any],
    snapshot: dict[str, int],
    *,
    protected_tickers: set[str] | None = None,
) -> dict[str, Any]:
    """Reconcile colors without reverting operations newer than the snapshot."""
    if not snapshot:
        return copy.deepcopy(portfolio_payload)
    universe = {
        str(ticker).strip().upper()
        for group in layout_payload["groups"]
        for ticker in group["tickers"]
    }
    protected = protected_tickers or set()
    missing = sorted(universe - set(snapshot) - protected)
    extra = sorted(set(snapshot) - universe - protected)
    if missing or extra:
        raise ValueError(
            f"portfolio_snapshot_incomplete: missing={missing} extra={extra}"
        )
    portfolio = copy.deepcopy(portfolio_payload)
    positions = {
        str(symbol).strip().upper(): int(shots)
        for symbol, shots in portfolio.get("positions", {}).items()
        if int(shots) > 0
    }
    for symbol, observed in snapshot.items():
        if symbol in protected:
            continue
        if observed == 0:
            positions.pop(symbol, None)
        elif observed == 1:
            positions[symbol] = 1
        else:
            positions[symbol] = max(positions.get(symbol, 0), 2)
    portfolio["positions"] = positions
    return portfolio


def snapshot_protected_tickers(
    history: list[dict[str, Any]], snapshot_at: str | None
) -> set[str]:
    if not snapshot_at:
        # Undated diagnostic snapshots cannot supersede committed operations.
        return {str(item["ticker"]).upper() for item in history}
    captured = datetime.fromisoformat(snapshot_at.replace("Z", "+00:00"))
    if captured.tzinfo is None:
        raise ValueError("portfolio_snapshot_timestamp_requires_timezone")
    return {
        str(item["ticker"]).upper()
        for item in history
        if item.get("publication_pending")
        or datetime.fromisoformat(
            (item.get("published_at") or item["applied_at"]).replace("Z", "+00:00")
        ) >= captured
    }


def mutate_tracking_state(
    layout_payload: dict[str, Any],
    portfolio_payload: dict[str, Any],
    *,
    action: str,
    ticker: str,
    group_id: str | None,
    observed_shots: int,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Return updated config payloads without performing I/O."""
    layout = copy.deepcopy(layout_payload)
    portfolio = copy.deepcopy(portfolio_payload)
    normalized = ticker.strip().upper()
    if not normalized:
        raise ValueError("ticker_required")
    if observed_shots < 0:
        raise ValueError("observed_shots_must_be_non_negative")

    group_by_id = {str(group["id"]): group for group in layout["groups"]}
    ticker_group = next(
        (
            group
            for group in layout["groups"]
            if normalized in {
                str(value).strip().upper() for value in group["tickers"]
            }
        ),
        None,
    )
    positions = {
        str(symbol).strip().upper(): int(shots)
        for symbol, shots in portfolio.get("positions", {}).items()
        if int(shots) > 0
    }
    structure_changed = False

    if action == ACTION_BUY:
        if ticker_group is None:
            if not group_id or group_id not in group_by_id:
                raise ValueError("group_required_for_new_ticker")
            ticker_group = group_by_id[group_id]
            ticker_group["tickers"].append(normalized)
            structure_changed = True
        current = max(positions.get(normalized, 0), observed_shots)
        positions[normalized] = current + 1
    elif action == ACTION_SELL:
        if ticker_group is None:
            raise ValueError("ticker_not_tracked")
        current = max(positions.get(normalized, 0), observed_shots)
        if current < 1:
            raise ValueError("ticker_has_no_open_shots")
        if current == 1:
            positions.pop(normalized, None)
        else:
            positions[normalized] = current - 1
    elif action == ACTION_REMOVE:
        if ticker_group is not None:
            ticker_group["tickers"] = [
                value
                for value in ticker_group["tickers"]
                if str(value).strip().upper() != normalized
            ]
            structure_changed = True
        positions.pop(normalized, None)
    else:
        raise ValueError(f"unsupported_tracking_action: {action}")

    portfolio["updated_at"] = date.today().isoformat()
    portfolio["positions"] = positions
    result = {
        "ticker": normalized,
        "shots": positions.get(normalized, 0),
        "tracked": any(
            normalized in {
                str(value).strip().upper() for value in group["tickers"]
            }
            for group in layout["groups"]
        ),
        "group_id": str(ticker_group["id"]) if ticker_group is not None else None,
        "structure_changed": structure_changed,
    }
    return layout, portfolio, result


def apply_tracking_change(
    *,
    action: str,
    ticker: str,
    group_id: str | None,
    observed_shots: int,
    portfolio_snapshot: dict[str, int],
    command_id: str,
    publish: bool,
    snapshot_at: str | None = None,
) -> dict[str, Any]:
    layout_payload = _read_json(LAYOUT_PATH)
    portfolio_payload = _read_json(PORTFOLIO_PATH)
    history = list(portfolio_payload.get("applied_tracking_commands") or [])
    prior = next(
        (item for item in history if item.get("command_id") == command_id),
        None,
    )

    is_new_operation = prior is None
    if is_new_operation:
        protected = snapshot_protected_tickers(history, snapshot_at)
        portfolio_payload = reconcile_portfolio_snapshot(
            layout_payload, portfolio_payload, portfolio_snapshot,
            protected_tickers=protected,
        )
        layout_payload, portfolio_payload, result = mutate_tracking_state(
            layout_payload,
            portfolio_payload,
            action=action,
            ticker=ticker,
            group_id=group_id,
            observed_shots=0 if ticker.upper() in protected else observed_shots,
        )
    else:
        result = dict(prior["result"])

    if is_new_operation:
        history.append(
            {
                "command_id": command_id,
                "action": action,
                "ticker": result["ticker"],
                "applied_at": datetime.now(timezone.utc).isoformat(),
                "publication_pending": publish,
                "result": result,
            }
        )
        portfolio_payload["applied_tracking_commands"] = history[
            -MAX_OPERATION_HISTORY:
        ]
        _write_json_atomic(LAYOUT_PATH, layout_payload)
        _write_json_atomic(PORTFOLIO_PATH, portfolio_payload)

    if publish:
        _upload_runtime_state(layout_payload, portfolio_payload)
        layout = _resolve_layout_payload(layout_payload)
        if result["structure_changed"]:
            _reconcile_structure(layout)
        _publish_portfolio(layout, portfolio_payload["positions"])
        for item in portfolio_payload.get("applied_tracking_commands", []):
            if item["command_id"] == command_id:
                item["publication_pending"] = False
                item["published_at"] = datetime.now(timezone.utc).isoformat()
        _write_json_atomic(PORTFOLIO_PATH, portfolio_payload)
        runtime_path = REPO_ROOT / "logs" / "market_tracking" / "runtime" / "portfolio.json"
        _write_json_atomic(runtime_path, portfolio_payload)
        subprocess.run(
            [require_gcloud(), "storage", "cp",
             f"--content-type={CONTENT_TYPE_JSON}", str(runtime_path),
             RUNTIME_PORTFOLIO_URI],
            check=True, timeout=90,
        )

    return result


def _resolve_layout_payload(payload: dict[str, Any]) -> dict[str, Any]:
    layout = copy.deepcopy(payload)
    resolve_balanced_table_geometry(layout)
    validate_market_sheet_layout(layout)
    return layout


def _reconcile_structure(layout: dict[str, Any]) -> None:
    client = GoogleSheetsRestClient(
        service_account=layout["spreadsheet"].get("service_account")
    )
    spreadsheet_id = layout["spreadsheet"]["spreadsheet_id"]
    for _ in range(3):
        state = client.get_spreadsheet(spreadsheet_id)
        changes = plan_structure_changes(layout, state)
        if not changes:
            return
        client.batch_update(
            spreadsheet_id,
            build_structure_requests(layout, changes),
        )
    state = client.get_spreadsheet(spreadsheet_id)
    remaining = plan_structure_changes(layout, state)
    if remaining:
        raise RuntimeError(
            f"market_structure_did_not_converge: {len(remaining)} changes"
        )


def _publish_portfolio(
    layout: dict[str, Any],
    positions: dict[str, int],
) -> None:
    client = GoogleSheetsRestClient(
        service_account=layout["spreadsheet"].get("service_account")
    )
    spreadsheet_id = layout["spreadsheet"]["spreadsheet_id"]
    values = client.batch_get_values(
        spreadsheet_id,
        ticker_read_ranges(layout),
    )
    ticker_rows = resolve_ticker_rows(layout, values)
    requests = [
        *build_portfolio_format_requests(
            layout,
            positions,
            ticker_rows=ticker_rows,
        ),
        *build_group_shot_strip_requests(
            layout,
            positions,
            ticker_rows=ticker_rows,
        ),
        *build_group_summary_position_requests(layout, positions),
    ]
    client.batch_update(spreadsheet_id, requests)


def _upload_runtime_state(
    layout_payload: dict[str, Any],
    portfolio_payload: dict[str, Any],
) -> None:
    gcloud = require_gcloud()
    runtime_dir = REPO_ROOT / "logs" / "market_tracking" / "runtime"
    runtime_dir.mkdir(parents=True, exist_ok=True)
    layout_path = runtime_dir / "market_sheet_layout.json"
    portfolio_path = runtime_dir / "portfolio.json"
    tickers_path = runtime_dir / "tickers_market.json"
    _write_json_atomic(layout_path, layout_payload)
    _write_json_atomic(portfolio_path, portfolio_payload)

    tickers = [
        str(ticker).strip().upper()
        for group in layout_payload["groups"]
        for ticker in group["tickers"]
    ]
    ticker_payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_sheet": "Mercado",
        "profile": "market",
        "count": len(tickers),
        "tickers": tickers,
        "ticker_records": [
            {
                "ticker": ticker,
                "owned": int(portfolio_payload["positions"].get(ticker, 0)) > 0,
                "ownership_source": (
                    "portfolio.positions"
                    if int(portfolio_payload["positions"].get(ticker, 0)) > 0
                    else None
                ),
            }
            for ticker in tickers
        ],
    }
    _write_json_atomic(tickers_path, ticker_payload)
    for source, destination in (
        (layout_path, RUNTIME_LAYOUT_URI),
        (portfolio_path, RUNTIME_PORTFOLIO_URI),
        (tickers_path, MARKET_TICKERS_URI),
    ):
        subprocess.run(
            [
                gcloud,
                "storage",
                "cp",
                f"--content-type={CONTENT_TYPE_JSON}",
                str(source),
                destination,
            ],
            check=True,
            timeout=90,
        )


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Update Mercado tracking and portfolio shots"
    )
    parser.add_argument(
        "--action",
        required=True,
        choices=(ACTION_BUY, ACTION_SELL, ACTION_REMOVE),
    )
    parser.add_argument("--ticker", required=True)
    parser.add_argument("--group-id")
    parser.add_argument("--observed-shots", type=int, default=0)
    parser.add_argument("--portfolio-snapshot-json", default="{}")
    parser.add_argument(
        "--snapshot-at", default=os.environ.get("PORTFOLIO_SNAPSHOT_AT")
    )
    parser.add_argument(
        "--command-id",
        default=os.environ.get("ANALYSIS_COMMAND_ID"),
    )
    parser.add_argument("--no-publish", action="store_true")
    arguments = parser.parse_args()
    if not arguments.command_id:
        parser.error("--command-id or ANALYSIS_COMMAND_ID is required")
    try:
        snapshot = json.loads(arguments.portfolio_snapshot_json)
    except json.JSONDecodeError as exc:
        parser.error(f"invalid --portfolio-snapshot-json: {exc}")
    if not isinstance(snapshot, dict):
        parser.error("--portfolio-snapshot-json must be an object")
    arguments.portfolio_snapshot = {
        str(symbol).strip().upper(): int(shots)
        for symbol, shots in snapshot.items()
    }
    return arguments


def main() -> None:
    arguments = _parse_args()
    result = apply_tracking_change(
        action=arguments.action,
        ticker=arguments.ticker,
        group_id=arguments.group_id,
        observed_shots=arguments.observed_shots,
        portfolio_snapshot=arguments.portfolio_snapshot,
        command_id=arguments.command_id,
        publish=not arguments.no_publish,
        snapshot_at=arguments.snapshot_at,
    )
    print(
        "OK market_tracking "
        f"ticker={result['ticker']} shots={result['shots']} "
        f"tracked={result['tracked']} "
        f"structure_changed={result['structure_changed']}"
    )


if __name__ == "__main__":
    main()
