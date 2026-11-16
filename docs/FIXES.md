# Review fixes and submission plan

Written 2026-11-16 after the whole-project review. The user has now requested
implementation. The initial documentation task is [issue 13](issues/13-fix-plan.md);
Git-permission/synchronization instructions are in [issue 16](issues/16-git-permissions-and-sync.md).
Record completed implementation criteria in `HANDOFF.md`.

Use one shared queue. Codex and Claude can both build every item; there are no
separate owners. The active agent works through the queue while reserving enough
capacity for checks and a complete handoff, then stops **before** its hard limit.
Everything it did must be recorded in `HANDOFF.md`; the next agent continues
from that record without needing the chat.

## What matters most

| Priority | Problem and evidence | Smallest useful fix |
| --- | --- | --- |
| 1 | A card confirms whichever offer is current on the server. Emergency, then fallback, then clicking the emergency card creates a routine ticket. `widget/meridian-chat.js` sends no offer identity; `assistant/escalation.py` uses the current offer. | Give each card an offer ID. Reject stale confirmations instead of filing a different offer. Retire obsolete controls. |
| 2 | The README's architecture, guardrails, evaluation, AI usage and limitations sections are empty. These are submission requirements. | Finish existing [issue 10](issues/10-readme.md), using the implementation and recorded evidence. Include the demo checklist and eventual video link. |
| 3 | The preserved held-out improvement is 50/60 to 51/60; accuracy and latency miss the project's targets. Those runs used the previous provider/model. | Explain exactly what was measured. Diagnose current development failures and timings before choosing one small quality/performance change. Preserve the old held-out runs. |

The brief does not mandate 90% accuracy or four-second p95; those are this
project's targets. Missing them must be disclosed. Documentation alone does not
fix performance, and a passing offline suite does not establish model quality.

## Shared continuation protocol

1. Before implementation, read `AGENTS.md`, this file, the active issue and
   `HANDOFF.md`. Check the branch, working tree and commits against the note.
   The existing note belongs to issue 9; settle its recorded PR/branch state
   before starting a new implementation branch. Do not assume it was merged.
2. Use the queue below, one issue and one PR at a time. Before starting A or B,
   create its issue file with the listed scope, steps, criteria and tests; read
   it in full. C reuses issue 10. Do not create duplicate README work.
3. Either agent may continue the same issue and branch. A `codex/` or `claude/`
   prefix records how the branch started, not exclusive ownership. In this
   checkout there is only one writer; do not run two implementing sessions
   against the same files. No fixed builder/reviewer split is required.
4. At the first implementation session, use `docs/HANDOFF_TEMPLATE.md`, carry
   forward Project status, and paste the active issue. After **each** acceptance
   criterion run `make check`, record the proving tests and result, tick the
   criterion, and write one concrete next action. Hold no more than one
   criterion of unrecorded work.
5. Check available usage, token/context and time-limit signals at session start,
   after each checkpoint and before starting another criterion or long command.
   Reserve enough capacity for one full check run, documenting the diff and a
   final handoff message. Do not work up to 99% or wait for a hard cutoff. If
   the remaining capacity cannot cover the next step **and** that reserve, stop
   implementation now. If exact quota information is unavailable, say so; never
   invent a percentage. Keep checkpoints small and treat the first limit warning
   as a stop signal.
   At that point start nothing new: finish or revert the small edit in hand,
   run the checks and complete every handoff section with Status `paused`.
   Record each changed/untracked file and why, distinguishing pre-existing user
   changes from this session's edits, completed and remaining criteria,
   exact checks and outcomes (including failures or checks not completed),
   decisions and rejected approaches, blockers, branch and actual HEAD hash, and
   any running processes or temporary artifacts. Stop session-owned background
   writers before handing over; do not stop the user's unrelated processes.
   Reconcile `git status` and the diff
   against the note so **nothing done or left unfinished is undocumented**.
   Leave one exact next command/edit, report the state to the user, then stop
   before exhaustion. Do not start another task after writing the handoff.
6. The next agent follows the existing Resume protocol, verifies the tree and
   tests against the note, logs the takeover and continues the next unchecked
   criterion. A mismatch is reported rather than guessed around. Continue
   implementation; do not restart the issue merely because the agent changed.
