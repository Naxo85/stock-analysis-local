# Independent flow and contract review — 2026-10-18

Scope: offline code review of one authenticated IBKR raw capture per ticker/provider/preparation, with derived news and analyst views. No production files modified by this reviewer; no new IBKR/model/network call or historical mutation.

## Observed flow before optimization

1. run_batch launches update_analysis_sources_pipeline and waits on per-ticker source progress. The pipeline processes news, analyst ratings, and action summary/backfill before releasing success.
2. News selects CURRENT report timestamp minus 24h, explicit since, previous earnings or 90-day fallback; analyst DJ-N selects max(last ingested minus 24h, now minus 30d), previous earnings or 30-day fallback. Initial analyst BRFUPDN seed is a distinct provider and 365-day window.
3. adaptive_stage.prepare can need a news start older than the current report: immutable full anchor minus 24h. Its backfill currently redownloads DJ-N. A model reservation, response or receipt prevents replacement of a frozen preparation.
4. The low-level adapter qualifies the stock contract, authenticates request-specific historicalNewsEnd, pages backward with overlap and identity/order/progress checks, and only admits terminal has_more=false. The available provider cache is exhausted; this is not an assurance that every market news item exists in IBKR.
5. require_complete_news_payload precedes news latest.json and analyst current state writes. A failed/partial capture must preserve the previous valid data. News/analyst raw files and financial reports are historical evidence and must not be mutated.
6. The natural Sunday run has 118 successful raw acquisitions (46 news, 46 analyst, 26 backfill). Identical raw sequences permit offline derivation, but do not show that separate captures during a changing market would contain identical information.

## Required invariants and independent verification

| Area | Required behavior | Negative/control cases |
|---|---|---|
| Scope | Explicit execution/preparation scope; no global persistent reuse | Different scopes fetch independently; missing scope preserves old route; resume cannot rejuvenate old capture |
| Identity | Exact ticker/provider/qualified contract and connection compatibility | Cross-symbol, conId, provider, host/port, secType/currency mismatch; BRFUPDN distinct from DJ-N; client IDs may differ |
| Completeness | Reuse only authenticated terminal complete bounded pagination | Timeout, error, has_more=true, missing terminal, wrong method/scope, truncated pages/counts, conflicting identities |
| Integrity | Immutable raw object plus hash-bound index; invalid state fails closed | Object/hash mismatch, changed envelope, broken JSON, missing object, index pointing to wrong capture |
| Time | Original generated_at/end/provider_fetched_at retained, with bounded age | Consumer delayed; now before capture; malformed date; stale scope; no extension to consumer time |
| Windows | Derive views from complete raw cache, preserve original acquisition metadata | Full anchor older than CURRENT, empty filtered view, before/after boundaries; derived basis never rewrites original request |
| Downstream | Existing parser, compact news, dedup, consensus and state logic unchanged | Replay actual 118 captures with equal clocks and initial states; zero/empty actions and repeated firms |
| Failure | Failed acquisition leaves no reusable index and preserves last good latest/current | First callback error then retry; complete capture then downstream failure; publication pointer partial writes |
| Freeze | Model-admitted preparation remains immutable | Reservation, response, receipt or already frozen input survives refresh path |
| Cost/scope | No extra model, aggregation, body fetch, fallback model, changed pages/clocks | Check CLI flag propagation, no-scope control and command construction |

Financial replay owners report 118/118 news/analyst-view equivalences and 236/236 firm/consensus equivalences in the available corpus. Independent integration/negative tests remain pending the actual snapshot module and wiring. These checks establish local transformation/integrity, not live provider behavior, predictive benefit, or batch wall-clock savings.
