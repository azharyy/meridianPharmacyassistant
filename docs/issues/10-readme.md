Builder: Claude · Review: CI and the user's read · Starts after: 9
Folders: `README.md` only.
Plan sections: Requirements and how each is met; Architecture; Module map and rules; Safety policy; Mock Meridian API (How order privacy is enforced); Evaluation; Decisions; Not in scope: next steps.

The README sections the plan leaves for the end of the build. One pull request. Describe what was built, not what was planned: read the code before writing about it.

Amendment (2026-11-16, `docs/FIXES.md` section C): the evaluation criterion also accepts numbers from the saved development reports, because `eval/REPORT.md` describes the earlier Groq configuration and can't describe the current default model. Section C's evidence table, provenance notes, stale-card behavior and demo script are part of this issue.

Acceptance criteria
- [ ] Architecture: the turn pipeline's eight steps, the component table with the reason each part is separate, and the assistant's routes, matching the code as merged.
- [ ] Where things live: the module map and the "where to change things" table, checked against the tree.
- [ ] Guardrail design: the policy table, the order of the safety layers, how order privacy is enforced, and what happens when the model fails.
- [ ] Evaluation: how to run it, the metrics and their targets, the judge and its calibration, and the measured change. Every number comes from `eval/REPORT.md`, or from the saved development reports (`eval/results/dev.md`, `eval/results/dev-compare.md`) with its configuration and development scope named beside it; nothing is invented.
- [ ] AI usage: how Claude Code and Codex were used in this build (who built which issue, the handoff note, the reviews), taken from the pull requests and the `HANDOFF.md` log, for the user to check and reword.
- [ ] Limitations and next steps: the plan's next steps, plus anything cut or left unfinished, said plainly.
- [ ] The "Status: in progress" line and the placeholder comment are gone, and every command, path and file name in the README exists.

Tests: none automated. Done when `make check` still passes and every command, path and file name in the README has been checked against the tree.
Follow the Session protocol in AGENTS.md.
