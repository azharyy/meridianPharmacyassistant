# Find products when a drug or brand name has a typo

Requested by the user on 2026-11-16. The live chat answered "i want to ask about meridian
ibuprufen" with the not-found reply: search has no typo tolerance, so "ibuprufen" matched
nothing and only "ask" and "meridian" found records (three policy sections and two allergy
products). Spelled "ibuprofen", the same message finds the three ibuprofen products
first. The user chose this fix over a "Did you mean" reply, which would need a new reply
type in `contracts/`.
Branch: `typo-tolerance`. Commits and the pull request carry no attribution.

## Fix

In the exact stage of `SearchIndex.search` (on by default, `MERIDIAN_EXACT_MATCH=1`),
respell a query word that is one typo away from exactly one catalog ingredient or brand
word of six or more letters, or two typos away from one of nine or more letters, with
lengths within one letter. A typo is a letter inserted, deleted or replaced, or two
neighbors swapped. Correct words stay as typed, and so do words near two catalog words
and look-alike drugs outside the catalog, such as desloratadine or chlorpromazine.

Keyword search, the label-word aliases and the strict `named` lookup behind safety
replies keep the customer's words: a guessed name never chooses the label a safety reply
shows, and the keyword-only baseline is unchanged. The reply still names the real
product and quotes its label word for word.

Scope: `assistant/retrieval/exact.py`, `assistant/retrieval/index.py`, their mirrored
tests and `README.md`. Standard library only. No contracts, prompts, alias table,
policy text, dependencies, cases or saved results.

## Acceptance criteria

- [x] 1. A word one typo from one catalog ingredient or brand word is respelled; correct
  words, short words, words two typos from a shorter name, words near two catalog words
  and look-alike drugs outside the catalog stay as typed. Prove it in
  `tests/assistant/retrieval/test_exact.py`.
- [x] 2. With the real index, "i want to ask about meridian ibuprufen" returns the three
  ibuprofen products first; the keyword-only baseline and the strict `named` lookup do
  not respell. Prove it in `tests/assistant/retrieval/test_index.py`. The README
  describes the behavior and `make check` is green.