7. Either agent may create/switch issue branches, stage scoped files, commit and
   push under AGENTS.md. A handover never requires a second PR. The user's
   2026-11-16 instruction authorizes the one-time force-with-lease sync to `main`
   and continuation of the proposed handoff contract/binding work; do not ask
   again for those already authorized actions. Later main/history rewrites still
   require an explicit user instruction.

Checks are offline: Ruff lint, Ruff format check and pytest. If `make` is absent,
run its three check commands directly. This sandbox's shared pytest temp/cache
directory can be inaccessible; use a fresh temporary directory inside the
workspace and disable pytest's cache provider if necessary. This is an execution
environment workaround, not a product fix. Never change the architecture test.

## A. Define the small handoff contract change

Proposed issue/PR: `14-handoff-offer-contract` / `handoff-offer-contract`.

**Authorization:** the user's implementation and Git follow-up on 2026-11-16
supersede the earlier approval/branch blockers for this named contract change.
Implement only issue 14's documented scope; normal protected-file rules still
apply to unrelated changes. No dependency or model-facing schema change is needed.

Scope: `contracts/chat.py`, the affected `contracts/examples/` replies,
`contracts/schemas.json`, and mirrored `tests/contracts/` fixtures/tests. If the
snapshot command rewrites the mock API snapshot, verify that its contents remain
unchanged; this proposal does not change the mock ticket API.

Steps:

1. Introduce an `offer_id` field on `ChatReply` and `HandoffRequest`: a nullable
   string with one documented UUID format, generated by code using stdlib
   `uuid4`, scoped to the existing session, not an authentication credential.
   Use `null` for replies without a card and the header's explicit
   current-conversation action. Do not expose only the existing counter: it
   restarts after session eviction/restart, so an old card could match a new one.
2. Make the addition compatible with current constructors during this contract
   PR, for example with a default of `None`. The following implementation issue
   must populate it on every real handoff-bearing response. The model never
   selects or writes it, and the existing `confirmed` check remains required.
3. Specify stale behavior: an unknown/superseded ID causes no ticket API
   call. Return HTTP 409 with the existing `HandoffReply` shape and a fixed
   explanation; the widget must not present an automatic retry for this case.
   A transient failure for a still-current offer keeps the existing retry flow.
4. Update affected examples, schema snapshots and validation tests through the
   existing contract-generation command. Do not hand-edit generated schemas.

Acceptance:

- [ ] Contract tests accept the documented offer-ID format and `null` header
  value, and reject empty or malformed IDs.
- [ ] Existing examples and snapshots pass; strict model output schemas are
  unchanged. `make check` is green. This PR alone is not advertised as the fix.

## B. Bind confirmations and retries to the displayed offer

Proposed issue/PR: `15-handoff-offer-binding` / `handoff-offer-binding`.
Starts after A. Read PLAN's Architecture, Safety policy / Escalation and Chat
widget sections, plus the existing escalation and session tests.

Scope: `assistant/session.py`, `assistant/pipeline.py`, `assistant/escalation.py`,
`assistant/app.py`, `assistant/policy.py`, `widget/meridian-chat.js`, their mirrored
tests, and a minimal `widget/` test fixture if needed. `eval/runner.py` and its
mirrored test may change only to pass the offer ID when its scripted action
confirms a displayed card. No case texts, metrics, prompts, retrieval or results
change. New code uses existing dependencies only.

Chosen behavior: **only the current offer is actionable.** A reply without a new
offer retains the earlier offer, as today. A new offer supersedes the old one;
old cards remain readable but cannot submit a different offer. Do not add an
offer-history database or keep every previous card alive.

Steps:

1. Start with the reproduced regression: emergency message -> model failure ->
   confirm the emergency card. Today this files a routine ticket. The new result
   must be a stale-offer response with zero ticket creation, not a silent switch
   to the fallback. Confirming the current emergency card still files an
   emergency ticket.
2. Add one UUID to `HandoffOffer` when it is allocated. Attach that exact ID to the reply
   returned for that turn. Use the returned offer object, not a later read of
   `session.handoff_offer`, which another request could replace. Cover every
   reply path that can offer a handoff, including order-form verification.
3. Pass the ID through `/handoff`. Validate and capture the current offer
   together under the existing short session lock. A supplied ID must
   match; `null` means the header's current-conversation action. Use the captured
   object for risk, urgency, summary and a `session:offer_id` idempotency key.
   The mock API still receives the same string field. This also prevents key
   reuse when a session is recreated. Never validate one offer and then file a
   freshly read one.
