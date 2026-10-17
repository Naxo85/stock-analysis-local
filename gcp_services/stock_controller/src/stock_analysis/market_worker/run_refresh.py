from __future__ import annotations

import argparse
import json
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

from stock_analysis.contracts.market import MarketSnapshot
from stock_analysis.controller.global_sheet_sort import (
    build_global_sort_control_requests,
    build_global_sort_plan,
    global_sort_read_ranges,
)
from stock_analysis.controller.group_summary_sort import (
    build_sorted_group_summary_requests,
    group_summary_read_range,
)
from stock_analysis.controller.market_sheet import (
    GoogleSheetsRestClient,
    build_benchmark_value_requests,
    build_general_panel_requests,
    build_market_value_requests,
)
from stock_analysis.controller.analysis_sheet import (
    build_live_proximity_background_requests,
    build_strength_border_requests_for_values,
)
from stock_analysis.controller.sheet_layout import (
    build_alignment_apply_requests,
    build_column_width_apply_requests,
    build_table_border_apply_requests,
    load_market_sheet_layout,
)
from stock_analysis.controller.sheet_tickers import (
    resolve_ticker_rows,
    ticker_read_ranges,
)
from stock_analysis.market_worker.general_market import (
    build_general_market_overview,
    fetch_general_market_inputs,
)
from stock_analysis.market_worker.metrics import (
    calculate_benchmark_metrics,
    calculate_universe_metrics,
    drawdown_from_intraday_high,
)
from stock_analysis.market_worker.providers import (
    TradierMarketDataProvider,
    tradier_token_from_environment,
)
from stock_analysis.market_worker.session import us_market_session


def configured_universe(layout: dict) -> tuple[str, ...]:
    return tuple(
        dict.fromkeys(ticker for block in layout["blocks"] for ticker in block["tickers"])
    )


def configured_benchmarks(layout: dict) -> tuple[str, ...]:
    return tuple(
        dict.fromkeys(group["benchmark"] for group in layout["groups"])
    )


