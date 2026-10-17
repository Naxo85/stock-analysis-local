# ChatGPT browser provider

ChatGPT Web is the default Markdown-generation backend. The existing Codex
provider remains available as an automatic fallback and its procedure is
unchanged.

## Install

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-chatgpt.txt
```

Firefox is the default browser engine. Selenium uses the installed Firefox and
keeps a dedicated persistent profile for the analysis flow.

## Credentials and browser profile

Accounts with a native ChatGPT password can store it in Windows Credential
Manager:

```powershell
.\.venv\Scripts\python.exe -m src.local_runner.chatgpt_browser_generator credentials set
```

The password prompt is hidden. Credentials are never written to `.env`, the
repository, analysis inputs, reports, or logs. Google accounts use the browser
session instead. Firefox state is kept in `.local/chatgpt-firefox-profile`,
which is ignored by Git.

Verify the saved credential status:

```powershell
.\.venv\Scripts\python.exe -m src.local_runner.chatgpt_browser_generator credentials status
```

Open each dedicated Firefox profile when no batch is running, authenticate
normally, complete any human verification yourself, and close the window only
after the ChatGPT composer is visible:

```powershell
.\.venv\Scripts\python.exe -m src.local_runner.chatgpt_browser_generator login --worker-id 1
.\.venv\Scripts\python.exe -m src.local_runner.chatgpt_browser_generator login --worker-id 2
.\.venv\Scripts\python.exe -m src.local_runner.chatgpt_browser_generator login --worker-id 3
```

The manual command opens a visible window intentionally and refuses to use a
profile already locked by an analysis. Do not run it from an Android-only
session unless you can interact with the remote PC desktop. After closing all
three windows, check the three automated workers with
`python scripts/check_chatgpt_workers.py --verify-background` before running
a batch; this does not send prompts or publish reports. If Cloudflare presents
another challenge in automated Firefox, its production challenge does not
support Selenium. Do not automate the checkbox or assume manual clearance
guarantees a future batch: stop and consider a supported generation route.
Since 2026-09-30 a human challenge or complete worker outage makes the batch
fail visibly instead of producing a cascade of Codex fallbacks.

Analysis attempts use chats inside the configured `Analisis` project. Its URL
is stored in `.local/chatgpt-project-url.txt` (or supplied through
`CHATGPT_PROJECT_URL`). A batch keeps three authenticated Firefox workers alive
by default, each with its own persistent profile and exclusive lock. Each
worker keeps up to five consecutive tickers in one project chat and then starts
a new project chat. Every request attaches one consolidated
`chatgpt_input.md`; the previous analysis and all authoritative instructions
are already embedded in that file.

ChatGPT currently canonicalizes the address bar back to
`https://chatgpt.com/` after the project is selected. The URL is therefore not
proof that the project was lost. Before every send, the runner requires an
exact visible project-context signal: `Nuevo chat en Analisis` or
`Cambiar proyecto: Analisis` (with their English equivalents). If that signal
is absent, the request fails before uploading or sending instead of silently
creating a normal chat. Browser restarts return to the configured project root.

On Windows, Firefox 156 cannot reliably create tabs in native headless mode on
this machine. The runner therefore starts a normal isolated Firefox on a
private Win32 desktop. Do not reintroduce `-headless` without repeating a
real Selenium smoke test. Chats are queued for conservative deferred cleanup;
cleanup failures are recorded but never invalidate a correct analysis.

The old hide-after-launch behavior could briefly expose the first Firefox
window. The replacement starts geckodriver and its Firefox children on a private
Win32 desktop from process creation, including restart attempts. It never
switches the user's desktop or silently retries on the interactive desktop.
Manual `login` remains headed. Enabled and live-verified on 2026-09-28 after the
user confirmed the batch had stopped: two local-only launches with typing,
new windows, resize and cleanup; then all three authenticated worker profiles
healthy with zero interactive windows and no analysis submissions.