4. Release the lock before network calls. An accepted confirmation can complete
   for its captured offer even if a newer offer arrives meanwhile. Do not
   serialize chat behind model/ticket calls or make the 911 response wait.
5. Card buttons and their retries send the same captured ID. Retire old
   card/retry controls when a newer offer appears; keep successful confirmations
   retired. An old promise's `finally` must not reactivate a retired button.
   Use a small local generation to keep old callbacks retired; UUIDs are not
   sortable. A delayed response must not revive a retired control. The
   server's stale check remains authoritative if responses arrive out of order.
6. Handle HTTP 409 as a stale offer, display the fixed text from `policy.py` and
   offer no retry of that card. Never retry by dropping its ID or redirecting
   it to the current offer. A failed request may retry the same ID while it
   remains current; after supersession it fails safely. The header remains the
   separate, explicit way to request help for the current conversation. A header
   request sends `null` and does not learn an offer ID from `HandoffReply`, so
   suppress automatic Retry for that request. A fresh header click is a new
   current-conversation action; do not pretend it retries the previous offer.
7. Keep the emergency banner and chat input usable while a handoff is pending.
   Update misleading comments that imply any old card can always file its
   original offer. If preserving old cards becomes a requirement, stop and
   propose retained-offer state separately rather than expanding this fix.

Acceptance and proving tests, using fake model/HTTP clients:

- [ ] Emergency -> fallback -> old-card confirmation makes no ticket; a valid
  current emergency confirmation retains emergency urgency. Add the regression
  in `tests/assistant/test_app.py` / `test_escalation.py`.
- [ ] Repeated and concurrent valid confirmations produce one ticket; a lost
  response retry for the same current ID returns the same ticket. A stale
  retry never creates a newer offer's ticket. Extend the existing idempotency
  tests instead of replacing them.
- [ ] A delayed normal reply and a faster emergency reply cannot exchange offer
  identities. Emergency replies complete with zero model calls while another
  model/ticket call is blocked. Use synchronization events, not timing sleeps.
- [ ] A reply without an offer preserves the earlier card; header confirmation
  with no offer still works; `confirmed=false` still creates nothing. Order
  verification handoff replies also carry an offer ID. Evict/recreate a session
  and verify its old card cannot match or reuse the new offer's ticket key.
- [ ] Exercise the real widget with deferred fake `fetch` replies: out-of-order
  responses, double click, success, transient failure, stale rejection, a failed
  header request without automatic retry, and an old callback after retirement.
  Keep evidence in the handoff. Use an installed
  browser/test facility or a small local harness; do not add a frontend stack or
  substitute a source-string assertion for this behavior check.

Run `make check` after each criterion and record the exact proving test names.

## C. Finish the submission and make the evidence unambiguous

Reuse [issue 10](issues/10-readme.md), on a `readme` branch after B. Both agents may
continue it under the shared protocol above; its original Builder label is not
an exclusive assignment for this follow-up. Scope stays `README.md`.

Before starting, amend issue 10's evaluation criterion to permit explicitly
attributed numbers from the saved development reports as well as `eval/REPORT.md`.
Its current requirement that every number come from REPORT cannot describe the
current model. Record this narrow issue amendment in the handoff.

1. Fill in the architecture diagram (a small Mermaid diagram is enough) and the
   responsibility table. Explain why routing, retrieval/planning, private order
   handling, safety checking, rendering and escalation are separate. Distinguish
   model calls from plain code; describe the actual shortcuts in the pipeline.
2. Explain emergency-first handling, redaction, exact label text, source
   construction, order verification/lockout, confirmation and idempotency, and
   what happens when the model/API fails. Include the new stale-card behavior.
3. Add this evidence table, checking every value against the linked saved files:

   When copying it to the root README, use `eval/...` links instead of `../eval/...`.

   | Configuration | Evidence | Accuracy | p95 |
   | --- | --- | --- | --- |
   | Groq GPT-OSS 120B + Qwen judge | Historical 60-case [held-out comparison](../eval/REPORT.md) | 50/60 -> 51/60 (83.3% -> 85.0%) | 25.545 s -> 17.226 s |
   | OpenCode GLM-5.3-Flash + Kimi judge | Saved 12-case [development run](../eval/results/dev.md); current default model | 11/12 (91.7%) | 8.157 s |
   | OpenCode GLM-5.3 + Kimi judge | Saved 12-case [development comparison](../eval/results/dev-compare.md) | 12/12 (100%) | 2.083 s |

