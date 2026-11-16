# Use OpenCode only for active evaluation and planning

The user's latest instruction cancels the unstarted Groq rerun and requires
OpenCode API/models for evaluations. No Groq implementation or live calls were
made. Branch: `codex/opencode-evaluation`, based on b26564c.

Scope: `eval/cli.py`, `tests/eval/test_cli.py`,
`tests/eval/test_calibration_cli.py`, `README.md`, `docs/PLAN.md`, `docs/FIXES.md`,
`docs/TEST_REPORT.md`, this issue and HANDOFF. The explicit request to remove the
provider from the plan authorizes this named PLAN update. No other protected
files, dependencies, app defaults, prompts, labels or archived scores change.

Read PLAN Model calls, Evaluation, Stack/commands and Decisions, plus issue09's
historical amendments. Active runtime GLM-5.3; comparison GLM-5.3-Flash; judge
Kimi K3.1 Pro, all on OpenCode Go with OPENCODE_API_KEY.

Acceptance criteria (full offline check and HANDOFF checkpoint each):
- [x] 1. Live evaluation/client construction/calibration reject non-OpenCode or
  mixed-provider roles before requests. Tests use synthetic settings and fakes;
  historical result/calibration validation still works without relabeling data.
  Add an optional CLI output directory so the requested new comparison can use
  its own experiment/results tree without replacing archived measurements.
- [x] 2. PLAN and FIXES contain no Groq plan instructions; update obsolete model,
  key, second-provider and human-label claims. README/TEST_REPORT distinguish
  OpenCode-only future evals, historical measurements and actual pending status.
  Remove cancelled-rerun artifacts. Verify links and full suite; no fresh scores
  unless a user-run live evaluation actually completes.

Historical artifacts are evidence, not current defaults; preserve them unchanged.
No live run/eval/judge command, .env access or key disclosure in this issue.
