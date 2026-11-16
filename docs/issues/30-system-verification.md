# Verify the assembled project

User requested full project/integration testing on 2026-11-16. Branch:
`codex/system-verification`, based on 6c7672a (complete local E1-E5 chain).
Read PLAN Architecture, Chat widget, Mock API and Evaluation command restrictions.
Scope: this issue, `docs/TEST_REPORT.md`, gitignored `HANDOFF.md`; temporary
workspace-only verification harness/artifacts may be created and removed.
Production/test fixes, if needed, get a separate scoped issue before editing.

Acceptance (one verification checkpoint):
- [x] 1. Run lint/format/full offline tests, real loopback HTTP checks of the
  assistant and mock API with scripted FakeSender and real catalog retrieval,
  browser checks of widget demo/sources/order form/escalation/keyboard and its
  existing handoff/preview fixtures. Record exact results and any blockers in
  TEST_REPORT and HANDOFF; preserve saved evaluation data and leave no servers
  running. No paid model calls, live eval/judge/fetch targets, .env access,
  protected files, dependency installs or claims of universal correctness.

Only synthetic contacts/orders and disposable local tickets. A green fake-model
run proves integration, not actual model routing quality or hosted latency.
