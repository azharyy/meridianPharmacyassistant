# Widget preview inspection

Inspected by Codex on 2026-11-15 using installed Microsoft Edge headless against
`http://localhost:8000/widget/preview.html`, served from the repository root by
`.venv/Scripts/python.exe -m http.server 8000 --bind 127.0.0.1`. Re-rendered the
same way on 2026-11-16 (issue 34): seven group screenshots came out byte-identical,
and `08-handoff.png` was replaced because issue 15 removed the preview's retry button.

The full page reported **Drew 20 of 20 examples.** Eight grouped screenshots cover
all 18 chat replies and both handoff states; every group reported its expected
count with no failures. [render-results.json](render-results.json) records the URLs,
counts and viewport sizes; the PNGs preserve the rendered content. Use the
[preview page](../../widget/preview.html) to render the examples again.

Visual review found no clipping, overlapping controls or missing reply content at
the captured desktop widths. The comparison table, product list, stock and store
details, sources, order forms and generic failure text are visible. The emergency
banner appears before its pharmacist card. Risk/fallback cards and the handoff
success and failure states are visible; ordinary non-risk replies have no offer card.

- `01-label-and-products.png`: label sections and product list.
- `02-comparison.png`: both products and all four label sections.
- `03-stock-store-policy.png`: availability, store info and policy excerpt.
- `04-orders.png`: order status, order form and order-not-verified form.
- `05-emergency-and-risk.png`: emergency, medical advice and dosing beyond label.
- `06-refusals-and-fallback.png`: prescription, injection refusal and fallback.
- `07-other-replies.png`: off topic, not found and failed lookup.
- `08-handoff.png`: created ticket and failed creation. The preview passes no retry
  callback, so the failed state has no "Try again" button.

This is a static visual inspection, not a live assistant test. Keyboard navigation,
opening source chips, submitting forms, retries, and mobile layouts were not
interactively tested. The user's own widget acceptance remains pending.
