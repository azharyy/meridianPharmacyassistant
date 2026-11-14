# HANDOFF: <issue-slug>

Issue: `docs/issues/<nn>-<issue-slug>.md` · Branch: <branch>
Started by: <Claude Code | Codex> · Now with: <Claude Code | Codex>
Status: in progress | paused | ready for review

Write this for the other agent: it may be the one that continues.

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
- Last commit: <hash and subject> (Codex: "none; the user commits")
- Unrecorded work: none | <files touched and what is half-done in each>

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
- <Claude Code>: criteria 1 to 3 done; paused at the usage limit (commit <hash>)

## For the user, while Codex is the builder
Codex can't commit, push or make a branch, so these are yours. Run them in this folder.
- Before Codex starts a new issue: `git switch main`, `git pull`, then `git switch -c codex/<issue-slug>`
- After each checkpoint Codex reports: `git add -A`, then `git commit -m "wip(<issue-slug>): <what now works>"`
- When every criterion is ticked and the check is green: `git push -u origin <branch>`, `gh pr create --fill`, `gh pr checks --watch`, then `gh pr merge --squash --delete-branch`
