# HANDOFF: <issue-slug>

Issue: `docs/issues/<nn>-<issue-slug>.md` · Branch: <branch>
Started by: <Claude Code | Codex> · Now with: <Claude Code | Codex>
Status: in progress | paused | ready for review

Write this for the other agent: it may be the one that continues.

Monitor available usage/context/time-limit signals throughout the session.
Before starting another step, reserve enough capacity to run checks and complete
this note. Stop implementation before that reserve is consumed; do not wait for
99% usage or the hard limit. If exact quota information is unavailable, do not
invent it: use small checkpoints and stop at the first warning. Update this note
as work happens, not only at the end. Before stopping, reconcile every changed or
untracked file with the note, complete every section, set Status `paused`, report
the state to the user and stop. Nothing done or unfinished may exist only in chat.

## Project status
<Carry this block from note to note and keep it current. Build order: 1, 2, 3, 4, 7, 5, 6, 8, 9, 10.>
- Merged: <issue numbers, each with its pull request>
- In progress: <this issue>
- Not started: <issue numbers, in build order>
- Waiting on the user: <what only the user can do, and the issue it blocks>

## Issue
<Paste the issue body here at the start, so a new chat needs nothing else.>

## Criteria
<One line per acceptance criterion, in the issue's order.>
- [ ] 1. <criterion> (proven by: <test file::test name>)

## State of the tree
- Last `make check`: green | RED: <what fails>
- Last commit: <hash and subject, or none if this session made no commit>
- Checkout HEAD: <actual `git rev-parse HEAD` hash, even when this agent made no commit>
- Unrecorded work: none | <files touched and what is half-done in each>
- Changed/untracked files: <each path, what changed, why, complete or partial, and pre-existing user work versus this session's edits>
- Checks this session: <exact commands, results, failures, and anything not run or interrupted; never label an incomplete check green>
- Processes/artifacts: <running commands/servers and temporary outputs, with safe cleanup or continuation instructions; stop session-owned background writers before handover, preserve unrelated user processes>
- Stop reason and limit signal: <observed warning/remaining budget if available, or unavailable; confirm the handoff was completed before exhaustion>

## Next step
<One concrete action, small enough to start cold. Example: "Write
tests/api/test_orders.py::test_wrong_contact for criterion 2, then make it pass.">

## Decisions made, and why
<Choices a new chat would otherwise have to rediscover or might undo.>

## Tried and rejected
<Approaches that failed, so they aren't repeated.>

## Open questions for the user
<Anything that needs a decision before the work can finish.>

## Log
<One line per session, newest last: who worked, which criteria, how it ended.>
- <Claude Code or Codex>: criteria 1 to 3 done; paused before the usage limit, all changes documented (commit <hash> or uncommitted)

## Git actions for either agent
Codex and Claude may create issue branches, stage scoped files, commit and push.
Use `codex/<issue-slug>` or `claude/<issue-slug>` and preserve unrelated work.
- After a green checkpoint: stage the issue's explicit paths and commit `wip(<issue-slug>): <what now works>`.
- When ready: push the issue branch, prepare the PR and check CI before merging.
- Direct pushes to `main` and remote-history rewrites require an explicit user instruction. For an authorized rewrite, use a lease pinned to the inspected remote tip and record the old tip for recovery.
