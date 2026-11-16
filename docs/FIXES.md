# Review fixes and submission plan

Updated 2026-11-16 after the user authorized implementation of the
[issue 23](issues/23-review-fix-plan.md) plan. E1-E5 are implemented and tested
locally in issues 24-28; [issue 29](issues/29-review-fix-documentation.md) records
completion and remaining validation. The implementation commits are stacked on
local issue branches, pending publication/review. [Issue 33](issues/33-provider-results-comparison.md)
has now completed fresh live calibration, development checks and the full held-out pair.

Current evaluation policy ([issue 32](issues/32-opencode-evaluation.md)) is
OpenCode Go only: GLM-5.3 runtime, GLM-5.3-Flash development comparison and
Kimi K3.1 Pro judge. The new held-out pair scored 46/60 baseline and 49/60 improved,
with improved p95 13.118s; accuracy, escalation precision and latency miss targets.
The [measured comparison](../eval/experiments/opencode-2026-11-16/PROVIDER_COMPARISON.md)
preserves historical evidence and identifies changed code/judge as confounders.

The earlier A-D queue has been addressed through issues 14-22: offer binding,
README completion, the named-product fix, the default-model decision and the
judge-context investigation. A-D below summarize those outcomes and link their
issue scopes and tests. The video and validation gaps remain pending.

The initial plan is [issue 13](issues/13-fix-plan.md). Record each future issue's
implementation criteria in `HANDOFF.md` once implementation is requested.

Use one shared queue. Codex and Claude can both build every item; there are no
separate owners. The active agent works through the queue while reserving enough
capacity for checks and a complete handoff, then stops **before** its hard limit.
Everything it did must be recorded in `HANDOFF.md`; the next agent continues
from that record without needing the chat.

## Review findings and fixes

| Priority | Problem and evidence | Smallest useful fix |
| --- | --- | --- |
| 1 | International phone numbers survive redaction and reach model requests and ticket summaries. | E1: extend bounded phone recognition, preserving doses and product identifiers. |
| 2 | Current emergencies across sentences and throat tightness are missed; water and ordinary dose statements trigger overdose. | E2: repair the reproduced recognition cases with positive and negative regressions. |
| 3 | Ingredient matching attaches oral-tablet directions to a topical-spray question, or selects the wrong strength. | E3: omit labels when exact product identity remains ambiguous. |
| 4 | All 40 normal HTTP worker slots can be waiting on model calls, delaying even a recognized emergency. | E4: keep the immediate emergency path outside the normal blocking-work queue. |
| 5 | Evaluation fingerprints omit API/contract code and the real policy directory. | E5: hash the actual runtime inputs so incompatible runs cannot be compared as one configuration. |
| Submission | Video, human label review and browser acceptance remain pending. The current held-out pair is measured and misses accuracy, precision and latency targets. | E6: finish external deliverables; preserve the completed experiment and investigate quality with development/synthetic cases. |

The brief does not mandate 90% accuracy or four-second p95; those are this
project's targets. Missing them must be disclosed. Documentation alone does not
fix performance, and a passing offline suite does not establish model quality.

## Shared continuation protocol

