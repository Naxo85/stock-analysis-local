from __future__ import annotations

import argparse
import hashlib
import json
import os
from dataclasses import replace
from pathlib import Path
from typing import Any

from stock_analysis.analysis_worker.reports import (
    GcsAnalysisReportStore,
    parse_analysis_report,
)
from stock_analysis.controller.analysis_sheet import (
    analysis_read_ranges,
    build_analysis_value_requests,
    build_strength_border_requests,
    resolve_ticker_rows_and_prices,
    resolve_visible_scores,
)
from stock_analysis.controller.global_sheet_sort import (
    build_global_sort_control_requests,
    build_global_sort_plan,
    global_sort_read_ranges,
)
from stock_analysis.controller.market_sheet import GoogleSheetsRestClient
from stock_analysis.controller.sheet_layout import (
    build_table_border_apply_requests,
    load_market_sheet_layout,
)


def configured_universe(layout: dict[str, Any]) -> tuple[str, ...]:
    return tuple(
        dict.fromkeys(
            ticker for block in layout["blocks"] for ticker in block["tickers"]
        )
    )


def effective_sync_version(report_version: str, layout: dict[str, Any]) -> str:
    """Invalidate a published projection when its layout or links change."""
    projection = {
        "presentation_version": 15,
        "schema_version": layout.get("schema_version"),
        "headers": layout["table_template"]["headers"],
        "show_resistance": layout['table_template'].get('show_resistance', True),
        "ticker_column_offset": layout["table_template"].get(
            "ticker_column_offset", 0
        ),
        "analysis_start_column_offset": layout["table_template"].get(
            "analysis_start_column_offset", 9
        ),
        "report_link": layout["links"]["report"],
        "global_sort": layout["global_sort"],
        "blocks": [
            {
                "id": block["id"],
                "header_row": block["header_row"],
                "start_column": block["start_column"],
                "end_column": block["end_column"],
                "tickers": block["tickers"],
            }
            for block in layout["blocks"]
        ],
        "groups": [
            {"id": group["id"], "tickers": group["tickers"]}
            for group in layout["groups"]
        ],
    }
    payload = report_version + "\n" + json.dumps(
        projection, sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()



def build_analysis_records(
    universe: tuple[str, ...],
    payloads: dict[str, dict[str, Any]],
    *,
    report_generations: dict[str, str],
    previous_state: dict[str, Any],
    visible_scores: dict[str, float],
    report_url_template: str,
) -> tuple[dict[str, Any], dict[str, str], dict[str, dict[str, str | None]]]:
    previous_generations = previous_state.get("report_generations")
    if not isinstance(previous_generations, dict):
        previous_generations = {}
    previous_presentations = previous_state.get("score_presentations")
    if not isinstance(previous_presentations, dict):
        previous_presentations = {}

    records: dict[str, Any] = {}
    failures: dict[str, str] = {}
    presentations: dict[str, dict[str, str | None]] = {}
    for ticker in universe:
        try:
            unchanged = (
                previous_state.get("score_presentation_version") == 2
                and
                previous_generations.get(ticker) == report_generations.get(ticker)
                and isinstance(previous_presentations.get(ticker), dict)
            )
            record = parse_analysis_report(
                ticker,
                payloads[ticker],
                report_url_template=report_url_template,
                previous_score_override=(
                    None if not previous_generations else visible_scores.get(ticker)
                ),
            )
            if unchanged:
                saved = previous_presentations[ticker]
                record = replace(
                    record,
                    score_background=saved.get("background"),
                    score_note=str(saved.get("note") or ""),
                )
            records[ticker] = record
            presentations[ticker] = {
                "background": record.score_background,
                "note": record.score_note,
            }
        except (KeyError, TypeError, ValueError) as error:
            failures[ticker] = f"{type(error).__name__}: {error}"
    return records, failures, presentations


def run(
    *,
    publish: bool,
    force: bool,
    requests_output: Path | None = None,
    bucket_name: str | None = None,
    store: GcsAnalysisReportStore | None = None,
    sheets_client: GoogleSheetsRestClient | None = None,
    layout: dict[str, Any] | None = None,
) -> dict[str, Any]:
    layout = layout if layout is not None else load_market_sheet_layout()
    universe = configured_universe(layout)
    resolved_bucket = (
        bucket_name
        or os.environ.get("MARKET_HISTORY_BUCKET")
        or layout["analysis_sync"]["mirror_bucket"]
    )
    report_store = store or GcsAnalysisReportStore(
        resolved_bucket,
        prefix=layout["analysis_sync"]["mirror_prefix"],
    )
    index = report_store.index(universe)
    sync_version = effective_sync_version(index.version, layout)
    previous_state = report_store.sync_state()
    if (
        not force
        and previous_state.get("schema_version") == 2
        and str(previous_state.get("version") or "") == sync_version
    ):
        return {
            "status": "skipped",
            "reason": "analysis_reports_unchanged",
            "version": sync_version,
        }

    client = sheets_client or GoogleSheetsRestClient(
        service_account=layout["spreadsheet"].get("service_account")
    )
    value_ranges = client.batch_get_values(
        layout["spreadsheet"]["spreadsheet_id"],
        analysis_read_ranges(layout),
        value_render_option="UNFORMATTED_VALUE",
    )
    ticker_rows, prices = resolve_ticker_rows_and_prices(layout, value_ranges)
    visible_scores = resolve_visible_scores(layout, value_ranges)
    payloads = report_store.load(index)
    report_generations = {
        ticker: str(((index.publications or {}).get(ticker) or {}).get("version") or getattr(blob, "generation", "") or "")
        for ticker, blob in index.blobs.items()
    }
    records, failures, score_presentations = build_analysis_records(
        universe,
        payloads,
        report_generations=report_generations,
        previous_state=previous_state,
        visible_scores=visible_scores,
        report_url_template=layout["links"]["report"],
    )
    requires_complete = layout["analysis_sync"].get(
        "requires_complete_universe", True
    )
    if failures and requires_complete:
        detail = "; ".join(f"{ticker}={error}" for ticker, error in failures.items())
        raise RuntimeError(f"refusing partial analysis publish: {detail}")

    spreadsheet = client.get_spreadsheet(
        layout["spreadsheet"]["spreadsheet_id"],
        include_grid_data=True,
        ranges=global_sort_read_ranges(layout),
    )
    sort_plan = build_global_sort_plan(
        layout,
        spreadsheet,
        sort_values={
            "score": {ticker: (record.thesis_score if "Tesis" in layout["table_template"]["headers"] else record.score) for ticker, record in records.items()},
            "setup_score": {ticker: record.setup_score for ticker, record in records.items()},
        },
    )
    ticker_rows = sort_plan.ticker_rows
    requests = [
        *sort_plan.requests,
        *build_analysis_value_requests(
            layout,
            records,
            ticker_rows=ticker_rows,
            prices=prices,
            held_tickers=sort_plan.held_tickers,
            allow_missing=not requires_complete,
        ),
        *build_global_sort_control_requests(layout, sort_plan.selection),
        *build_table_border_apply_requests(layout["sheet"]["sheet_id"], layout),
        *build_strength_border_requests(
            layout,
            records,
            ticker_rows=ticker_rows,
        ),
    ]
    if requests_output:
        import json

        requests_output.parent.mkdir(parents=True, exist_ok=True)
        requests_output.write_text(
            json.dumps(requests, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    if publish:
        client.batch_update(layout["spreadsheet"]["spreadsheet_id"], requests)
        report_store.mark_synced(
            sync_version,
            len(records),
            report_generations=report_generations,
            score_presentations=score_presentations,
            support_validity={ticker: {'entry': record.entry_support_validity,
                                      'washout': record.washout_support_validity}
                              for ticker, record in records.items()},
        )
    return {
        "status": (
            "partial" if publish and failures else "published" if publish else "dry_run"
        ),
        "tickers": len(records),
        "missing": sorted(failures),
        "requests": len(requests),
        "version": sync_version,
        "sort": sort_plan.selection,
        "reordered": sort_plan.changed,
        "strengths": sum(
            record.entry_strength is not None or record.washout_strength is not None
            for record in records.values()
        ),
    }



def main() -> None:
    parser = argparse.ArgumentParser(
        description="Synchronize validated analysis reports into Mercado"
    )
    parser.add_argument("--publish", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--requests-output", type=Path)
    parser.add_argument("--bucket")
    arguments = parser.parse_args()
    result = run(
        publish=arguments.publish,
        force=arguments.force,
        requests_output=arguments.requests_output,
        bucket_name=arguments.bucket,
    )
    print(
        "ANALYSIS_SYNC "
        + " ".join(f"{key}={value}" for key, value in result.items())
    )


if __name__ == "__main__":
    main()
