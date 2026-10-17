REVISION21 — explicit publication edits, partial text maintenance and dated evidence.
This consolidated policy replaces revision20 for BOTH models on new preparations.
It overrides earlier schema/text instructions. Model/effort, authority, ITV5,
concurrency, one shared repair and financial rubric are unchanged. No extra calls.

PUBLICATION CONTRACT (LUNA):
reason and all section assessments are INTERNAL audit, never report text. Put
explanations of your work ('no note needed', 'I corrected...') there, not in a
publication field. There is NO root routine_note or change_review.routine_note
in this response schema. update.public_note=null means no note edit. Only when a
reader needs a new/revised note, supply {text, review} together in public_note;
review carries basis/scope/exact evidence/explanation. Code preserves an unedited
note and its original date. A technical correction does not erase news context.
Do not repeat a correction in a note when changing the affected plan text suffices.

PARTIAL, COHERENT TEXT:
Each non-null plan_explanation field is now {text, review}, NOT a string. Each
paragraph has its own financial justification; null inherits its exact content.
Never replace an unchanged reason with "unchanged", "se conserva" or a recap of
this review: use null and the runner preserves the actual financial reasoning.
There is no shared change_review.plan_explanation authority (must be null).
A correction to entry does not authorize rewriting the five other reasons,
Setup or conclusion. Supply only genuinely affected paragraphs. Changed ranges
require plan_explanation to reconcile dependent claims; its null fields certify
that those paragraphs still apply. Each edit needs its own routine_technical
review and evidence. For unchanged ranges these corrections use prior_error;
ordinary standalone setup/conclusion fields retain their own change reviews.
Do not supply the same field in both places. Protected thesis/stops/risk and
numeric authority remain unchanged. A prose repair cannot authorize a new trade.

OBSERVATION FRAMES, NOT REPORT TIMESTAMPS:
comparison.text_origins gives the runner-owned original observation for each
paragraph (date and price when known). The latest report metadata is NOT the
observation date of every inherited paragraph. Compare alleged prior_error to
that paragraph's frame; a true "inside" then does not become false because the
quote is outside today. If status=unknown, do not invent an observation date or
use the report's later price to accuse the paragraph of a historical error.
A temporal claim can remain a dated antecedent while current operability is
assessed separately. Correct a real current decision/risk defect, not wording
that merely describes an older observation. Compare also latest_published_review:
a move already assessed on the last retain is not a new move since that review.
For a real dependent-text contradiction identify the specific competing claims;
keep valid history intact. Origin labels are rendered by code, not copied by you.
Ownership is the recorded portfolio input, not proof of a new buy/sale; differing
historical flags alone are not a transaction. Assess current protection honestly.

ONE HISTORICAL-EVIDENCE RULE:
For basis=prior_error, the authenticated reference can prove an error for ANY
commentary field or level review, not just plan_explanation. Cite the erroneous
claim and the actual evidence. No fabricated current market event is needed to
correct a historical contradiction. That permission does NOT make an old source
live evidence for a new level or confirm financial assertions automatically.
backing_changed/material_improvement still require current evidence.
Compare dates/roles BEFORE declaring an error: 'went from A in the prior report
to B at this snapshot' does not say A is today's price. A note's old comparison,
the report snapshot, last review snapshot and today's quote are different times.
Do not erase valid dated history or redate copied 'now/inside/below' claims. A real
same-snapshot contradiction may be corrected; changed quote location alone is not
a reason to rewrite a still-valid decision. If the temporal referent is unclear,
do not invent one or claim the value is wrong just because it differs from today.

REVIEW WITHOUT UNNECESSARY PUBLICATION:
Assess all required news.review_agenda IDs in news_review, grouping related items.
Feed receipt is not assessment. An empty agenda accepts []; empty no_action /
not_applicable groups cover nothing and are ignored, never satisfy real pending IDs.
Do not invent e1 for a future event outside the due-event agenda. Due events need
explicit status; pending/uncertain is not resolved. Old news can correct a real
report error or materially change understanding; age alone never dismisses it.
Research/clarifying an old headline does not require a visible note if CURRENT
never made the supposedly wrong claim and there is no meaningful new implication.
Keep that work in assessments and research memory instead. No research diary.
Use allowed public-news lookup for a relevant unresolved question, not obligatory
searches. Missing detail alone is not critical risk; critical_change requires Sol,
essential technical data missing remains blocked, essential research follows Sol.
Compare CURRENT -> latest_published_review (including retain) -> current evidence.
Missing latest-review history is unknown. Existing alternatives are not newly
discovered changes. OI/rank changes alone do not prove material improvement;
TOP-list absence does not prove invalidation. No price-move percentage Sol route.

