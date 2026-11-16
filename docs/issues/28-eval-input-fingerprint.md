# Fingerprint the actual evaluation runtime inputs

Implements FIXES E5, authorized 2026-11-16. Branch:
`codex/eval-input-fingerprint`, stacked on the tested E1-E4 chain.
Read PLAN Evaluation and Module map. Scope: `eval/cli.py`,
`tests/eval/test_cli.py`, `tests/eval/test_compare.py`. No runtime, cases,
judge/calibration, metric definitions, saved reports/results or dependencies.

Include API/contract Python code and actual `data/policies/*.md` alongside the
existing runtime code/prompts/public data. Deterministic explicit file types,
excluding generated caches/results, held-out cases and private files. The case
set has its own fingerprint. No live eval commands or case-file reads needed.

Acceptance (checkpoint/full offline checks each):
- [ ] 1. Temporary synthetic policy/API/contract file changes alter the digest;
  unchanged trees give the same digest. Prove with temporary-root fixtures.
- [ ] 2. Actual runtime input changes reject stale comparisons before clients or
  API start; unrelated root prose, caches, results and cases do not alter digest.
- [ ] 3. Archived measurements remain unchanged. Record in HANDOFF that old
  development fingerprints are incompatible; future comparison requires fresh
  compatible user-run measurements, never silent report replacement.

Preserve all prior evidence; no held-out rerun or evaluation-method claim.
