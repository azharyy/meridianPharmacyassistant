@AGENTS.md

# Claude Code only
- You build every issue in `docs/issues/`, one at a time, in this order: 1, 2, 3,
  4, 7, 5, 6, 8, 9, 10. Issue 5 waits for the user's
  `eval/cases/handwritten_questions.md`: build 8 while you wait, then stop and ask.
  If your quota runs out, Codex continues from `HANDOFF.md`; when the user asks you
  to resume an issue Codex worked on, follow Resume in the Session protocol.
- No approval stop per issue: write the issue's plan and decisions into
  `HANDOFF.md` and keep going. Stop only for the user's "pause" or a usage warning,
  a file only the user may write, a decision the issue doesn't cover, or a check
  you can't fix.
- Read specific files and line ranges; never read `catalog/raw/`,
  `catalog/products.json` or `eval/results/` wholesale.
- Commit at every checkpoint (Session protocol). When every criterion is ticked and
  the check is green, push your `claude/*` branch, open the pull request with
  `gh pr create`, fill in the template from `HANDOFF.md`, and squash-merge it once
  CI is green. Then update the Project status block in `HANDOFF.md`. Ask before any
  push to `main`.
- You may run `make fetch-labels`. When you need `make run` or a `make eval*` or
  `make judge*` target, ask the user to run it and paste the output.
- Keeping the eval honest: never read `eval/cases/handwritten_questions.md` before
  issue 5 is merged, and never read `eval/cases/test.jsonl`. In issue 9 a fresh
  subagent drafts the cases; tell it not to open `catalog/aliases.yaml`,
  `assistant/retrieval/`, `assistant/prompts/` or `assistant/safety/`. Tune only
  from `eval/cases/dev.jsonl`.