Persistent installation settings: `.local/background_windows.json`,
currently `{"firefox": false, "ibkr": true}` after the user requested a
return to the earlier hide-after-launch Firefox mode on 2026-09-30. This mode
can briefly show Firefox on the interactive desktop. A no-prompt project
preflight still failed for all three workers, so it is not yet validated for
batch execution. Profiles beneath `.local` read this file at
each launch; no command-worker restart is needed. The file is ignored by Git;
recreate it when restoring this installation on another PC.
`ANALYSIS_PRIVATE_DESKTOP=1` overrides it (including profiles outside `.local`);
`=0` explicitly selects legacy hide-after-launch behavior for diagnostics.
Invalid settings fail explicitly instead of exposing a window.
Repeat local isolation with `python scripts/check_firefox_background.py` and
actual-profile preflight with
`python scripts/check_chatgpt_workers.py --verify-background`, only without an
active analysis. Neither script sends an analysis request.

## Generate one ticker

Prepare with the normal input builder, then run the default provider:

```powershell
.\.venv\Scripts\python.exe -m src.local_runner.run_one RKLB --prepare
.\.venv\Scripts\python.exe -m src.local_runner.run_one RKLB --generate --no-generator-fallback
.\.venv\Scripts\python.exe -m src.local_runner.run_one RKLB --validate
```

For a normal full run with automatic Codex fallback:

```powershell
.\.venv\Scripts\python.exe -m src.local_runner.run_one RKLB --run-full
```

Add `--chatgpt-browser-headed` only when the Firefox window must remain
visible for diagnostics. The current Windows setting launches a headed window
on the interactive desktop and hides it after startup; the private-desktop
mode remains available through the per-installation setting.

## Validation and retries

Every request attaches the complete
`output/<TICKER>/chatgpt_input.md`. ChatGPT must return exactly one Markdown
code block. The candidate is saved separately and run through the normal
analysis validator. Invalid output is not promoted to `latest.md`.

On extraction or validation failure, the next request includes the exact
errors and instructs ChatGPT to redo the whole analysis from the beginning.
After the configured attempt limit, the normal mode falls back to Codex. Use
`--no-generator-fallback` when testing ChatGPT itself.

## Batch use

`run_batch` accepts the same provider options. ChatGPT browser work is
distributed across three secured profiles and reusable browser processes by
default. Work remains sequential inside each Firefox worker but parallel
across workers. Preparation and publication keep their independent workers and
overlap with Web generation. If one browser session fails, the runner may
restart that worker without stopping the others.

Project-context loss and driver transport failures before `send` receive one
local worker restart, clear the old chat group, reopen the configured project,
and reverify Sol/High. An unconfirmed homepage is never retained from a failed
request. If restart itself fails or the recovered request hits another
pre-send browser-state failure, the worker is quarantined for the remainder of
the batch. The current ticker may still use fallback; subsequent tickers lease
healthy workers only. If none remain, waiting leases fail explicitly instead
of blocking forever. `disabled_worker_ids` includes these quarantined workers.
Transport errors during/after send do not trigger this restart/replay path.

Regression coverage is in `test_project_recovery_regressions.py`. This change
has been verified offline, not by a new live ticker or batch.

ChatGPT Web is treated as the Sol-authoritative path. Route models such as
Tierra remain fallback choices and do not leak their lower-authority policy
into the Web attachment. A valid Web result is not sent through an equivalent
second Sol review.

Before every Web request, including the first request after a browser or
session restart, the runner opens ChatGPT's model control and verifies both
`GPT-5.6 Sol` and reasoning effort `High` (`Alta` in the Spanish UI). If either
choice cannot be selected and confirmed, the request fails before attachments
or prompt submission. Successful generation metadata records
`web_model=gpt-5.6-sol`, `web_reasoning_effort=high`, and the verification time.

The time limits are independent and can be overridden with environment
variables:

- `CHATGPT_NAVIGATION_TIMEOUT_SECONDS`: page load and composer, default 120.
- `CHATGPT_SEND_START_TIMEOUT_SECONDS`: confirmation that the prompt was
  actually submitted, default 60.
- `CHATGPT_SEND_READY_STABLE_SECONDS`: continuous time that the send control
  must remain truly enabled before it is clicked, default 10.
- `CHATGPT_RESPONSE_TIMEOUT_SECONDS`: one ChatGPT response, default 1800.
- `CHATGPT_BROWSER_LOCK_TIMEOUT_SECONDS`: wait for the shared browser profile,
  default 21600.

These limits apply to one browser operation, not to the duration of the whole
batch.

