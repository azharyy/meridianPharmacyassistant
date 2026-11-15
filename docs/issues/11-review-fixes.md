Builder: Codex · Review: tests and independent code review · Starts after: issues 1, 2, 3, 4, 7 and 8
Folders: `api/orders.py`, `assistant/safety/emergency.py`, `assistant/redaction.py`, `assistant/pipeline.py`, `assistant/session.py`, `assistant/escalation.py`, `assistant/app.py`, `scripts/label_text.py`, `catalog/products.json`, and their mirrored tests. No new dependencies, contracts or make targets.
Plan sections: Architecture (steps 1 and 2); Mock Meridian API (order privacy); Safety policy (emergencies and escalation); Data (complete warnings); Chat widget (embedding).

Fix the seven findings reproduced in Codex's after-merge review. The user authorized these fixes and explicitly authorized preparing uncommitted changes on `main` because Codex cannot mutate Git.

Acceptance criteria
- [ ] 1. Order matching strips punctuation and an optional US country prefix only; arbitrary prefixes and other country codes get the same generic failure as a wrong contact. Existing lockouts still work.
- [ ] 2. Historical or label clauses cannot silence a separate current emergency report; curly apostrophes work. Pure past events, label questions and figures of speech retain their behavior. Current emergencies make zero model calls.
- [ ] 3. Phone numbers with slashes, repeated whitespace and spaced punctuation are redacted before model requests, session history and ticket summaries; ages, doses and medicine names stay intact.
- [ ] 4. All pipeline log paths use a deterministic opaque session reference, so phone/order identifiers chosen as session IDs never appear raw in logs. Internal session and ticket keys remain stable.
- [ ] 5. Concurrent confirmations for the same current offer, including the header button with no offer, create one ticket; retries retain the key and failures are recoverable. Emergency replies never wait for ticket creation.
- [ ] 6. Catalog warnings include the source label's overdose subsection and all other warning subsections. Independently tested warning completeness covers all 52 products; labels with forbidden content are replaced from saved raw labels without deleting warning text or inventing medical text.
- [ ] 7. The public, cookie-free assistant API accepts widget JSON preflights and POST responses from another origin, including validation errors and handoff. CORS does not grant browser credentials.

Tests: regressions for each reported failure, including API responses, fake model requests, captured logs, concurrent handoffs and independent catalog provenance. Full offline lint, format check and pytest after each criterion; use an isolated pytest temporary directory because this sandbox cannot write the shared pytest temp/cache directories.
