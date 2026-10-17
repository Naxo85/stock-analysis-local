from __future__ import annotations

import argparse

from stock_analysis.controller.market_sheet import GoogleSheetsRestClient
from stock_analysis.controller.group_summary_sort import (
    group_summary_order_from_values,
    group_summary_read_range,
)
from stock_analysis.controller.portfolio_sheet import (
    build_group_shot_strip_requests,
    build_group_summary_position_requests,
    build_portfolio_format_requests,
    update_positions,
)
from stock_analysis.controller.sheet_layout import load_market_sheet_layout
from stock_analysis.controller.sheet_tickers import (
    resolve_ticker_rows,
    ticker_read_ranges,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Update portfolio ticker markers")
    parser.add_argument("--set", action="append", default=[], metavar="TICKER=SHOTS")
    parser.add_argument("--remove", action="append", default=[])
    parser.add_argument("--publish", action="store_true")
    arguments = parser.parse_args()

    changes = {}
    for value in arguments.set:
        ticker, separator, shots = value.partition("=")
        if not separator:
            parser.error(f"invalid --set value: {value!r}; expected TICKER=SHOTS")
        changes[ticker] = int(shots)
    positions = update_positions(set_shots=changes, remove=arguments.remove)
    layout = load_market_sheet_layout()
    if arguments.publish:
        client = GoogleSheetsRestClient(
            service_account=layout["spreadsheet"].get("service_account")
        )
        value_ranges = client.batch_get_values(
            layout["spreadsheet"]["spreadsheet_id"], ticker_read_ranges(layout)
        )
        ticker_rows = resolve_ticker_rows(layout, value_ranges)
        summary_values = client.batch_get_values(
            layout["spreadsheet"]["spreadsheet_id"],
            [group_summary_read_range(layout)],
        )[0].get("values", [])
        group_order = group_summary_order_from_values(layout, summary_values)
        requests = [
            *build_portfolio_format_requests(
                layout, positions, ticker_rows=ticker_rows
            ),
            *build_group_shot_strip_requests(
                layout, positions, ticker_rows=ticker_rows
            ),
            *build_group_summary_position_requests(
                layout, positions, group_order=group_order
            ),
        ]
        client.batch_update(
            layout["spreadsheet"]["spreadsheet_id"], requests
        )
    else:
        requests = [
            *build_portfolio_format_requests(layout, positions),
            *build_group_shot_strip_requests(layout, positions),
            *build_group_summary_position_requests(layout, positions),
        ]
    print(
        f"OK portfolio={len(positions)} set={len(arguments.set)} "
        f"remove={len(arguments.remove)} publish={arguments.publish}"
    )


if __name__ == "__main__":
    main()
