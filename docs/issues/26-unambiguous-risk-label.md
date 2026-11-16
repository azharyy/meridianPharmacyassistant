# Withhold ambiguous product labels in safety replies

Implements FIXES E3, authorized 2026-11-16. Branch:
`codex/unambiguous-risk-label`, stacked on E2 01336ee.
Read PLAN Architecture, Module map and Safety policy.

Scope: `assistant/retrieval/index.py`, `exact.py` only if necessary, mirrored
retrieval tests, `tests/assistant/test_app.py`, `tests/eval/test_runner.py`.
Necessary caller scope added after inspection: `assistant/pipeline.py` and its
mirrored test; it currently discards all but the first routed product mention.
No contract, dependency, prompts, catalog, eval case/result or metric changes.

Acceptance (full checks and HANDOFF checkpoint after each):
- [x] 1. Ambiguous ingredient/alias families never show a random variant's label;
  spray/tablet and strength regressions through fake-model HTTP retain the fixed
  refusal/offer and have no label sources. Prefer abstention to a new parser.
- [x] 2. Unique explicit SKU/full name takes precedence; conflicting explicit
  products, including separate router mentions, abstain. Unambiguous ingredient/
  alias matches still cite verbatim sections. Both retrieval flag values agree.
- [x] 3. Ordinary catalog retrieval/comparison remains unchanged; eval evidence
  capture records displayed labels only, including an intentionally omitted label.

Record exact tests and commits. No live evaluation or held-out reads.
