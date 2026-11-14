# AGENTS.md: Meridian Pharmacy Assistant

## Project
Customer-support assistant for a fictional pharmacy storefront: an assistant
service, a mock Meridian API, SQLite catalog search and an embeddable chat widget.
Synthetic or public sample data only. The spec is `docs/PLAN.md`: read the
sections your issue names, not the whole file.

## Commands
- Setup: `uv sync --frozen`
- All checks: `make check` (lint, format check, offline tests). Needs no network.
- Fix formatting: `make fmt`
- Never run `make run` or any `make eval*` or `make judge*` target: they need a
  key. Ask the user to run them. `make fetch-labels` needs the network: Claude Code
  may run it, Codex asks the user to.
- Make recipes call Python only, with no shell syntax, so they run on Windows too.
  If `make` is missing in your shell, run the `check` target's three commands directly.

## Issue workflow
- Every change is one issue file in `docs/issues/`: what to build, acceptance
  criteria, tests and the folders it may touch. Read the whole issue before
  writing code.
- Implement only what the issue asks, and tick its criteria as you go, in
  `HANDOFF.md` (see Session protocol).
- A fix under ~50 lines that changes no specified behavior needs only a
  one-line issue.

## Session protocol
A session can be cut off at any moment (usage limit, context limit, crash), and the
other agent may be the one that continues. The working folder, git and `HANDOFF.md`
hold the state; the chat holds nothing that matters. Write `HANDOFF.md` for a reader
who has seen none of your chat. This applies whenever you build or fix an issue.
A review skips it.

Start
- Check the branch is this issue's (`git branch --show-current`).
- If `HANDOFF.md` is for this issue, follow Resume, whichever agent wrote it. Otherwise copy
  `docs/HANDOFF_TEMPLATE.md` to `HANDOFF.md`, replacing any older note, and paste
  the issue into it. Carry the older note's Project status block over and bring it
  up to date. `HANDOFF.md` is gitignored.

Checkpoint, after every acceptance criterion
- Run `make check`. In `HANDOFF.md`, tick the criterion, name the test that proves
  it, record the check result and rewrite "Next step" as one concrete action.
- Claude Code: then commit, `wip(<issue-slug>): <what now works>`.
- Codex: never stage or commit; `.git` is read-only in your sandbox, so the user commits.
- Never hold more than one criterion of unrecorded work.
- Never use `git stash`: stashes are shared across working folders.

Pause, when the user says "pause" or you see a usage or context warning
1. Start nothing new. Finish the edit in hand or revert it, whichever is smaller.
2. Run `make check`.
3. Complete every section of `HANDOFF.md`, with Status "paused".
4. Claude Code: commit, `wip(<issue-slug>): paused, green` or
   `wip(<issue-slug>): paused, RED: <what fails>`.
5. Reply with the branch, the check result, criteria done and left, the next step
   and any open questions. Then stop.

Resume, in a new chat in the same folder, by either agent
1. Read `HANDOFF.md`. Run `git status`, `git log --oneline origin/main..HEAD` and
   `make check`.
2. If the tree disagrees with the note (changes it doesn't mention, a different
   check result, another branch), stop and report. Never guess.
3. If the other agent wrote the note, add a line to its Log saying you took over.
   Claude Code: first commit any uncommitted work the note describes,
   `wip(<issue-slug>): taken over`.
4. Restate the next step in two lines, then continue from it.

## Ownership
- Change only in a pull request the user asked for by name: `contracts/`,
  `pyproject.toml`, `uv.lock`, `.github/`, `.claude/`, `docs/PLAN.md`, `CLAUDE.md`,
  `tests/test_architecture.py`, this file.
- Everything else: only the folders your issue names. Tests mirror the tree: an
  issue that owns `x/y/` also owns `tests/x/y/`. Add only the make targets your
  issue names.
- Need a dependency or a contract change? Stop and ask in the PR description.

## Code shape
Every module must be easy to find, to test and to change on its own. The module
map and its rules are in `docs/PLAN.md`; `tests/test_architecture.py` enforces them.
- One job per module, stated in the docstring on its first line.
- A step is a plain function: typed contract objects in, typed contract objects out.
- A step never imports another step. Only `pipeline.py` and `app.py` wire steps
  together; a step imports nothing from `assistant/` but the shared modules
  (`settings`, `llm`, `api_client`, `session`, `policy`, `templates`).
- Pass dependencies in as arguments (model client, API client, retriever), so a
  test swaps in a fake without patching.
- Read environment variables only in `assistant/settings.py`.
- Customer-facing sentences live only in `assistant/policy.py` and
  `assistant/templates.py`; prompts only in `assistant/prompts/`; emergency and
  injection patterns in one list at the top of their module.
- Every module gets a test file at the mirrored path. Functions stay under about
  40 lines; `make check` fails a function with complexity above 10.
- If the architecture test blocks you, stop and ask. Never edit it to pass.

## Rules
- Tests never call a real model: use the fake model client with scripted responses.
- Never open, print, copy or create a `.env` file, and never print an environment
  variable that holds a key. Only the user's own folder has a `.env`.
- Work only inside this folder, on your own branch.
- A model returns a structured plan, never reply text. Replies are built only from
  templates, catalog or policy text copied word for word, and API results.
- No model request carries `tools`: every call uses strict structured outputs, and
  a tool request is a plan field that code checks and runs.
- The model never sees order data, an order number or a customer's contact
  details. Contact details and order numbers typed into the chat are redacted
  before the model or the logs see them.
- The order lookup answers identically for an unknown order and a wrong contact,
  and returns status, delivery estimate and item count only.
- Every factual reply carries a sources list built in code.
- Only code sets `handoff_offered`. The emergency rules run before any model call.
- A ticket is created only when the customer confirms, with an idempotency key.
- Reading a ticket needs the staff key; the assistant never holds it.
- `eval/cases/test.jsonl` is for the eval issue only: never read it for other
  work, and never use its text in prompts, rules, templates or the alias table.
- Write the least code that meets the issue: does it need to exist, does the
  codebase, stdlib or an installed package already do it, can it be one line?
- Safety checks, validation, privacy guards and tests are never over-building.

## Pull requests
- One pull request per issue, on branch `claude/<issue-slug>` or `codex/<issue-slug>`.
  Aim for under ~600 changed lines of code (data files don't count); if an issue
  needs more, say so in `HANDOFF.md`. Run `make check` first.
- Description: the issue file, what changed, how to test, contracts touched (none).
- Codex never pushes: the user commits, pushes and merges its work. Claude pushes
  its own branch when every criterion is ticked, and merges the pull request once
  CI is green.

## Review guidelines
- P0: order data returned without the matching contact; an order reply with item
  names or an address; the model receiving order data or contact details; contact
  details in logs; label text not copied word for word from a catalog record; any
  model-written text shown to the customer; a factual reply without sources;
  `handoff_offered` set by a model; a ticket created without the customer's
  confirmation, or twice; a ticket readable without the staff key; product facts
  in a fallback reply; an order lookup that answers differently for an unknown
  order and a wrong contact, or that allows unlimited tries; anything that delays
  the 911 reply.
- P1: new behavior without tests; edits outside the issue's folders; behavior
  the issue didn't ask for; unticked criteria.
- Check every acceptance criterion in the issue against a test that proves it.
- A reviewer changes no files: it reports findings with file and line.
