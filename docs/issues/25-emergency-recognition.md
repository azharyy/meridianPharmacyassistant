# Repair emergency recognition

Implements FIXES E2, authorized 2026-11-16. Branch:
`codex/emergency-recognition`, stacked on E1 d376d08 (local).
Read PLAN Safety policy, Architecture and Module map/rules.
Scope: `assistant/safety/emergency.py`, its mirrored test and
`tests/assistant/test_pipeline.py`. No model, clinical dosing engine, dependency,
contract, prompt or eval data changes. Detection only; E4 handles HTTP scheduling.

Acceptance criteria, each with full offline check and HANDOFF checkpoint:
- [ ] 1. Explicit current recurrence after an adjacent historical emergency
  sentence and current throat tightness get the existing 911 reply/offer with
  zero model/API calls. Prove detector and pipeline cases, including model down.
- [ ] 2. Water, a whole single tablet and a 10 mg strength do not independently
  trigger overdose. Retain genuine overdose, bulk medicine containers, large
  tablet counts and existing child-ingestion checks. Add detector regressions.
- [ ] 3. Unrelated present-time words after a historical event and negative
  recurrence do not trigger; existing historical and label-question tests pass.
  Recognition patterns remain centralized in the existing module.

Do not reinterpret classification as advice that any reported dose is safe.
