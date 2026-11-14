---
name: Change
about: One change, one builder, one prompt
title: "<issue-slug>"
---
Builder: <Claude | Codex> · Review: <CI and the user's read | the other agent> · Starts after: <issue numbers>
Folders: <the folders this issue may touch; tests go in the mirrored `tests/` folders>
Plan sections: <the headings in docs/PLAN.md to read>

<One or two sentences: what to build.>

Acceptance criteria
- [ ] <observable behavior, one per line>

Tests: <the tests that prove the criteria>. Done when `make check` passes.
Follow the Session protocol in AGENTS.md.
