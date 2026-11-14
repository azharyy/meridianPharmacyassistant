Builder: Claude · Review: CI and the user's read · Starts after: 1 and 3, and after the user has committed `eval/cases/handwritten_questions.md`
Folders: `assistant/retrieval/`, `catalog/aliases.yaml`, `tests/assistant/retrieval/`.
Plan sections: Architecture (step 4); Module map and rules; Data; Evaluation (The measured change; Rules).

The search index, and the exact-and-alias stage whose effect the evaluation measures. One pull request. Issue 6 wires the retriever into the pipeline; this issue doesn't touch `pipeline.py`.

Acceptance criteria
- [ ] An in-memory SQLite FTS5 index is built at startup over product sections and policy-page sections, ranked with BM25. A product hit returns the whole record.
- [ ] It implements the retrieval interface from `contracts/`.
- [ ] With `MERIDIAN_EXACT_MATCH=1`, the default, an exact stage runs first: SKU, product name, active ingredient and alias lookups, ignoring case and punctuation. With `0`, only keyword search runs.
- [ ] `catalog/aliases.yaml` maps national brand names to ingredients, from a brand list per catalog ingredient, and everyday words to label terms. It is written without reading anything under `eval/cases/`.
- [ ] A query that names two products returns both records.
- [ ] A query that matches nothing returns an empty list.

Tests: a lookup by SKU, by name, by ingredient and by alias; keyword search with the flag off; an alias query that fails with the flag off and passes with it on; two products in one query; no match; a policy question that returns the right page section. Done when `make check` passes.
Follow the Session protocol in AGENTS.md.
