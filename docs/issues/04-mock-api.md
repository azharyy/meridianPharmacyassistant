Builder: Claude · Review: Codex, after the merge · Starts after: 1 and 3
Folders: `api/`, `tests/api/`.
Plan sections: Mock Meridian API; Module map and rules.

The real endpoints behind the contract's stubs, one module per group of endpoints (orders, products, stores, tickets). The API, not the model, decides who may see an order. One pull request.

Acceptance criteria
- [ ] `POST /v1/orders/lookup` returns status, delivery estimate and item count only when the order number and the email or phone both match one order. Matching ignores case and surrounding spaces in an email and punctuation in a phone number.
- [ ] Every failure (an unknown order, a wrong contact, a contact from another customer) returns the same 404 status and body. No response ever holds an item name or an address.
- [ ] Lockout: after five failed lookups for one contact or one order number, every lookup for it, even a correct one, gets that same 404 for ten minutes. The clock is passed in, so a test can move time.
- [ ] `GET /v1/products/{sku}/availability` returns stock by store; an unknown SKU gets a 404 with the contract's error body.
- [ ] `GET /v1/stores` and `GET /v1/stores/{store_id}` return hours, address, phone and services from `data/stores.yaml`; an unknown store gets a 404.
- [ ] `POST /v1/tickets` requires an idempotency key and a summary that passes its schema. The same key returns the same ticket and never creates a second one.
- [ ] `GET /v1/tickets/{ticket_id}` requires the `X-Staff-Key` header to match `MERIDIAN_STAFF_KEY`; without it the answer is 401.
- [ ] The header `X-Meridian-Test: timeout` makes any endpoint time out.
- [ ] The contract snapshot test against `contracts/meridian-api.json` passes without changing the snapshot.

Tests, one per path: a verified lookup; a wrong contact; a partial contact; another customer's contact; look-alike order numbers; the two customers with the same name; a cancelled order; the lookup response checked for item names and addresses; identical status and body for an unknown order and a wrong contact; six wrong order numbers for one contact and then the right one, which is refused; the same lookup allowed again after ten minutes; unknown SKU; unknown store; a duplicate ticket key; a ticket read with and without the staff key; the timeout header. Done when `make check` passes.
Follow the Session protocol in AGENTS.md.