Follow the [AGENTS session protocol](../AGENTS.md#session-protocol) and
[handoff template](HANDOFF_TEMPLATE.md) for checkpoints, checks, pause/resume
and Git actions. The active issue and `HANDOFF.md` determine the next task;
historical proposals do not restart completed work. Either agent may continue
an issue, with one implementing writer per file in this checkout. Reserve
capacity for checks and a complete handoff before starting another criterion.

The synchronization in [issue 16](issues/16-git-permissions-and-sync.md) was a
one-time instruction, not continuing permission to rewrite main or remote history.
For sandbox-specific offline-check commands, see the
[verification report](TEST_REPORT.md#reproduction-and-remaining-acceptance).

## Historical A-D proposals

The outcomes below replace superseded implementation instructions. Linked issues
retain their scopes and regression criteria; the README and saved reports hold
the current behavior and measured evidence. These completed items do not authorize
new work. Remaining submission and validation tasks are listed in E6.

## A. Define the small handoff contract change

[Issue 14](issues/14-handoff-offer-contract.md) added nullable UUID-v4 `offer_id`
fields to chat replies and handoff requests, with validation, example payloads
and schema snapshots. Code generates the identity; customer confirmation remains
required. This prepared the boundary for the binding fix in B.

## B. Bind confirmations and retries to the displayed offer

[Issue 15](issues/15-handoff-offer-binding.md) binds each card and retry to its
captured offer ID. Only the current offer is actionable; a reply without a new
offer preserves it. Stale or unknown IDs return HTTP 409 without a ticket, and
concurrent confirmations use one `session:offer_id` idempotency key. Capturing
an offer releases the session lock before network calls, so emergency replies
remain available.

The widget retires older controls and callbacks. A transient failure may retry
the same current card; stale cards and failed header actions offer no automatic
retry. The header's null ID remains an explicit current-conversation action.
The [browser fixture](../widget/handoff-test.html) covers deferred responses;
current browser and keyboard acceptance remains listed in E6.

## C. Finish the submission and make the evidence unambiguous

[Issue 10](issues/10-readme.md) and [issue 22](issues/22-readme-brief-coverage.md)
completed the README's setup, architecture, guardrails, evaluation evidence,
AI usage and [demo script](../README.md#demo). Measurements identify their
model, judge, code and development/held-out scope; archived reports and AI-label
provenance remain intact. The latest comparison is linked above.

The demo video, independent human label review and live widget/keyboard
acceptance remain pending under E6. Documentation and offline checks do not
establish improved live-model quality.

## D. Small quality/latency follow-up, if needed before submission

1. [Issue 17](issues/17-named-product-lookup.md) fixed a reproduced development
   failure by using exact named-product lookup for safety replies, leaving
   ordinary catalog retrieval unchanged. E3 later addressed ambiguous variants.
2. [Issue 20](issues/20-judge-context-check.md) reproduced the judge's missing
   conversation context but found limited measured impact, so it deliberately
   left the evaluator unchanged. This limitation remains deferred below.
3. [Issue 18](issues/18-default-glm-5-3.md) records the user's GLM-5.3 default
   choice after a fresh development comparison. GLM-5.3-Flash remains selectable;
   the original proposal to wait for that comparison is complete.

Further quality work uses development or synthetic cases. Preserve historical
scores and original-label artifacts; a new held-out experiment needs its own
user authorization and separate outputs. The later authorized OpenCode experiment
is recorded in [issue 33](issues/33-provider-results-comparison.md).

## E. Feasible follow-ups from the latest review (completed locally)

All reproductions below used synthetic inputs and offline fakes. The review's
baseline was 1,365 passing tests. E1-E5 now have regression coverage and 1,454
tests pass, with Ruff lint/format green. Full checks and commits were recorded
after each criterion in HANDOFF.md. Existing dependencies/contracts were sufficient.
No improvement to live model scores is claimed by these offline checks.

### E1. Close the reproduced phone-redaction gaps

Proposed slug: `phone-redaction`. Scope: `assistant/redaction.py`,
`tests/assistant/test_redaction.py`, and integration tests in
`tests/assistant/test_pipeline.py` / `test_escalation.py`.

Completed in [issue 24](issues/24-phone-redaction.md), including sentence-boundary
regressions found during review.

`Call me at +44 20 7946 0958` survived redaction; the review observed it in the
fake model's request and the ticket summary. Add bounded recognition for
country-code/grouped international phones and context-marked local phones such
as `call me at 555-0142`. Keep patterns centralized. Preserve email/order
redaction, ages, doses and SKUs; do not turn every numeric sequence into a phone.
Document supported forms without claiming universal contact recognition.

Acceptance:
- [x] Synthetic international and context-marked local numbers are absent from
  fake-model requests, stored messages, captured logs and ticket summaries.
- [x] Existing US/email/order cases still redact. Dose ranges, strengths, ages
  and catalog identifiers keep their existing intended behavior. No new package
  or changes to private order verification are needed.

### E2. Repair emergency misses and false overdose matches

Proposed slug: `emergency-recognition`. Scope:
`assistant/safety/emergency.py`, `tests/assistant/safety/test_emergency.py`, and
`tests/assistant/test_pipeline.py`. This issue changes detection only; E4 handles
HTTP scheduling. Emergency/injection precedence and fixed replies stay intact.

Completed in [issue 25](issues/25-emergency-recognition.md), including reviewed
strength-unit and medicine-container regressions.

Handle explicit current recurrence across adjacent sentences, for example
`I had a seizure last year. I am having one again now.`, and current throat
tightness. Constrain ingestion/count patterns by context so `I drank a bottle
of water`, `I swallowed a whole tablet of aspirin`, and `I took 10 mg of
cetirizine this morning` do not independently establish an overdose. This is
classification of the reported event, not a judgment that a dose is safe.
Keep recognition patterns centralized at the top of the existing module; do not
add a medical dosing engine or a model call.

Acceptance:
- [x] The recurrence and throat-tightness regressions return the fixed emergency
  reply and offer with zero model/API calls, including when the model is down.
- [x] The ordinary-ingestion examples do not trigger the emergency detector;
  explicit overdose, swallowed medicine bottles and child ingestion remain
  covered. Existing historical-event and label-question tests still pass.
- [x] `I had a seizure last year. Are you open now?` does not become an emergency.
  A present-time word elsewhere must not globally override historical context.

### E3. Withhold ambiguous product labels in safety replies

Proposed slug: `unambiguous-risk-label`. Scope:
`assistant/retrieval/index.py`, `assistant/retrieval/exact.py` only as needed,
their mirrored tests, and integration assertions in
`tests/assistant/test_app.py` / `tests/eval/test_runner.py`.

Completed in [issue 26](issues/26-unambiguous-risk-label.md). Caller inspection
also required `assistant/pipeline.py`: pass all routed product mentions to the
strict lookup instead of discarding later mentions. No general retrieval change.

Before issue 26, `named("diphenhydramine 2% spray")` chose oral 25 mg tablets;
`famotidine 10 mg` chose 20 mg. The full risk path displayed those directions
even with the correct model risk label. Issue 17 removed keyword guessing but
left ingredient/alias variants ambiguous.

Use the smallest safe rule: a unique exact full product name or SKU can identify
a record; ingredient/alias matching may attach a label only when it identifies
one distinct product. Multiple variants return no product and therefore the
existing fixed refusal plus pharmacist offer, without label text. Do not add a
form/strength parser at this stage. Conflicting explicit identifiers must also
abstain. Preserve ordinary catalog retrieval, which may return multiple records.

Acceptance:
- [x] The spray and strength examples never show another variant's directions
  in full fake-model HTTP responses. Ambiguous cases retain the fixed refusal
  and offer, with no orphan label sources.
- [x] Exact SKU/full-name and unambiguous ingredient/alias matches still show
  verbatim text with correct sources. Multiple explicit products do not silently
  select the first. Behavior is independent of the retrieval feature flag.
- [x] Normal catalog search/comparisons and eval evidence capture still work;
  an intentionally omitted label is not recorded as displayed evidence.

### E4. Keep emergencies responsive when normal work is saturated

Proposed slug: `emergency-request-scheduling`. Scope: `assistant/app.py`,
`assistant/pipeline.py` only for a small shared emergency-path extraction if
necessary, and their mirrored tests. Depends on preserving E2's detector behavior.

Completed in [issue 27](issues/27-emergency-request-scheduling.md); the dispatch
change fits in app.py and reuses the pipeline without extraction.

Before issue 27, the synchronous `/chat` handler waited for a shared worker before
checking the message. The review filled all 40 available workers with event-blocked fake
router calls; an emergency completed only after release. Raising worker limits
moves this failure threshold and is not the fix.

Check the cheap emergency path before dispatching ordinary blocking work. Reuse
the existing detector, redactor, renderer and offer/turn bookkeeping. Dispatch
normal pipeline work through the framework's existing thread facility. No model,
HTTP or ticket I/O may run on the event loop. Do not convert the whole service to
async, add a second renderer, or hold session locks across network calls.

Acceptance:
- [x] An event-controlled HTTP test fills the normal-work capacity and proves an
  emergency finishes before those calls are released, with zero model/API calls.
  Derive capacity from the test limiter; use events and a bounded failure timeout,
  not a sleep-based performance assertion.
- [x] The immediate path keeps redaction, fixed reply, offer identity, session
  recording and logging behavior. Normal chat, private verification, stale-card
  rejection and overlapping ticket/model work retain their existing checks.

### E5. Fingerprint the inputs the evaluation actually uses

Proposed slug: `eval-input-fingerprint`. Scope: `eval/cli.py` and
`tests/eval/test_cli.py` / `test_compare.py`. No cases, judge prompts, metric
definitions, saved reports or runtime behavior change.

Completed in [issue 28](issues/28-eval-input-fingerprint.md). Saved results and
calibration artifacts remain unchanged; old development fingerprints are incompatible.

Before issue 28, `implementation_digest()` omitted `api/` and `contracts/` code and
checked a root `policies/` directory instead of `data/policies/`. Include those actual runtime
inputs alongside existing assistant/eval code, prompts, catalog and public data.
Keep explicit paths/extensions and deterministic ordering. Exclude environment
files, keys, generated caches, results and held-out case contents; the case set
already has its own separate fingerprint.

Acceptance:
- [x] Temporary fixtures show that changing a policy, API module or contract
  module changes the digest; identical inputs produce the same digest.
- [x] Comparisons reject different implementation fingerprints before live
  work. Adding unrelated/cache/result files does not change the digest.
- [x] Archived measurements remain byte-for-byte unchanged. State that old
  development fingerprints are incompatible with new runs; any later comparison
  needs a fresh compatible pair, run by the user, not silent report replacement.

### E6. Submission and validation, separate from the code queue

- The README already contains setup, architecture, guardrail design and AI Usage.
  Do not rewrite it wholesale. After fixes, update only claims/limitations that
  their tests establish, under a separate documentation issue.
- The user records the existing 5-7 minute demo and supplies its link. Use the
  existing flow checklist, including cited answers, private order lookup, safety
  refusal and confirmed ticket summary. Keep video status pending until it exists.
- Human review of safety/calibration labels and live widget/keyboard acceptance
  remain explicit validation tasks. Do not present AI labels as human-reviewed.
- Keep the historical 60-case comparison, original-label artifacts and matching
  calibration intact. The newly completed OpenCode pair uses separate output
  paths and matching metadata for the code measured in issue 33. The user's explicit authorization
  permitted credential loading/live evaluation for this experiment; future live
  work still follows AGENTS.md unless the user authorizes it.
- Preserve the disclosed historical metrics and one-net-case improvement. The
  90% accuracy/four-second p95 targets are project goals, not submission thresholds
  from the brief. No metric improvement is claimed for this planning update.

### Deferred at this stage

- Judge conversation context: [issue 20](issues/20-judge-context-check.md)
  investigated it and deliberately left it unchanged because the measured effect
  was limited. Revisit only as an explicit evaluation-method change, with redacted
  history, synthetic fake-request tests and recalibration before new claims.
- Ingredient/alias caching and other micro-optimizations: retrieval already found
  29/30 gold source sets in the historical runs. Prioritize correct selection and
  measured model latency; profile again before adding caches or shortcuts.
- Vector databases, new agent frameworks/dependencies, formulation parsers,
  broad async conversion, model training, extra languages and order OTP flows
  would expand this bounded fix round. They are not prerequisites for these fixes.
- Other audit notes in the handoff are not silently added to this queue. In
  particular, do not deduplicate a helper by importing one pipeline step into
  another; the architecture rules still apply.

## Next action

E1-E5 code and this completion note are ready for review on local stacked issue
branches. Publish/review one issue at a time, consolidating same-issue follow-up
commits as needed without rewriting main or a remote branch. Keep E6's video,
human-label review, live widget acceptance and any new live measurements pending
until they are actually completed. Do not restart E1-E5 or rerun archived evaluations.
