Planning only: write `docs/FIXES.md` with the smallest complete fixes for the reproduced handoff bug, incomplete submission documentation and evaluation limitations; link it from `docs/PLAN.md`, and record the documentation changes in the existing `HANDOFF.md` without taking over the unfinished eval session. Acceptance: concrete steps, future issue scopes, regression checks and one shared Codex/Claude continuation protocol; no fixed agent ownership, implementation, model calls or Git writes. Verify the links, scope and `git diff --check`; existing offline checks remain the baseline. The user explicitly requested the PLAN link on 2026-11-16.

User follow-up (2026-11-16): strengthen the limit instructions in those documents
and `docs/HANDOFF_TEMPLATE.md`. Both agents must monitor available usage/context
signals, reserve time for checks and a complete handoff, and stop before their
hard limit. Every change, result and unfinished step must be documented for the
next agent. Verify the wording and diff; no implementation or new tests required.
