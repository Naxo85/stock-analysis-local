# Styled HTML reports

After successful validation, Python converts `output/TICKER/latest.md` into a
self-contained `output/TICKER/latest.html`. This conversion uses fixed CSS and
does not invoke Codex or consume tokens.

Successful real uploads include:

```text
TICKER/latest.html
TICKER/YYYY-MM-DD/HH-MM-SS.html
```

The Markdown and JSON artifacts remain the source data. Raw HTML contained in
generated Markdown is escaped before rendering.

## Reader

The versioned reader in `gcp_functions/reports_reader/` accepts:

```text
?symbol=NBIS&format=html
```

For the current personal Sheet, `apps_script/update_targets_and_notes.gs` links
scores directly to the authenticated GCS object at
`https://storage.cloud.google.com/stock-analysis-reports-naxo85/TICKER/latest.html`.
This requires the browser user to have access to the bucket, but avoids a reader
deployment. The versioned reader remains available for a future shared view.
