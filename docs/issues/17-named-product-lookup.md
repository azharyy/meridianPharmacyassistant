# Show only the product the customer named

From `docs/FIXES.md` section D, after the diagnosis recorded in `HANDOFF.md`
(2026-11-16). The user approved this fix on 2026-11-16 and chose to re-measure the
development set afterwards before deciding on the default model; no model change here.
Branch: `named-product-lookup`. Commits and the pull request carry no attribution.

## Problem

A risk reply for medical advice or dosing beyond the label shows a label section of
"the product the customer named". `pipeline.named_product` finds that product with the
full retriever: the exact stage, then keyword search. A medicine outside the catalog can
then match another product's label text. In the saved GLM-5.3-Flash development run,
dev-009 named warfarin; keyword search matched MRD-PAN-002 (Acetaminophen 500 mg), whose
warnings mention warfarin, and the reply showed acetaminophen's directions.

## Fix

Look a named product up only through the exact stage: SKU, name, ingredient or brand
alias (`exact_products` in `assistant/retrieval/exact.py`). No match means no label
section: the reply is the policy table's text and the card. Catalog answers (step 4) keep
the full retriever unchanged. The strict lookup applies whatever `MERIDIAN_EXACT_MATCH`
says, because it is a safety guard, not the measured retrieval change.

Scope: `assistant/pipeline.py` (a `find_product` step and `named_product`),
`assistant/retrieval/index.py` (a strict `named` method), `assistant/app.py` (binding it),
`eval/runner.py` (its record-capture wrapper must also see the new step, so groundedness
keeps its evidence), and their mirrored tests. No contracts, prompts, policy text,
dependencies, cases, metrics or saved results.

## Acceptance criteria

- [ ] 1. A risk reply naming a medicine outside the catalog shows no label section, even
  when keyword search would return a product; a catalog product named by name, ingredient
  or brand alias still shows its section. Prove it in `tests/assistant/test_pipeline.py`
  (fake steps), `tests/assistant/retrieval/test_index.py` (the real index: "warfarin"
  names nothing although keyword search finds MRD-PAN-002) and `tests/assistant/test_app.py`
  (the default steps end to end).
- [ ] 2. The eval runner records the shown product's text and name through the new step
  as before, and catalog answers still use the full retriever. Prove it in
  `tests/eval/test_runner.py`; the full offline suite stays green.

After the merge the user runs `make eval-dev`, then `make eval-compare`, and pastes the
output; the default-model decision follows from that, outside this issue.
