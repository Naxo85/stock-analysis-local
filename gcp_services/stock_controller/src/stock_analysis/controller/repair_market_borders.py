from __future__ import annotations

from stock_analysis.controller.market_sheet import GoogleSheetsRestClient
from stock_analysis.controller.sheet_layout import (
    build_table_border_apply_requests,
    load_market_sheet_layout,
)


def main() -> None:
    layout = load_market_sheet_layout()
    client = GoogleSheetsRestClient(
        service_account=layout["spreadsheet"].get("service_account")
    )
    requests = build_table_border_apply_requests(
        layout["sheet"]["sheet_id"], layout
    )
    client.batch_update(layout["spreadsheet"]["spreadsheet_id"], requests)
    print(f"OK border_requests={len(requests)}")


if __name__ == "__main__":
    main()
