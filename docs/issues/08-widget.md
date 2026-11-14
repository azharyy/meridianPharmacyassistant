Builder: Claude · Review: CI and the user's read · Starts after: 1
Folders: `widget/` only. Issue 2 already serves this folder at `/widget` and its demo page at `/demo`.
Plan sections: Chat widget.

The embeddable chat widget, a demo storefront page and a preview page. One pull request. It is built against the example replies in `contracts/examples/`, so it needs no running model. Keep one small function per block type, so a new block is one new function.

Acceptance criteria
- [ ] `widget/meridian-chat.js` is a plain JavaScript web component with no build step, inside Shadow DOM. One script tag with `data-api` and `data-store` adds a launcher; colors come from CSS custom properties.
- [ ] It draws every block type in the reply schema as given and adds no text of its own. Replies arrive complete, with a "checking the label…" indicator meanwhile.
- [ ] A source chip sits under every answer: a label section that opens the exact text, a policy page, or a live lookup with its time.
- [ ] The order form collects the order number and an email or phone, posts them to `/orders/verify`, never into the chat, and shows the same message for any failure.
- [ ] "Talk to a pharmacist" is always in the header. The offer card appears only on replies that set `handoff_offered`. Confirming calls `/handoff` and shows the ticket ID, or says the request didn't go through and offers a retry.
- [ ] An emergency reply is a red banner with the 911 text first, then the card.
- [ ] Keyboard use works throughout, new messages are announced through an ARIA live region, focus is visible, and the footer reads "Not medical advice. In an emergency, call 911."
- [ ] `widget/demo.html` is a fake Meridian product page with the widget on it.
- [ ] `widget/preview.html` draws every example reply from `contracts/examples/` with no assistant running, from a plain static server started in the repo root.

Tests: none automated; every reply type is checked by eye on the preview page. Done when `make check` still passes and the user has looked at every reply type in the preview.
Follow the Session protocol in AGENTS.md.
