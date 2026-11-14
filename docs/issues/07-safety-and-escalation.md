Builder: Claude · Review: Codex, after the merge · Starts after: 2
Folders: `assistant/safety/` (`emergency.py`, `injection.py`, `reviewer.py`), `assistant/escalation.py`, the wiring in `assistant/pipeline.py`, the `/handoff` route in `assistant/app.py`, and their mirrored `tests/` folders.
Plan sections: Safety policy; Architecture (steps 1 and 6; When the model fails); Module map and rules.

Emergency rules, the replies for each risk label, the safety reviewer, and the pharmacist handoff. One pull request; the two parts below are its order of work. Emergency and injection patterns sit in one list at the top of their module. If issue 4 isn't merged yet, part (b)'s tests use an in-process fake of the ticket endpoints built from the contract's models.

Acceptance criteria, part (a)
- [ ] Emergency rules: a clear report of a current emergency involving the customer or anyone else (an overdose, trouble breathing, chest pain, unconsciousness, a seizure, throat swelling, self-harm) returns the fixed 911 reply before any model call, in any conversation state, including a message that also holds contact details. The pharmacist card is offered after the 911 text.
- [ ] A past event, a question about what a label warning means, and a figure of speech such as "I'm dying to try your new vitamins" don't fire the rules.
- [ ] A turn the router labels `emergency` gets the same 911 reply.
- [ ] Every other risk label gets the reply the policy table fixes. `medical_advice` shows the named product's warnings word for word when a product is named; `dosing_beyond_label` shows its directions word for word; `prescription` and `prompt_injection` show their refusals. All of them set `handoff_offered`.
- [ ] A few pattern rules back up the router's injection label. An injection attempt is logged and the conversation carries on.
- [ ] Safety reviewer: it rejects a plan with a record that wasn't retrieved, a section that doesn't exist, or a reply type the policy doesn't allow for the turn's risk label. A rejected plan becomes the fallback reply with `handoff_offered` set.
- [ ] Only code sets `handoff_offered`.

Acceptance criteria, part (b)
- [ ] `POST /handoff` creates exactly one ticket through the API for the session's current offer, with an idempotency key, and returns the ticket ID. Calling it again returns the same ticket.
- [ ] The header button works with no offer on screen: it creates a ticket marked as requested by the customer.
- [ ] The ticket summary is built by code: the risk label, an urgency, the customer's last messages after redaction, the products mentioned, what the assistant replied and why it offered the handoff.
- [ ] If ticket creation fails, the reply says so, and the retry reuses the same key.

Tests: one per emergency pattern, including one about a third party and one with an email in the message; the three things that must not fire; each risk label's reply; one test per reviewer rejection; an instruction planted in a policy-page fixture that changes nothing; handoff idempotency; a failed creation; the 911 text before the card; every summary field; no contact detail in a summary. Done when `make check` passes.
Follow the Session protocol in AGENTS.md.