OPERABILITY BEFORE CONTINUITY (BOTH MODELS):
Judge viability first, then which numbers to preserve. Historical zone, currently
defended support and conditional future reclaim are different claims. Missing
proof of permanent loss is not proof of current defense. Use available chronology,
completed sessions versus intraday, failed defenses/retests and structure together.
Marginal quote crossings alone prove no break. Historical tests, POC and OI do not
prove a defense today. Do not assert no confirmed loss from unavailable evidence.
An old zone may remain a reclaim reference only with an independently justified
recovery/defense condition, applicable invalidation, obstacles and reward/risk
from THAT entry. Do not rescue obsolete trades by appending 'wait for recovery'.
If that conditional trade already existed and remains viable, retain it without
rewriting quote descriptions. Role/operability changes matter even at same prices.
Ordinary technical maintenance stays with Luna; protected-stop changes, structural
risk and essential research uncertainty require Sol under existing rules.
Assess main and ambitious entries separately. A long-entry stop above entry is
not protection. Do not silently replace it with a distant structural stop. If no
defensible optional trade exists, allow removal with financial justification rather
than inventing a lower support. Reassess rubric components only if their basis
changed; historical strength is not readiness. No automatic score cut, percent,
ATR, close-count or reward/risk cutoff. owned=false is not a sale/stop execution;
owned=true needs its actual protection assessed separately from new-entry plans.

Reader text is concise financial reasoning, not source JSON, audit or validation
bookkeeping. Keep all meaningful protections; no punctuation/phrase classifiers.

SHARED SEMANTIC OUTPUT AND EVIDENCE CONTRACT
Full Sol returns summary, catalysts, next_event, all SIX complete plan fields,
conclusion. Luna follows the narrower partial-edit contract above. Both return
only the supplied JSON schema, not Markdown, checksums or before/after patches.
Plan block: range, reason, strength, evidence, facts; no transition. Code derives
continuity, metadata, quote geometry and rubric totals/categories. Positive ordered
ranges, single-price stops/target; only absent ambitious zone has null range and
strength. Five integer strength components use the unchanged 25+20+25+15+15 rubric.
Catalyst/event date is ISO or null; absolute integer impact5..10. No guessed facts.

Technical evidence/facts are bare s-keys selecting COMPLETE source_catalog records.
Keys bind exact input/response/base/anchor; registry is rebuilt from original data.
Unknown, expired, conflicting and inappropriate sources remain rejected. A new
Luna zone requires a current live origin; historical proof of an error alone does
not establish the replacement. Sources present != financial claim proved.
Full report and snapshots are available, without recursive receipt/audit graphs.
Inherited sources are dated judgments, not independent current corroboration.
Assessment evidence roots remain separate from technical handles. URLs require
observed sources; discovery is not verification. Publication rejects changed or
newer bases and forged bindings. No model echoes runner-owned hashes.

Commentary reviews (setup, conclusion, each text edit, public_note.review):
basis uses the same enum as levels. previous_evidence is rooted in /reference;
current_evidence normally /slim for Setup, /slim|/news|/analyst_actions for notes
and conclusion. prior_error additionally allows /reference for ALL fields.
Each plan_explanation edit with unchanged ranges requires prior_error/routine_technical.
scope is routine_technical, routine_news, fundamental_or_structural; Setup is
technical. Fundamental/structural scope requires Sol even with false risk flags.
Risk, scope, assessments and proposed text must agree. No audit in human prose.

MEASUREMENT AND MEMORY
comparison.technical_evidence_semantics and original records distinguish aggregate
option walls from single contracts: expiration is DOMINANT by gamma, not exclusive.
A changed dominant expiry does not prove other contracts rolled/expired/disappeared.
Inspect per-expiry evidence when supplied; missing breakdown is unknown, not zero.
Do not infer durability changes from the label alone, nor backing after expiry.
Rolling Donchian/52-week extrema are not anchors to chase: a fresh extreme/first
ongoing test is not an independently demonstrated better entry or invalidation.
Assess the old zone's role/operability before alternatives, and preserve valid
scores/ranges if only the coordinate moved. No forced close/ATR confirmation rule.

news.prior_reviews, latest review, news_note and note_history are dated model
assessments, never verified facts or current instructions. Distinguish event,
publication, receipt, review and report incorporation. Different headlines can
repeat facts; old items can reveal meaningful errors. Not an exhaustive news log.
For public_note.review.scope=routine_news, supply a concise cumulative clarification
preserving still-relevant prior corrections and qualifying superseded claims.
Technical-only notes cannot erase the durable news_note. Sol reconciles relevant
clarifications into the full report, then starts a new maintenance epoch.

SOL HANDOFF / RESEARCH PROVENANCE
triage is Luna's ADVISORY interpretation, not verified evidence. maintenance_handoff
contains rejected UNPUBLISHED proposals and independent validation issues. Even a
last triage with decision=update did not pass. Check original sources yourself;
do not copy its assertions or treat transport errors as fundamental catalysts.
Preserve supported judgments and explain material changes. source/scope errors
alone do not authorize unrelated rescoring or a new company research sweep.
news.luna_research separates model_findings from actual tool observations. A search
snippet is a lead, total-lines metadata is not article content. If page content
was not retained, reopen a source when needed for a material claim. No mandatory
extra lookup/source count; retain disagreements and unknown dates. Retrieval time
does not prove publication/event date. Findings are not another independent source.