4. State that these are saved measurements of their recorded implementations,
   not fresh measurements of the code after this fix. Current-default held-out
   quality has not been measured. The historical gain is one net case in one
   paired run; retrieval success stayed 29/30. Do not describe this as a large or
   statistically established improvement. Report every metric requested by the
   brief, with raw counts, and keep the historical target misses visible.
5. Keep the AI-authored/AI-labeled provenance, pending independent human review
   and post-run label audit visible. Copy no held-out questions into prompts,
   aliases, tests or README examples. Do not claim human validation happened.
6. Finish AI Usage from the recorded PR/handoff history, limitations and the
   actual setup paths. Note deviations from the original PLAN's provider/model
   choices using [issue 9's amendments](issues/09-eval.md); do not silently
   restore the old defaults or the old judge to match the original plan.
7. Add a 5-7 minute demo script: normal cited product/store question, order form
   with synthetic details, wrong-contact refusal, safety refusal, confirmed
   pharmacist ticket, and an emergency response. Check keyboard operation and
   source chips. The user records the video and supplies its link; keep this
   deliverable explicitly pending until then. Do not invent a recording URL.

Acceptance:

- [ ] All issue 10 sections contain actual implementation details; links and
  commands are checked. No empty submission sections remain.
- [ ] Every number identifies its configuration and dev/held-out scope; archived
  results are unchanged. Model quality and human-label validation are not
  overstated. The one-case improvement and unmet targets remain disclosed.
- [ ] The four required demo flows, keyboard check and video status are recorded.
  Only completed deliverables are marked complete. `make check` remains green;
  new automated tests for README prose are unnecessary.

## D. Small quality/latency follow-up, if needed before submission

This is the next improvement task, not a promise that documentation fixes the
scores. Keep it behind A-C so a tuning exercise cannot displace correctness and
the required submission. Create a narrowly scoped issue only after diagnosis.

1. Use the development set and saved development timings only. Inspect the
   current default's `dev-009` risk/reply mismatch and its slowest stages. Separate
   model latency, timeout/retry and provider backoff from retrieval cost. Do not
   tune against the held-out failures or change gold labels to raise a score.
2. Check the evaluator before tuning the assistant: its evidence judge receives
   only the latest customer question. A contextual follow-up such as "How do I
   take it?" can lose the preceding product reference. This request-context gap
   was verified offline; it is not an established cause of `dev-009` or the
   reported 85% accuracy. Reproduce with two small
   synthetic conversations and inspect fake judge requests. If confirmed as the
   relevant failure, give the judge the necessary redacted context in a separate
   eval issue (`eval/runner.py`, `eval/judge/judge.py`, recorded-result types only
   if required, and mirrored tests). This changes the evaluation method; preserve
   old scores, document the difference and recalibrate before trusting new ones.
3. Prefer an existing configuration option over a rewrite. GLM-5.3 is an already
   supported candidate: its saved development comparison was faster and more
   accurate, but twelve cases do not establish reliability. Recommend a default
   switch only after a fresh, compatible development comparison and an explicit
   user choice about the recorded cost/allowance tradeoff. Do not switch now.
4. If a code/prompt defect is reproduced, fix only that defect, with synthetic
   regression cases and a scope listing the exact affected modules/tests. Avoid
   a vector database, new agents, model training, extra dependencies or a broad
   retrieval rewrite. Do not reduce safety checks or hide retry time to hit p95.
5. Live commands are user-run under the current repo rules. Never run `make run`,
   `make eval*` or `make judge*` as Codex. Preserve existing development evidence
   before an authorized new measurement. The historical `baseline`, `improved`,
   original-label artifacts, matching calibration and report remain preserved;
   do not rerun the held-out set or overwrite them. A new held-out experiment
   needs a separate user decision and separate output paths.
6. End with a factual before/after development result or a clear unresolved
   limitation. Do not claim 90% held-out accuracy or sub-four-second general p95
   from offline tests, a changed configuration or a twelve-case development run.

## First action when implementation is authorized

Follow the issue-16 Git sync, then create the `handoff-offer-contract` branch and
implement issue 14. The contract/binding work is authorized; live evaluation
remains subject to the existing user-run rule.
