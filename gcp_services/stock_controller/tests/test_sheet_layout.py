import copy
import unittest

from stock_analysis.controller.sheet_layout import (
    build_alignment_apply_requests,
    build_column_width_apply_requests,
    build_dimension_apply_requests,
    build_table_border_apply_requests,
    a1_row,
    column_to_index,
    desired_column_widths,
    desired_sheet_state,
    drawdown_presentation,
    index_to_column,
    load_market_sheet_layout,
    plan_layout_changes,
    resolve_balanced_table_geometry,
)


class MarketSheetLayoutTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.layout = load_market_sheet_layout()

    def test_column_labels_round_trip(self) -> None:
        for label in ("A", "H", "I", "J", "V", "W", "X", "AA", "AJ"):
            self.assertEqual(index_to_column(column_to_index(label)), label)

    def test_a1_row_parses_single_cell_references(self) -> None:
        self.assertEqual(a1_row("A13"), 13)

    def test_layout_covers_a_to_aj_exactly(self) -> None:
        widths = desired_column_widths(self.layout)
        self.assertEqual(len(widths), 38)
        self.assertEqual(list(widths), [index_to_column(index) for index in range(38)])
        self.assertEqual(
            self.layout["table_template"]["column_widths_px"],
            [20, 80, 74, 64, 80, 64, 70, 66, 80, 92, 92, 92, 64, 64],
        )

    def test_three_surface_geometry_is_declared(self) -> None:
        tables = {block["id"]: block for block in self.layout["blocks"]}
        self.assertEqual((tables["left"]["start_column"], tables["left"]["end_column"]), ("J", "W"))
        self.assertEqual((tables["right"]["start_column"], tables["right"]["end_column"]), ("Y", "AL"))
        self.assertEqual(tables["left"]["header_row"], 3)
        self.assertEqual(tables["right"]["header_row"], 3)
        summary = self.layout["summary_table"]
        self.assertEqual((summary["start_column"], summary["end_column"]), ("A", "H"))
        self.assertEqual(summary["title_row"], 12)
        self.assertEqual(summary["header_row"], 13)
        self.assertEqual(self.layout["sheet"]["spacer_rows"], [])

    def test_ticker_tables_partition_the_group_universe(self) -> None:
        tables = {block["id"]: block for block in self.layout["blocks"]}
        count = sum(len(group['tickers']) for group in self.layout['groups'])
        self.assertEqual(len(tables["left"]["tickers"]), (count + 1) // 2)
        self.assertEqual(len(tables["right"]["tickers"]), count // 2)
        self.assertEqual(set(tables["left"]["tickers"]) & set(tables["right"]["tickers"]), set())
        table_tickers = [ticker for block in self.layout["blocks"] for ticker in block["tickers"]]
        group_tickers = [ticker for group in self.layout["groups"] for ticker in group["tickers"]]
        self.assertEqual(len(table_tickers), count)
        self.assertEqual(set(table_tickers), set(group_tickers))
        self.assertEqual(len(table_tickers), len(set(table_tickers)))

    def test_table_sizes_and_lower_geometry_follow_the_universe_size(self) -> None:
        layout = copy.deepcopy(self.layout)
        layout["groups"][0]["tickers"].append("NEW")

        resolve_balanced_table_geometry(layout)

        self.assertEqual(
            [len(block["tickers"]) for block in layout["blocks"]],
            [(sum(len(g['tickers']) for g in layout['groups']) + 1) // 2, sum(len(g['tickers']) for g in layout['groups']) // 2]
        )
        self.assertEqual(layout["sheet"]["spacer_rows"], [])
        self.assertEqual(layout["summary_table"]["title_row"], 12)
        self.assertEqual(layout["summary_table"]["header_row"], 13)
        self.assertEqual(layout["sheet"]["row_count"], 27)

    def test_group_summary_follows_the_global_sort_control(self) -> None:
        layout = copy.deepcopy(self.layout)
        layout["global_sort"]["control_cell"] = "A15"

        resolve_balanced_table_geometry(layout)

        self.assertEqual(layout["summary_table"]["title_row"], 17)
        self.assertEqual(layout["summary_table"]["header_row"], 18)
        self.assertEqual(layout["sheet"]["row_count"], 32)

    def test_group_summary_has_fourteen_benchmark_rows(self) -> None:
        self.assertEqual(len(self.layout["groups"]), 14)
        benchmarks = [group["benchmark"] for group in self.layout["groups"]]
        self.assertEqual(len(benchmarks), len(set(benchmarks)))
        self.assertIn("DRAM", benchmarks)
        self.assertIn("EUV", benchmarks)
        self.assertIn("QTUP", benchmarks)

    def test_automatic_columns_and_schedule_are_explicit(self) -> None:
        refresh = self.layout["data_refresh"]
        self.assertEqual(
            refresh["session_intervals_minutes"],
            {"regular": 1, "pre-market": 5, "post-market": 5, "closed": 60},
        )
        self.assertEqual(
            refresh["automatic_columns"],
            ["Valor", "Día", "Fuerza", "5d", "20d", "Vol", "DD6M"],
        )
        self.assertFalse(
            self.layout["analysis_sync"]["requires_complete_universe"]
        )

    def test_score_link_targets_the_rendered_html_report(self) -> None:
        self.assertTrue(self.layout["links"]["report"].endswith("format=html"))

    def test_global_sort_layout_has_no_hidden_helpers(self) -> None:
        hidden = desired_sheet_state(self.layout)["hidden_columns"]
        self.assertEqual(hidden, {})
        self.assertTrue(self.layout["sort_policy"]["automatic"])
        self.assertEqual(self.layout["sort_policy"]["owner"], "global_control")
        self.assertEqual(self.layout["global_sort"]["label_cell"], "C9")
        self.assertEqual(self.layout["global_sort"]["control_cell"], "C10")
        self.assertEqual(
            [option["label"] for option in self.layout["global_sort"]["options"]],
            ["Tesis", "Setup", "Sector", "Fuerza"],
        )
        widths = desired_column_widths(self.layout)
        self.assertEqual(widths["A"], 180)
        self.assertEqual(widths["I"], 14)
        self.assertEqual(widths["J"], 20)
        self.assertEqual(widths["X"], 14)
        self.assertEqual(widths["Y"], 20)
        self.assertEqual(widths["AL"], 64)

    def test_clean_state_has_no_drift(self) -> None:
        current = desired_sheet_state(self.layout)
        self.assertEqual(plan_layout_changes(current, self.layout), [])

    def test_manual_width_change_is_reported_as_drift(self) -> None:
        current = copy.deepcopy(desired_sheet_state(self.layout))
        current["column_widths_px"]["A"] = 90
        self.assertIn(
            {"target": "column_widths_px.A", "before": 90, "after": 180},
            plan_layout_changes(current, self.layout),
        )

    def test_apply_requests_enforce_dimensions_without_hidden_helpers(self) -> None:
        requests = build_dimension_apply_requests(20260907, self.layout)
        grid = requests[0]["updateSheetProperties"]["properties"]["gridProperties"]
        self.assertEqual(grid["rowCount"], 27)
        self.assertEqual(grid["columnCount"], 38)
        self.assertEqual(grid["frozenRowCount"], 0)
        self.assertTrue(grid["hideGridlines"])
        central_panel = next(
            request
            for request in build_column_width_apply_requests(20260907, self.layout)
            if request["updateDimensionProperties"]["range"]["startIndex"] == 0
        )
        self.assertEqual(
            central_panel["updateDimensionProperties"]["properties"],
            {"pixelSize": 180},
        )

    def test_all_three_surfaces_are_recentered(self) -> None:
        requests = build_alignment_apply_requests(20260907, self.layout)
        self.assertEqual(len(requests), 3)
        self.assertTrue(
            all(
                item["repeatCell"]["cell"]["userEnteredFormat"]["horizontalAlignment"] == "CENTER"
                for item in requests
            )
        )

    def test_ticker_tables_restore_metric_family_dividers(self) -> None:
        requests = build_table_border_apply_requests(20260907, self.layout)
        self.assertEqual(len(requests), 13)
        clear = requests[0]["updateBorders"]
        self.assertEqual(
            clear["innerHorizontal"],
            {"style": "NONE"},
        )
        self.assertEqual(clear["innerVertical"], {"style": "NONE"})
        self.assertEqual(
            clear["range"]["startRowIndex"],
            self.layout["blocks"][0]["header_row"] - 1,
        )
        trading = requests[1:6]
        self.assertEqual(
            [item["updateBorders"]["range"]["endColumnIndex"] for item in trading[1:]],
            [13, 16, 17, 18],
        )

    def test_drawdown_color_depends_on_percentile(self) -> None:
        self.assertIsNone(drawdown_presentation(89, self.layout)["background"])
        self.assertEqual(drawdown_presentation(90, self.layout)["background"], "#F4CCCC")
        extreme = drawdown_presentation(99, self.layout)
        self.assertEqual(extreme["background"], "#E06666")
        self.assertEqual(extreme["note"], "")
        self.assertEqual(
            self.layout["notes"]["drawdown_header"],
            "Rojo oscuro solo por caída histórica extrema (percentil >=95); rojo claro por percentil 90-94 o precio hasta 3% sobre el mínimo de 6 meses.",
        )


if __name__ == "__main__":
    unittest.main()
