# Bind handoff confirmations to their offers

Either agent continues this issue until its limit reserve, then completes
HANDOFF.md before stopping. Branch: `codex/handoff-offer-binding`, initially
based on issue14 commit `0c48fe9`; PR base is `codex/handoff-offer-contract` until
that contract PR is merged, then `main`. User authorized continuation and the
proposed scope on 2026-11-16. No repeated approval gate.

Read docs/FIXES.md Shared continuation protocol and B in full; PLAN Architecture,
Safety policy / Escalation and Chat widget. Only the current offer is actionable.
New offers supersede old ones; a non-offer reply keeps the earlier offer. Reject
stale cards rather than silently redirecting their confirmation. Do not retain
an offer history or serialize chat behind model/network calls.

Scope: assistant/session.py, pipeline.py, escalation.py, app.py, policy.py;
widget/meridian-chat.js and a small widget/handoff-test.html fixture; mirrored
tests/assistant/ modules. eval/runner.py and tests/eval/test_runner.py only to
bind a scripted card confirmation to the offer it confirms. No contracts,
dependencies, prompts, retrieval, case text, metrics or saved result changes.

Steps: allocate UUID4 on each HandoffOffer; attach the allocated object's ID to
all offered replies (including order verification); atomically validate/capture
the requested current offer; release session lock before ticket I/O and use
session:UUID for idempotency. Unknown/stale IDs allocate nothing and return HTTP
409 with fixed policy text in the existing HandoffReply shape. Null is the
header's explicit current-conversation action. Widget cards/retries capture an
ID; old controls and callbacks stay retired, successes stay disabled, stale
responses have no retry, and a failed null header request has no automatic retry.
Emergency banner and input remain available during all pending work.

Acceptance criteria (run full offline checks and checkpoint after each):

- [ ] 1. Emergency -> fallback -> confirm old ID returns 409 without a ticket;
  current emergency confirmation retains emergency urgency. Unknown IDs never
  allocate an offer or call the ticket API. Session recreation rejects old IDs.
  Prove in tests/assistant/test_app.py, test_session.py, test_escalation.py.
- [ ] 2. Concurrent/repeated current confirmations and lost-response retries use
  one UUID key and one ticket; stale retries never create a newer offer's ticket.
  Extend existing tests/assistant/test_escalation.py idempotency tests.
- [ ] 3. Event-controlled overlapping model/ticket work keeps each captured
  offer's risk/urgency/ID, with emergency replies making zero model calls and
  finishing while the other work is blocked. No lock across network calls.
  Prove in tests/assistant/test_pipeline.py and test_escalation.py.
- [ ] 4. Non-offer replies preserve earlier offers, header without an offer works,
  false confirmation creates nothing, order-verification offers carry IDs,
  and the fake eval runner sends the current card ID. Prove in mirrored tests.
- [ ] 5. Real widget with deferred fake fetch responses proves out-of-order
  replies, success/double-click, transient retry bound to the same ID, stale
  rejection, failed header without retry, and old callbacks after retirement.
  Use a small local browser fixture without installing a frontend stack; record
  the observed results in HANDOFF.md. Existing full offline suite remains green.

PR description must link this issue, explain stale rejection and UUID keys,
list proven regressions/check result and identify any remaining browser/manual
check. Contracts touched: none (uses issue14). This issue does not claim improved
live-model quality or modify archived evaluation measurements.
