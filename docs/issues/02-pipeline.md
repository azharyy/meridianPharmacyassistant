Builder: Claude · Review: CI and the user's read · Starts after: 1
Folders: `assistant/` (`settings.py`, `llm.py`, `api_client.py`, `session.py`, `templates.py`, `redaction.py`, `render.py`, `pipeline.py`, `app.py`, thin first versions of `router.py` and `catalog_agent.py`, `prompts/`) and `tests/assistant/`. Adds the make target `run`.
Plan sections: Architecture, including Model calls and When the model fails; Module map and rules.

The shared modules and the turn pipeline end to end, with one cited answer through the chat endpoint on the fake model. One pull request.

Acceptance criteria
- [ ] Model client: one small class over the OpenAI SDK, with strict structured outputs, no `tools`, a timeout and one retry. Settings are held per role (provider, base URL, model, reasoning effort, timeout): the runtime role defaults to gpt-oss-120b on Groq, the eval's judge role will use GPT-6 Luna on OpenAI, and pointing the runtime at OpenAI is a config change.
- [ ] A fake client with scripted responses is the default. The real client is used only when `MERIDIAN_LLM=live`, and starting live without the key that role needs (`GROQ_API_KEY` or `OPENAI_API_KEY`) stops with a clear message that names the missing variable and the `.env` file.
- [ ] `settings.py` is the only place that reads environment variables. `api_client.py` is the only code that calls the mock API: one small typed function per endpoint in the contract.
- [ ] An in-memory session store keeps the turns, the verified order and the last handoff offer.
- [ ] Redaction replaces emails, phone numbers and order numbers in the `MRD-ORD-` format with placeholders before the model or the logs see them. Ages, doses and medicine names stay intact.
- [ ] The pipeline is the plan's eight steps as plain functions called top to bottom. Each step is passed in as a callable, with what it depends on as arguments. Steps that later issues own (emergency rules, retrieval, safety reviewer, tool executor) have a do-nothing default defined in `pipeline.py`, behind fixed signatures.
- [ ] `router.py` and `catalog_agent.py` exist as thin first versions: one structured call each, with a placeholder prompt in `prompts/`. Issue 6 finishes them.
- [ ] `POST /chat` returns one cited answer on the fake model: a directions question against a two-product fixture returns that label section word for word, with the source `SKU#directions`.
- [ ] The renderer builds that reply and the fallback reply from templates and record text only.
- [ ] A model timeout, a rate-limit error, or an output still invalid after one retry gives the fixed fallback with `handoff_offered` set.
- [ ] Logs carry the session ID and a timing per stage, never raw message text or contact details.
- [ ] `app.py` holds routes only, and serves the `widget/` folder at `/widget` and its demo page at `/demo` when that folder exists.
- [ ] `make run` sets `MERIDIAN_LLM=live` itself, as a make variable and not with shell syntax, and starts the API on port 8001 and the assistant on port 8000 from one small Python launcher, with no shell job control, so it works from Git Bash on Windows as well as macOS and Linux.

Tests: redaction (an email, a phone number, an order number; an age and a dose left intact); the cited answer end to end; the reply holds only template and fixture text; the three failure cases; log contents; live mode without a key; the runtime role switched to the other provider by settings alone. Done when `make check` passes.
Follow the Session protocol in AGENTS.md.
