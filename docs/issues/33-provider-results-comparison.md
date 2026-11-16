# Compare historical Groq results with live OpenCode results

Latest user clarification: use the existing project credentials for live tests
and compare the preserved Groq results with newly measured OpenCode results.
This authorizes loading the user's .env through the normal uv runner and the
requested live calls, superseding the earlier user-run-only restriction for
this experiment. Never display/copy key values or inspect the key file contents.
No fresh Groq calls or provider change: new evaluations remain OpenCode only.

Branch: `codex/provider-results-comparison`, based on b4d3cdf. Read PLAN Model
calls/Evaluation, issue09 historical amendments and issue32. Scope: new files
under `eval/experiments/opencode-2026-11-16/`, `README.md`, `docs/TEST_REPORT.md`,
`docs/FIXES.md`, this issue and HANDOFF. No runtime, cases, labels, prompts,
dependencies, protected files or historical result edits. Use existing helpers
for a one-off comparison report instead of adding a new reporting framework.

Acceptance/checkpoints (full offline checks after each):
- [ ] 1. Load credentials securely using the project runner, execute fresh Kimi
  calibration, GLM-5.3 development and GLM-5.3-Flash development comparison into
  the new experiment/results directory. Record actual outputs/failures; do not
  silently change models, hide timeouts or claim failed calls succeeded.
- [ ] 2. Execute both full60-case held-out runs with GLM-5.3/Kimi, exact-match0
  then1; preserve raw results and report. If external failure blocks a run,
  preserve and explain actual evidence instead of inventing scores.
- [ ] 3. Generate a metrics/configuration comparison against the archived Groq
  pair. Check matching cases and paired-run consistency; disclose different code
  and judge as confounders. Update README/test report/fix status and HANDOFF from
  measured evidence. Full offline suite green; archived files unchanged.

Live model requests use synthetic/public data and existing redaction. No test
ever calls a real model; live eval commands are separate from the offline suite.
