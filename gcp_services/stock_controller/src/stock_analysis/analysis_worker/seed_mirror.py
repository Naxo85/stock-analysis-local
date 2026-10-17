from __future__ import annotations

import argparse
import subprocess
from concurrent.futures import ThreadPoolExecutor

from stock_analysis.analysis_worker.run_sync import configured_universe
from stock_analysis.controller.sheet_layout import load_market_sheet_layout


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Seed the new report mirror from the legacy GCS bucket"
    )
    parser.add_argument("--source-bucket", default="stock-analysis-reports-naxo85")
    parser.add_argument("--target-bucket", default="stock-analysis-system-naxo85")
    parser.add_argument("--max-parallel", type=int, default=4)
    arguments = parser.parse_args()
    layout = load_market_sheet_layout()
    prefix = layout["analysis_sync"]["mirror_prefix"].rstrip("/")
    tickers = configured_universe(layout)

    def copy(ticker: str) -> str:
        subprocess.run(
            [
                "gcloud.cmd",
                "storage",
                "cp",
                f"gs://{arguments.source_bucket}/{ticker}/latest.json",
                f"gs://{arguments.target_bucket}/{prefix}/{ticker}.json",
            ],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=60,
        )
        return ticker

    workers = max(1, min(arguments.max_parallel, 8))
    with ThreadPoolExecutor(max_workers=workers) as executor:
        copied = list(executor.map(copy, tickers))
    print(f"OK seeded={len(copied)} prefix=gs://{arguments.target_bucket}/{prefix}/")


if __name__ == "__main__":
    main()