def run(
    *,
    publish: bool,
    force: bool,
    output: Path | None = None,
    requests_output: Path | None = None,
    now: datetime | None = None,
    history_cache_dir: Path | None = None,
) -> MarketSnapshot | None:
    layout = load_market_sheet_layout()
    session = us_market_session(now)
    if not force and not session.open:
        print(f"SKIP market session={session.name} now_et={session.now_et.isoformat()}")
        return None

    universe = configured_universe(layout)
    benchmarks_universe = configured_benchmarks(layout)
    benchmark_config = layout["benchmark_metrics"]
    market_universe = tuple(dict.fromkeys((*universe, *benchmarks_universe, "QQQ")))
    provider = TradierMarketDataProvider(
        tradier_token_from_environment(), cache_dir=history_cache_dir
    )
    data, failures = provider.fetch_universe(
        market_universe,
        market_date=session.now_et.date(),
        prefer_extended=session.name in {"pre-market", "post-market"},
    )
    ticker_data = {ticker: data[ticker] for ticker in universe if ticker in data}
    benchmark_data = {
        ticker: data[ticker]
        for ticker in (*benchmarks_universe, "QQQ")
        if ticker in data
    }
    metrics = calculate_universe_metrics(
        ticker_data, market_date=session.now_et.date()
    )
    benchmarks = calculate_benchmark_metrics(
        benchmark_data,
        tickers=(*benchmarks_universe, "QQQ"),
        market_date=session.now_et.date(),
        return_sessions=benchmark_config["return_window_sessions"],
    )
    qqq = next((item for item in benchmarks if item.ticker == "QQQ"), None)
    qqq_data = benchmark_data.get("QQQ")
    if qqq is not None and qqq_data is not None:
        qqq = replace(
            qqq,
            drawdown=drawdown_from_intraday_high(
                qqq_data.quote.price, qqq_data.daily_bars
            ),
        )
    general_inputs = fetch_general_market_inputs(
        layout["general_panel"]["analysis_status_bucket"],
        status_prefix=layout["general_panel"]["analysis_status_prefix"],
    )
    general = build_general_market_overview(qqq, general_inputs)
    snapshot = MarketSnapshot(
        schema_version=3,
        generated_at=datetime.now(timezone.utc),
        universe=universe,
        metrics=metrics,
        failures=failures,
        benchmarks=benchmarks,
        general=general,
    )

    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(snapshot.as_dict(), indent=2), encoding="utf-8")

    client = None
    ticker_rows = None
    sort_requests = []
    sort_selection = layout["global_sort"]["default"]
    if publish:
        if failures:
            raise RuntimeError(
                f"refusing partial publish: {len(failures)} ticker failures"
            )
        client = GoogleSheetsRestClient(
            service_account=layout["spreadsheet"].get("service_account")
        )
        value_ranges = client.batch_get_values(
            layout["spreadsheet"]["spreadsheet_id"], ticker_read_ranges(layout)
        )
        resolve_ticker_rows(layout, value_ranges)
        spreadsheet = client.get_spreadsheet(
            layout["spreadsheet"]["spreadsheet_id"],
            include_grid_data=True,
            ranges=[*global_sort_read_ranges(layout), group_summary_read_range(layout)],
        )
        sort_plan = build_global_sort_plan(
            layout,
            spreadsheet,
            sort_values={
                "strength": {item.ticker: item.strength for item in snapshot.metrics}
            },
        )
        ticker_rows = sort_plan.ticker_rows
        sort_requests = sort_plan.requests
        sort_selection = sort_plan.selection

    support_validity = {}
    if publish:
        from stock_analysis.analysis_worker.reports import load_support_validity
        try:
            support_validity = load_support_validity(
                layout['analysis_sync']['mirror_bucket'], layout['analysis_sync']['mirror_prefix'])
        except Exception as error:
            # A display read cannot stop quote publication or invent a margin.
            print(f'WARN support extent unavailable; green only inside ranges: {type(error).__name__}')

    value_requests = build_market_value_requests(
        layout, snapshot, ticker_rows=ticker_rows
    )
    benchmark_requests = (
        build_sorted_group_summary_requests(layout, snapshot, spreadsheet)
        if publish
        else build_benchmark_value_requests(layout, snapshot)
    )
    general_requests = build_general_panel_requests(layout, snapshot)
    sort_control_requests = build_global_sort_control_requests(
        layout, sort_selection
    )
    width_requests = build_column_width_apply_requests(
        layout["sheet"]["sheet_id"], layout
    )
    alignment_requests = build_alignment_apply_requests(
        layout["sheet"]["sheet_id"], layout
    )
    border_requests = build_table_border_apply_requests(
        layout["sheet"]["sheet_id"], layout
    )
    requests = [
        *sort_requests,
        *value_requests,
        *benchmark_requests,
        *general_requests,
        *sort_control_requests,
        *width_requests,
        *alignment_requests,
        *border_requests,
        *(
            build_live_proximity_background_requests(
                layout,
                sort_plan.analysis_levels,
                ticker_rows=ticker_rows,
                prices={item.ticker: item.price for item in snapshot.metrics},
                held_tickers=sort_plan.held_tickers,
                support_validity=support_validity,
            )
            if publish and ticker_rows is not None
            else []
        ),
        *(
            build_strength_border_requests_for_values(
                layout,
                sort_plan.support_strengths,
                ticker_rows=ticker_rows,
            )
            if publish and ticker_rows is not None
            else []
        ),
    ]
    if requests_output:
        requests_output.parent.mkdir(parents=True, exist_ok=True)
        requests_output.write_text(json.dumps(requests, indent=2), encoding="utf-8")
    if publish:
        assert client is not None
        client.batch_update(layout["spreadsheet"]["spreadsheet_id"], requests)
        print(
            f"OK published={len(metrics)} benchmarks={len(benchmarks)} "
            f"general={snapshot.general is not None} "
            f"sort={sort_selection!r} reordered={bool(sort_requests)} "
            f"requests={len(requests)}"
        )
    else:
        print(
            f"DRY-RUN metrics={len(metrics)} benchmarks={len(benchmarks)} "
            f"general={snapshot.general is not None} "
            f"sort={sort_selection!r} "
            f"failures={len(failures)} "
            f"requests={len(requests)}"
        )
    return snapshot


def main() -> None:
    parser = argparse.ArgumentParser(description="Refresh automatic Mercado columns")
    parser.add_argument("--publish", action="store_true")
    parser.add_argument("--force", action="store_true", help="run outside market sessions")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--requests-output", type=Path)
    arguments = parser.parse_args()
    run(
        publish=arguments.publish,
        force=arguments.force,
        output=arguments.output,
        requests_output=arguments.requests_output,
    )


if __name__ == "__main__":
    main()
