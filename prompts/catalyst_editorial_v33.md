CATALYST EDITORIAL33 — replaces reader32 catalyst visibility instructions.

The public catalysts section is a causal digest of what matters NOW, not a news
archive or a checklist of every fact that remains true about the business.
Keep the complete dated facts in catalysts for research memory. Do not delete
facts, change dates/scores or call a model again just to shorten the display.

Assess each fact before writing the reader digest:
- driver: a DISTINCT active force affecting today's situation, a concrete pending
  consequence or a material unresolved risk the reader needs to understand now.
  rationale identifies that current mechanism and why the summary/event/another
  driver does not already cover it. Being relevant to the business in general,
  still true, high-scored, adverse, recent, or in a news feed is NOT sufficient.
- background: useful antecedent or absorbed event without its own current
  decision-relevant consequence. rationale says why it belongs in memory only.
- covered: additional evidence/reaction about an existing driver, not a second
  independent catalyst. Link it to that driver; do not count each article,
  broker opinion, date or restatement as a separate force.

For each driver write brief: one compact causal paragraph, at most two short
sentences/40 words, with the decisive evidence, attribution and useful source
link(s). Integrate its covered facts where necessary; no news-by-news inventory.
Keep materially different consequences and disagreement without repeating the
whole history. The selected driver's date/impact label still describes that
source fact, NOT a synthetic date/score for the entire group; attribute different
dates inside brief if needed. There is no quota/minimum: no active drivers is
valid, as are multiple genuinely independent ones. Do not invent a price move.

Examples of judgment, NOT automatic category/age exclusions:
- Several competitor developments and broker reactions may describe ONE
  competitive pressure. A distinct funding consequence remains separate if real.
- Old results/cash and prior satellite losses usually support the background;
  show them only for a specific live runway, covenant, capacity or deadline risk.
- A law firm's repeated class-action solicitation is not a new judicial event.
  A ruling, material exposure or consequential unresolved deadline may matter.
- An old short-interest estimate is not current positioning without relevant
  fresh evidence; a concrete live squeeze/liquidity risk can be a driver.
- Shipment and analyst launch-delay commentary may describe the SAME execution
  uncertainty. The next-event section already carries the next launch/date:
  don't duplicate it unless the catalyst adds a separate current consequence.
- A confirmed integration/contract that materially changes execution confidence
  can be its own driver; generic positive corporate history is not enough.
Old serious risks may remain live; fresh minor news may be background. Never
hide adverse material evidence just to make the report shorter. No age/score cut.

FULL33: each catalyst replaces show_in_report with reader_assessment:
{role:driver|background|covered, rationale:string, brief:string|null,
 covered_by:string|null}. For covered, covered_by is the EXACT unique title of
the driver in this same response; brief=null. For background both are null.
For driver brief is the public paragraph and covered_by=null. Keep original
description, dates, scores and source links as the complete financial record.
Group selection and brief do not grant permission to invent/change those facts.
next_event keeps its reader32 show_in_report boolean.

MAINTENANCE33: reader_review=null inherits the existing view. Otherwise return
{catalysts:[{id:cID,role,rationale,brief,covered_by}],hide_next_event:boolean},
covering each supplied reader_catalog ID exactly once. covered_by uses the cID
of a driver in the same selection. Assess old archive-style views on the first
review; retaining financial conclusions is NOT a reason to inherit that archive.
Only existing authenticated CURRENT facts can be summarized here. New research
still uses existing coverage/public_note/risk paths; it cannot be smuggled into
an editorial brief. Material changes still require normal financial routing.
Keep dates, financial fields, ITV, anchor and news memory untouched. The digest
is a separate editorial projection, not an edit of protected catalyst facts or
summary. It may accompany retain without a paid full report or additional call.
The same independent summary, useful event and concise plan rules remain.
