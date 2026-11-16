# Remove proven dead code and obsolete documentation

User request: audit the entire repository and remove code that cannot run and
old or redundant documentation that no longer serves a purpose. Preserve all
supported behavior, safety/privacy guards, test coverage and useful provenance.

Branch: `codex/repo-cleanup`, based on `03858c9`.
Read PLAN sections Architecture, Module map and rules, and Stack, layout and
commands; consult feature sections only when a candidate requires them.

Scope: `assistant/`, `api/`, `scripts/`, evaluation Python modules (excluding
cases, labels, prompts and saved measurement files), `widget/`, mirrored tests,
`README.md`, `docs/FIXES.md`, `docs/TEST_REPORT.md`, `docs/issues/`,
`artifacts/widget-preview/`, and HANDOFF. Audit other tracked files read-only.
No contracts, dependencies, protected instructions/configuration, architecture
test or PLAN edits. Do not inspect `.env` or `eval/cases/test.jsonl`, run live
models, alter catalog/policy data, or regenerate historical measurements.

Acceptance criteria (full offline checks and a commit after each):
- [x] 1. Trace code candidates through callers, tests, fixtures and entrypoints;
  remove only proven unused code or unreachable branches, updating tests that
  solely exercise removed internals. Record the evidence and retained edge cases
  in HANDOFF. Supported runtime and tooling behavior remains covered and green.
- [x] 2. Remove obsolete/redundant documentation or duplicated preview artifacts
  with no distinct remaining use, repair affected links, and retain unique
  instructions, issue history and evaluation evidence. Record the audit's scope
  and exclusions; local documentation links and full offline checks pass.

Validation: the Makefile check target's ruff lint, ruff format check and complete
offline pytest suite (run directly with the existing virtualenv if make is
unavailable); targeted caller/reference searches; local Markdown link checks;
`git diff --check`. No new dependency or broad refactor is needed.
