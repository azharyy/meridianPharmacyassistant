# Update the review fix plan (planning only)

The user requested feasible follow-ups from the 2026-11-16 Ponytail/Roast review
in the existing fix plan, explicitly without starting implementation.

Scope: `docs/FIXES.md`, this issue file and the gitignored `HANDOFF.md`.
Branch: `codex/review-fix-plan`. No runtime, test, contract, dependency, prompt,
evaluation-data, saved-result, README or protected PLAN changes. No live calls.

Update the active queue with the reproduced emergency, contact-redaction,
ambiguous-product and worker-pool defects, plus evaluation fingerprint coverage.
Give each future issue a bounded scope, regression checks and dependencies.
Separate submission actions and deferred work from feasible code fixes. Mark
completed A-D work as historical so stale model numbers, Git instructions and
previous implementation authorization cannot restart it. Preserve earlier work.

Acceptance criterion
- [ ] The plan contains a prioritized, bounded queue with concrete acceptance
  checks, separates pending video/validation from implementation, records the
  judge-context deferral, and explicitly authorizes planning only. Local links
  and `git diff --check` pass; the full offline checks remain green. Only the
  scoped documentation changes. No new automated tests for prose.

Follow the AGENTS.md session/checkpoint protocol for this documentation issue.
Commit the plan locally after checks; do not push or open an implementation PR.
