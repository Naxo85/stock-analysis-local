from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from stock_analysis.controller.market_sheet import GoogleSheetsRestClient
from stock_analysis.controller.sheet_layout import load_market_sheet_layout
from stock_analysis.controller.sheet_layout import build_column_width_apply_requests
from stock_analysis.controller.sheet_structure import (
    build_panel_font_apply_requests,
    build_table_font_apply_requests,
    build_structure_requests,
    plan_structure_changes,
)


def _load_state(
    path: Path | None,
    client: GoogleSheetsRestClient,
    spreadsheet_id: str,
) -> dict[str, Any]:
    if path is not None:
        return json.loads(path.read_text(encoding="utf-8"))
    return client.get_spreadsheet(spreadsheet_id)


def _print_plan(changes: list[dict[str, Any]]) -> None:
    print(f"PLAN changes={len(changes)}")
    for change in changes:
        print(f"{change['action'].upper()} {change['target']}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Plan or reconcile Mercado structure")
    parser.add_argument(
        "mode", choices=("plan", "apply", "render", "apply-font", "apply-layout")
    )
    parser.add_argument("--state", type=Path, help="read a captured spreadsheet state")
    parser.add_argument("--requests-output", type=Path)
    arguments = parser.parse_args()

    layout = load_market_sheet_layout()
    spreadsheet_id = layout["spreadsheet"]["spreadsheet_id"]
    client = GoogleSheetsRestClient(
        service_account=layout["spreadsheet"].get("service_account")
    )
    state = _load_state(arguments.state, client, spreadsheet_id)
    if arguments.mode in {"apply-font", "apply-layout"}:
        if arguments.state is not None:
            parser.error(f"{arguments.mode} cannot use --state; live state is required")
        sheet_id = layout["sheet"]["sheet_id"]
        requests = [
            *build_table_font_apply_requests(sheet_id, layout),
            *build_panel_font_apply_requests(sheet_id, layout),
        ]
        if arguments.mode == "apply-layout":
            requests = [*build_column_width_apply_requests(sheet_id, layout), *requests]
        client.batch_update(spreadsheet_id, requests)
        print(
            f"APPLIED mode={arguments.mode} table_font="
            f"{layout['table_template']['font_size']} "
            f"panel_font={layout['general_panel']['font_size']} "
            f"requests={len(requests)}"
        )
        return
    changes = (
        [{"action": "render_layout", "target": layout["sheet"]["title"]}]
        if arguments.mode == "render"
        else plan_structure_changes(layout, state)
    )
    _print_plan(changes)
    requests = build_structure_requests(layout, changes)

    if arguments.requests_output is not None:
        arguments.requests_output.parent.mkdir(parents=True, exist_ok=True)
        arguments.requests_output.write_text(
            json.dumps(requests, indent=2), encoding="utf-8"
        )
    if arguments.mode == "plan" or not changes:
        return
    if arguments.state is not None:
        parser.error("apply cannot use --state; live state is required")

    for pass_number in range(1, 4):
        client.batch_update(spreadsheet_id, requests)
        state = client.get_spreadsheet(spreadsheet_id)
        changes = plan_structure_changes(layout, state)
        if not changes:
            print(f"APPLIED passes={pass_number}")
            return
        requests = build_structure_requests(layout, changes)
    raise RuntimeError(f"structure did not converge: {len(changes)} changes remain")


if __name__ == "__main__":
    main()
