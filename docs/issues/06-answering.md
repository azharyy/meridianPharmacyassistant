Builder: Claude · Review: Codex, after the merge · Starts after: 2, 4 and 5
Folders: `assistant/` (`router.py`, `catalog_agent.py`, `tools.py`, `orders.py`, `render.py`, `templates.py`, `prompts/`, and the wiring in `pipeline.py` and `app.py`) and `tests/assistant/`.
Plan sections: Architecture; Module map and rules; Mock Meridian API (How order privacy is enforced); Safety policy (the `none` rows).

The two model calls, the tool executor, the full renderer and the order flow, and the wiring of the real retriever, tools and orders into `pipeline.py`. One pull request; the two parts below are its order of work.

Acceptance criteria, part (a)
- [ ] Router: one structured-output call over the redacted conversation returns the router output. A circumstance stated in an earlier turn still counts.
- [ ] Catalog agent: given the question and the retrieved records, marked as data, it returns a plan and never text.
- [ ] The renderer covers every reply type: label sections word for word; a side-by-side comparison of two products (active ingredients, uses, warnings, directions); a product list showing each product's uses, in retrieval order and never ranked; a policy excerpt; not found; off-topic.
- [ ] The sources list is assembled in code from what the turn used.
- [ ] The two prompts live in `assistant/prompts/`. Neither holds text from `eval/cases/`.

Acceptance criteria, part (b)
- [ ] Tool executor: it checks the requested tool against an allowlist for the intent, and checks that the SKU or store exists, before calling the API. Reads get a timeout and one retry; a failed tool gives a fixed "couldn't check right now" reply.
- [ ] Availability and store replies are rendered from the API response, with an `api:` source and the time of the call.
- [ ] Order flow: `POST /orders/verify` passes the form's order number and contact to the API. On success the session holds the verified order and the reply is the order-status template: status, delivery estimate and item count. Any failure gives one generic message.
- [ ] An order question in the chat gets the order status if the session is verified, and the order-form block otherwise.
- [ ] No model request ever holds order data, an order number or a contact.

Tests, all on the fake model: context carried across turns; each reply type from its plan; a comparison built from both records; an allowlist rejection; an unknown SKU and an unknown store; a tool timeout; the order flow for a match, a wrong contact and someone else's order; the fake client's recorded requests checked for order data; one trace of the model requesting a tool and code running it. Done when `make check` passes.
Follow the Session protocol in AGENTS.md.
