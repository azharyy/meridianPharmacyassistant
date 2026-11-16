# Keep emergencies responsive under normal request saturation

Implements FIXES E4, authorized 2026-11-16. Branch:
`codex/emergency-request-scheduling`, stacked on the tested E2/E3 follow-ups.
Read PLAN Architecture, Module map and Safety policy. Scope: `assistant/app.py`,
`assistant/pipeline.py` only if needed, and their mirrored tests.
No dependencies, contracts, model/prompt, API, or eval result changes.

Keep the cheap emergency check outside the normal blocking-worker queue.
Reuse the existing pipeline for emergency redaction/rendering/offer/turn/logging;
ordinary turns must run in the framework thread facility. No model or API I/O
on the event loop. Do not raise worker limits or broadly convert the service.

Acceptance criteria (full checks + HANDOFF checkpoint each):
- [x] 1. Event-controlled HTTP saturation test fills the test limiter's capacity
  with fake blocked normal work; emergency finishes before release, with fixed
  reply/offer and no model/API calls. Bounded timeouts only, no timing sleeps.
- [x] 2. HTTP emergency path preserves redaction, state/history, offer binding
  and logs. Existing normal/private verification/stale-card/overlap checks pass.

No session lock spans network work; no second emergency renderer or pipeline.