## Interface-change runbook

Use this procedure whenever ChatGPT changes its UI. Do not diagnose a browser
compatibility failure by repeatedly launching the complete market batch.

1. Stop the affected batch before it falls through to Codex and preserves a
   misleading partial result.
2. Read `output/<TICKER>/browser_diagnostics/current.json`. Its `stage`
   identifies the first broken contract.
3. Open the newest failed attempt's `.png`, then read its `.txt` and
   `.html`. The screenshot establishes what the user sees; the HTML
   establishes what Selenium can select.
4. Compare the current markup with the selector map below. Prefer stable
   `data-*`, role, type and aria attributes over generated CSS classes.
5. Fix both Selenium and Playwright when they share the affected contract.
6. Add a focused regression to `tests/test_chatgpt_browser_lock.py`.
7. Run the focused test suite.
8. Run exactly one real ticker with one Web attempt and no fallback.
9. Validate it independently and inspect `generation_metadata.json`.
10. Relaunch the market batch only after the smoke result records
    `provider_used=chatgpt-browser`, `status=ok`, Sol high and zero
    unexpected retries.

Focused tests:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_chatgpt_browser_lock.py -q
```

Real smoke test:

```powershell
.\.venv\Scripts\python.exe -m src.local_runner.run_one AMD --generate `
  --generation-provider chatgpt-browser --no-generator-fallback `
  --chatgpt-browser-max-attempts 1
.\.venv\Scripts\python.exe -m src.local_runner.run_one AMD --validate
```

The smoke normally spends several minutes in `wait_assistant`; that is model
execution, not an interface stall. Diagnose with stages and artifacts rather
than elapsed time alone.

## Current UI contract

The canonical selectors live near the top of
`src/local_runner/chatgpt_browser_generator.py`. This table explains what
each contract is intended to find:

| Contract | Current stable hooks |
| --- | --- |
| Composer | `#prompt-textarea` or a contenteditable textbox with `data-composer-markdown` |
| Project context | sidebar row `data-app-action-sidebar-project-id` plus button `Nuevo chat en Analisis`, then composer aria label `Nuevo chat en Analisis` or `Cambiar proyecto: Analisis`; the address bar may be only `https://chatgpt.com/` |
| Attachment input | file input labelled `archivos`/`files`, dynamic file input without `accept`, or legacy `#upload-files` |
| Attachment menu | `data-composer-navigation-target="add-context"` or the attach/add-files aria label |
| Stale attachment removal | buttons whose aria label starts with `Quitar` or `Remove` |
| Reasoning control | `data-codex-intelligence-trigger`, `data-composer-navigation-target="reasoning"`, or a menu button titled `Esfuerzo de razonamiento` / `Reasoning effort` |
| Model submenu | menuitem `Seleccionar modelo` / `Select model`, then checked `GPT-5.6 Sol` radio |
| High reasoning confirmation | `data-selected-reasoning-effort="high"`, or checked Sol plus slider `aria-valuenow="2"`; the new closed button displays a generic label |
| Slider keyboard interaction | menuitem `aria-keyshortcuts="ArrowLeft ArrowRight"`; the new internal ARIA slider thumb is hidden |
| Send | stable test IDs or submit buttons labelled `Enviar`/`Send` |
| User turn | legacy `data-message-author-role="user"` or `data-content-search-unit-key$=":user"` |
| Assistant turn | legacy `data-message-author-role="assistant"` or `data-content-search-unit-key$=":assistant"` |
| Agent activity | `data-chatgpt-agent-turn-start` or a visible `Detener`/`Stop` control before the final assistant container exists |
| Markdown result | legacy `pre code` or `[data-markdown-copy="code-block"] code` |

ChatGPT can expose both legacy and new assistant markers nested in the same
turn. Extraction must walk backward to the newest assistant container that
actually contains a code block; selecting the last node of the CSS union is
not sufficient.

## Stage-to-cause map

