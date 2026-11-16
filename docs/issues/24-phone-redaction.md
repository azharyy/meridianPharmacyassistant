# Redact international and context-marked local phones

User authorized FIXES E1-E5 implementation on 2026-11-16. Branch:
`codex/phone-redaction`, based on the local issue-23 plan commit e953c2c.
Read FIXES E1 and PLAN Architecture, Module map and Safety policy.

Scope: `assistant/redaction.py`, mirrored `tests/assistant/test_redaction.py`,
`tests/assistant/test_pipeline.py`, `tests/assistant/test_escalation.py`.
No dependencies, contracts, private verification, prompts or eval data changes.
Use synthetic contacts only. Keep supported recognition forms documented in the
module; do not claim universal phone recognition.

Acceptance criteria (checkpoint and full offline checks after each):
- [ ] 1. Explicit international phones (+ or 00 country prefix, grouped digits,
  optional trunk parentheses) and context-marked seven-digit local phones are
  redacted. Fake-model requests, session messages, captured logs and ticket
  summaries contain no synthetic phone. Prove with redaction parameter cases,
  pipeline integration and summary integration tests.
- [ ] 2. Existing US/email/order redaction remains correct; ages, dose ranges,
  strengths and SKUs stay intact. Add edge cases for the new patterns and run
  existing preservation/idempotence tests. No arbitrary numeric suppression.

Use AGENTS.md checkpoints and update HANDOFF.md as edits/checks happen.
