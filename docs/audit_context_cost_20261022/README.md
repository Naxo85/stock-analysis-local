# Context and cache investigation — 22 October 2026

**Actualización posterior:** el usuario autorizó activar el punto1. El transporte
por referencias ya está activo para nuevas revisiones; [implementación, pruebas,
protocolo de tablas e investigación ampliada de caché](implementation.md).
Los resultados siguientes conservan el estudio inicial previo a esa activación.

Scope: offline investigation requested after switching new maintenance preparations
to GPT-6 Luna high. No model calls, source refresh, batch, financial publication,
production transport/prompt changes or session resets were performed by this audit.

## Corpus and reproducibility

46 actual model inputs/receipts from `logs/batch/2026-10-21/06-52-46/adaptive`.
Matched prior inputs: `logs/batch/2026-10-20/21-10-28/adaptive` (46 tickers).
Run `.venv\Scripts\python.exe docs\audit_context_cost_20261022\audit.py`.
Aggregate and per-ticker measurements are in `results.json`. Inputs remain exact.

Size measurements below are serialized Unicode **characters**, not model tokens,
bytes, included Plus usage or measured financial quality. No exact compatible
tokenizer or live billing experiment was used. Token savings cannot be inferred
by applying these percentages directly to the weekly allowance.

## 1. Context reduction

Existing lossless object/array aliasing already reduces expanded context from
47,011,075 to 17,148,388 characters (63.5%). The packed JSON consists chiefly of:

| Block | Characters | Share |
|---|---:|---:|
| comparison | 7,094,427 | 41.4% |
| reference | 4,231,082 | 24.7% |
| slim | 3,137,544 | 18.3% |
| alias map | 1,151,693 | 6.7% |
| news | 576,725 | 3.4% |

Shares describe physical serialized placement after deduplication, not unique
financial information. In particular a small serialized sol_reference does not
mean the full anchor has been discarded: aliases reconstruct it exactly.

Offline prototypes, **not activated**:

| Variant | Characters | Reduction from existing packed input |
|---|---:|---:|
| Diff rows use existing presence flags/pointers instead of copying previous/current values | 16,505,430 | 3.75% |
| Homogeneous record arrays share column names once | 15,257,537 | 11.03% |
| Both | 14,815,675 | 13.61% |

The pointer variant checks 19,520 values against their exact original logical
paths, repacks/unpacks and reconstructs the full original context for all46.
Tabular encoding/decoding preserves every row, column, value and order for all46;
the combined form also passes exact roundtrip checks. These are transport
equivalence checks only: a model's ability to interpret the more indirect view
has not been tested. In particular, a new transport must preserve logical source
identities; positional rows must never turn source handles into guessed offsets.

Additional long-string aliasing has an optimistic upper bound of159,488 characters
(0.93%), before new instructions or implementation overhead. Not a priority.
The retained news/dated antecedents, optional unknowns and historic/current risk
distinctions were not pruned. A large comparison block is not proof it is dispensable.

Recommendation: if implementing a further revision, start with pointer-only diff
transport and clear logical-path reconstruction; evaluate table encoding separately
because it increases interpretation risk. Preserve original frozen data and code
validation authority, and do not claim financial equivalence from a roundtrip.

## 2. Stable baseline and cache

Between the selected20→21 inputs, expanded full anchors are identical45/46 and
CURRENT reference objects41/46. Existing serialized user JSON shares only20,465
leading characters in aggregate (about445 per ticker); its leading alias map
depends on current dynamic differences. Later identical data cannot repair an
earlier changed prefix.

Packing reference+anchor independently produces5,885,218 characters, of which
5,214,867 form a common prefix against the matching previous independent baseline.
This shows substantial stable content exists (about30% of the original packed
input size in this selected corpus), **not** that30% would become cached or saved.
Block separation can duplicate objects formerly shared across blocks; production
implementation must account for that overhead and exact message/breakpoint layout.
The measured prefix experiment has no provider request overhead or tokenization.

Current runner already has stable developer instructions, contract-isolated pooled
sessions and clean history reuse. On21Oct,45/46 triage receipts say session_reused;
39 report32,640 cached tokens,6 report zero, and one web-research triage reports
1,067,392. Session reuse is not proof of a cache hit; receipts alone do not expose
backend lookup boundaries, eviction or the precise cause of those6 misses.

Official API documentation currently specifies GPT-5.6+ TTL controls of30m/default
or12h, and exact eligible prefix boundaries. Daily24h gaps are outside those
documented lifetimes. This particular20→21 pair is overnight, shorter than12h;
it is not representative evidence of guaranteed daily cache retention.
These are **API controls**: this audit has not established an equivalent supported
Codex ChatGPT-authenticated CLI setting, nor changed the model access route.
Keeping local session files does not keep remote cache tensors alive.

Recommendation: stable baseline-first layout is technically promising for nearby
reviews/repairs, conditional on supported Codex cache boundaries/retention. Do not
build daily savings estimates around it yet. Never add warm-up calls, keep-alives
or old ticker conversation history merely to inflate the cached-token percentage.

Sources read22Oct:
- https://developers.openai.com/api/docs/guides/prompt-caching
- https://learn.chatgpt.com/docs/pricing

No claim of changed weekly usage or model quality follows from this investigation.
