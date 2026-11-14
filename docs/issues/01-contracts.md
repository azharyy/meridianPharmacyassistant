Builder: Claude · Review: CI and the user's read · Starts after: the bootstrap commit
Folders: `contracts/`, `api/app.py`, `assistant/policy.py` and their mirrored `tests/` folders. Adds the make target `contracts`.
Plan sections: Architecture; Module map and rules; Data; Mock Meridian API; Safety policy; Chat widget.

The frozen interfaces every other issue builds against, plus the policy table. No behavior yet: schemas, stubs, examples and the tests that guard them. One pull request.

Acceptance criteria
- [ ] `contracts/` holds the taxonomy as enums: intents (`product_info`, `compare`, `availability`, `store_info`, `policy`, `order_status`, `off_topic`), risk labels (`none`, `emergency`, `medical_advice`, `dosing_beyond_label`, `prescription`, `prompt_injection`), reply types, label sections (`active_ingredients`, `uses`, `warnings`, `directions`) and tool names.
- [ ] Router output model: the intent, the risk label, product mentions, label sections and a store topic.
- [ ] Plan model: the records and sections that answer the question, and at most one tool request (`check_availability(sku)` or `get_store_info(store_id)`). No field holds text meant for the customer.
- [ ] Both model-facing schemas pass a strict-mode check: every field required, `additionalProperties: false` on every object, optional values written as nullable.
- [ ] Chat shapes: the chat request (session ID, message); the reply (reply type, blocks, sources, `handoff_offered`, an emergency flag); the order-form request (session ID, order number, contact); the handoff request and its reply (ticket ID). Block types: text, label section, comparison, product list, availability, store info, policy excerpt, order status, order form.
- [ ] The product record model, with exactly the field names in the plan's Data section, and the retrieval interface (`search(query, k)` returning whole records) live in `contracts/`, so issues 3, 5 and 6 agree on them.
- [ ] Every endpoint in the plan's API table is declared in `api/app.py` with typed request, response and error models, each a stub that returns 501. The OpenAPI spec is committed as `contracts/meridian-api.json`.
- [ ] `contracts/examples/` holds one example reply per reply type as JSON, and a test validates each against the reply model.
- [ ] Snapshot tests fail when a schema or the API's OpenAPI drifts from the committed files. `make contracts` regenerates them.
- [ ] `assistant/policy.py` holds the plan's policy table: for each risk label, the reply type, the label sections it may show, the fixed text and whether `handoff_offered` is set. It also holds the fixed replies: emergency, fallback, off-topic, not found, and one refusal per label.

Tests: strict-mode validity of both schemas; every example payload; both snapshots; every risk label has a policy row; the emergency text contains 911, 1-800-222-1222 and 988; the fallback text contains "call 911". Done when `make check` passes.
Follow the Session protocol in AGENTS.md.
