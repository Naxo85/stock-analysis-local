# Batch Workflow

The batch runner analyzes multiple tickers with limited parallelism.

Main command:

```powershell
python -m src.local_runner.run_batch --from-gcs --upload-real --max-parallel 2
```

It reads tickers from:

```text
gs://stock-analysis-reports-naxo85/config/tickers.json
```

The JSON must contain a `tickers` list. The runner trims values, uppercases them, removes empty values, deduplicates them, and keeps the original order.

## What It Runs

Each ticker runs the same full one-ticker flow:

```powershell
python -m src.local_runner.run_one TICKER --run-full
```

That means:

```text
prepare -> generate -> validate -> upload real
```

Each ticker uses its own paths:

```text
output/{TICKER}/
data/slim/{TICKER}/
logs/{TICKER}/
```

If one ticker fails, the batch records the failure and continues with the rest.

## Parallelism

Recommended initial parallelism:

```powershell
--max-parallel 2
```

`--max-parallel 1` runs sequentially. Values above `5` are capped to `5`.

## Small Tests

Run only the first two tickers from GCS:

```powershell
python -m src.local_runner.run_batch --from-gcs --upload-real --max-parallel 2 --limit 2
```

Run an explicit list without reading GCS:

```powershell
python -m src.local_runner.run_batch --tickers RKLB,GOOG --upload-real --max-parallel 2
```

## Logs

Each batch writes a summary:

```text
logs/batch/YYYY-MM-DD/HH-MM-SS/summary.json
```

Each ticker also gets a batch-level log:

```text
logs/batch/YYYY-MM-DD/HH-MM-SS/tickers/RKLB.json
```

The summary includes start/end time, source, parallelism, success count, failure count, and per-ticker results.

## Resume

Resume can skip tickers already marked `ok` in a previous summary:

```powershell
python -m src.local_runner.run_batch --from-gcs --upload-real --max-parallel 2 --resume --resume-from logs/batch/YYYY-MM-DD/HH-MM-SS/summary.json
```

Failed tickers are retried if they are still in the ticker list.