| Failed stage | Inspect first |
| --- | --- |
| `navigate` / browser launch | Firefox process, profile runtime locks, Marionette/geckodriver and authentication |
| `ensure_sol_high` | reasoning trigger attributes, visible model label and selected effort |
| `locate_composer` | textbox role, `contenteditable`, composer data hooks |
| `attach` | hidden file input and add-context button |
| `confirm_attachments` | filename chip, duplicate-file dialog and stale attachment remove buttons |
| `wait_send_ready` | submit button label/type and whether the attachment is still uploading |
| `wait_request_start` | change of the newest virtualized turn, agent activity, visible stop control and rate-limit dialog |
| `wait_assistant` | assistant turn, agent-activity hook or visible stop control; several minutes can be normal Sol reasoning |
| `wait_response` | stop button, changing response text and inactivity timer |
| `extract` | actual code element and its nearest assistant container |

The September 2026 interface change broke, in order, model confirmation,
composer discovery, attachment discovery, attachment-chip confirmation,
stale-attachment cleanup, send-button discovery, turn detection and Markdown
extraction. The final extraction failure looked like
`expected_exactly_one_markdown_block: found=0` even though the report was
visible. The cause was a new
`div[data-markdown-copy="code-block"] ... code` structure replacing
`pre code`.

## Diagnostic artifacts

Account-load errors (`No hemos podido cargar tu cuenta`) receive at most three
ordinary application retry clicks during authentication, at least ten seconds
apart and within the existing startup deadline. Human challenge controls are
never clicked. The passive network observer preserves a challenged endpoint
until a successful response for that endpoint arrives; retries cannot mark a
still-blocked shell healthy. Traces include the retry timestamps and the last
100 essential-response events (path/status/challenge only, no queries, bodies or
credentials). Exhausted account errors disable that worker and do not trigger
mass Codex fallback. On 2026-10-01 the retry sequence was exercised on profiles
2/3 but could not recover their confirmed external challenges; profile 1 passed
project/model/hidden-window checks after manual recovery. A new three-profile
preflight and Web-only ticker smoke remain required before declaring readiness.

Startup failures before a ticker is assigned now write PNG, HTML, visible text
and JSON to `logs/browser_startup/worker-N/`. A missing composer at startup is
retried with at most two worker restarts; after exhaustion, pool preflight
excludes that worker and continues with healthy workers. If none are healthy,
the batch still fails visibly. `scripts/check_chatgpt_workers.py` verifies all
three profiles without submitting a prompt. A resumed fatal checkpoint keeps
the previous exception in `failure_history` and publishes fresh running state.

Startup launch/authentication also handles native Selenium exceptions (not
only RuntimeError). InvalidSessionIdException and Marionette's "Tried to run
command without establishing a connection" require a fresh driver, not a
repeat response poll. Restart is bounded to two attempts, retains the profile
lock, and tolerates quit failure on the dead driver. JSON preserves the exact
exception even if page capture is impossible. Preflight excludes exhausted
workers, rebuilds the healthy queue, and fails explicitly with zero workers
if all failed. Unknown errors still propagate. This does not authorize replay
of requests whose send has begun. Offline coverage:
`test_dead_browser_session_recovery.py`; actual-profile startup verified on
2026-09-29 with three healthy workers and zero interactive windows, including
one recovered native StaleElementReferenceException. No analysis was sent.

Every Selenium attempt writes state under:

```text
output/<TICKER>/browser_diagnostics/
```

- `current.json`: live stage, status and completed stage timings.
- `timeline.jsonl`: chronological stage transitions across attempts.
- `<timestamp>-<TICKER>-attempt-N.json`: terminal stage and exact exception.
- matching `.png`: page screenshot at failure.
- matching `.txt`: visible page text, capped at 200,000 characters.
- matching `.html`: full DOM snapshot for selector inspection.

Read the artifacts from the same timestamp together. A visible completed report
with `extract/found=0` is an extractor problem and must not trigger another
model request. A page without a submitted user turn is a send problem. A page
with a user turn but no assistant turn is either normal model execution or a
response-start detection problem.

## Smoke-test acceptance

A UI fix is complete only when all of these are true:

- focused tests pass;
- the real ticker finishes without fallback;
- `current.json` ends at `stage=complete`, `status=ok`;
- `generation_metadata.json` records
  `provider_used=chatgpt-browser`, `web_model=gpt-5.6-sol` and
  `web_reasoning_effort=high`;
- `web_attempt_count=1` and `web_retry_count=0` unless the test deliberately
  exercises recovery;
- `run_one <TICKER> --validate` succeeds.
