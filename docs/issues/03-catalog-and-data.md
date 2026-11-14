Builder: Claude · Review: CI and the user's read · Starts after: the bootstrap commit
Folders: `catalog/`, `data/`, `scripts/` and their mirrored `tests/` folders. Adds the make targets `fetch-labels` and `seed-data`.
Plan sections: Data.

The fictional inventory built from public label samples, and the store, policy, order and stock data. One pull request. It runs alongside issue 1, so use the field names in the plan's Data section; the test against the product record model in `contracts/` is the last criterion, and needs `main` brought in once issue 1 has merged. Claude Code runs `make fetch-labels` itself. Codex's sandbox has no network: if Codex is the builder, it writes the script, then stops and asks the user to run it, and builds part (b) while it waits.

Acceptance criteria, part (a)
- [ ] `scripts/fetch_labels.py` queries the openFDA drug label API for OTC labels of about 30 common ingredients across allergy, pain and fever, cough and cold, digestive, skin, sleep and eye care. It keeps only labels that have all four sections, pauses briefly between requests, and saves each raw label under `catalog/raw/` with its set ID and date.
- [ ] `catalog/products.json` holds 52 products with the plan's field names: a fictional name, a SKU like `MRD-ALG-012`, category, form, strength, price, the four sections copied word for word, and the source set ID and date.
- [ ] The `warnings` section holds the label's complete warnings: the main warnings text plus any warning subsections the API returns as separate fields, in label order, with nothing dropped.
- [ ] No real brand, manufacturer or distributor name and no phone number appears in any record.
- [ ] Every category has at least two products, and at least four pairs of products share a use, so comparisons have something to compare.

Acceptance criteria, part (b)
- [ ] `data/stores.yaml` holds two stores, each with address, phone, hours by weekday and services.
- [ ] `data/policies/` holds `returns.md`, `delivery.md` (area, fees, times), `privacy.md` and `pharmacist-services.md`, each with a heading per topic.
- [ ] `scripts/seed_data.py` (`make seed-data`) writes about 20 orders for about 12 customers to `data/orders.json` from a fixed seed, with order numbers like `MRD-ORD-48213` and the traps: two customers with the same name, a cancelled order and look-alike order numbers. Running it twice gives identical files.
- [ ] `data/stock.json` holds stock for every SKU at both stores, with some products out of stock.

Tests: every product against the product record model in `contracts/` (last, after issue 1 merges); each section found word for word in its raw label after whitespace is normalized; no name from the raw labels' brand and manufacturer fields in any record; seed determinism; the three order traps; a stock row for every SKU. Done when `make check` passes.
Follow the Session protocol in AGENTS.md.
