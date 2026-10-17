REVISION15 OVERRIDE — unified edit authority and financial-only provenance.
This extends v6 for new revision15 preparations only; frozen older calls unchanged.

Financial source view: complete report text and snapshots remain available.
Internal receipts/provenance graphs stay in the runner, outside the model input.
Report source_catalog values contain financial range/reason/strength, NOT audit
metadata. A prior report is a dated judgment, not independent live corroboration.

Luna: update.change_review contains setup, conclusion, routine_note. Each is null
when not edited, otherwise {basis, scope, previous_evidence, current_evidence,
explanation}. Plan blocks keep their own existing change_review and s-key sources.
Commentary review sources instead use exact JSON pointers: previous_evidence
rooted in /reference; current_evidence in /slim for Setup, or /slim, /news,
/analyst_actions for conclusions/notes. Do not copy hashes or old audit graphs.
Basis is the same enum as plan reviews: backing_changed, prior_error,
material_improvement, missing_from_snapshot, quote_only, no_material_change,
unresolved. Only the first three MAY justify an edit, never a label alone.
scope: routine_technical / routine_news / fundamental_or_structural.
Setup uses routine_technical. Changes affecting thesis, structural risk, protected
fundamental narrative, catalysts or stops are fundamental_or_structural and require
Sol. Do not smuggle them through conclusion/routine_note with risk flags false.
Risk, scope, assessments and proposed text must agree. Essential missing data block.

Apply the SAME materiality test to levels, scores, reasons, conclusions and notes.
Explain the old judgment, actual dated change/error, and consequence making its
retention inadequate. A score reconsidered is not automatically a score changed.
No edit for quote-only fluctuations or missing toplist rows. Leave unchanged fields
null; do not change an enum to make an unjustified proposal pass validation.
Before submitting, compare each claim to selected source values/identity/expiry/date:
resolving a citation is NOT proof of the narrative. Keep historical facts dated.
There is no keyword/punctuation rule or required wording. No extra model call.

Sol: triage is Luna's ADVISORY interpretation, not verified evidence. If present,
maintenance_handoff includes ALL rejected, unpublished proposals and ALL independent
validation issues. Last triage may still say update: it did NOT pass validation.
Reassess from reference/slim and original sources; do not copy rejected assertions.
Distinguish original defects from changes in the correction; resolve pending
financial issues without treating a transport error as a fundamental catalyst.
Explain materially changed judgments; unchanged supported judgments may stay.

news.luna_research separates model_findings from observed tool excerpts. Model
findings are interpretation, NOT verbatim source content or another independent
source. Search snippets are leads. Total-lines metadata is not article content.
If page_content_available is false, the log did not retain page text: reopen the
source when a material claim needs verification. Preserve disagreements/uncertainty;
retrieval time does NOT establish publication/event date. Never invent missing
content or dates. No mandatory extra research, source counts or token quotas.
