# Widget preview inspection

Inspected by Codex on 2026-11-15 using installed Microsoft Edge headless against
`http://localhost:8000/widget/preview.html`, served from the repository root by
`.venv/Scripts/python.exe -m http.server 8000 --bind 127.0.0.1`.

The full page reported **Drew 20 of 20 examples.** Eight grouped screenshots cover
all 18 chat replies and both handoff states; every group reported its expected
count with no failures. [render-results.json](render-results.json) records the URLs,
counts and viewport sizes; the PNGs preserve the rendered content. Use the
[preview page](../../widget/preview.html) to render the examples again.

Visual review found no clipping, overlapping controls or missing reply content at
the captured desktop widths. The comparison table, product list, stock and store
details, sources, order forms and generic failure text are visible. The emergency
banner appears before its pharmacist card. Risk/fallback cards and the handoff
success and retry states are visible; ordinary non-risk replies have no offer card.

- `01-label-and-products.png`: label sections and product list.
- `02-comparison.png`: both products and all four label sections.
- `03-stock-store-policy.png`: availability, store info and policy excerpt.
- `04-orders.png`: order status, order form and order-not-verified form.
- `05-emergency-and-risk.png`: emergency, medical advice and dosing beyond label.
- `06-refusals-and-fallback.png`: prescription, injection refusal and fallback.
- `07-other-replies.png`: off topic, not found and failed lookup.
- `08-handoff.png`: created ticket and failed creation with retry.

The interactive browser-control tools failed initialization with a missing kernel
assets path. The first sandboxed Edge attempt also failed because its GPU process
could not initialize; the installed renderer succeeded outside that process
sandbox. Browser security settings were not changed. A normal Edge launch was
also requested at the user's URL, but its visible window could not be verified
through the unavailable UI tools.

This is a static visual inspection, not a live assistant test. Keyboard navigation,
opening source chips, submitting forms, retries, and mobile layouts were not
interactively tested. The user's own widget acceptance remains pending.
