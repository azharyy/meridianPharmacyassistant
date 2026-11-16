# System verification, 2026-11-16

Code tested: `1c6e27b`, including the local E1-E5 fixes. All model responses were
scripted or supplied through a fake SDK HTTP transport. No external model call,
key file, held-out case inspection or saved evaluation update was used.

Evaluation policy update, 2026-11-16 ([issue 32](issues/32-opencode-evaluation.md)):
future live evaluations and calibration use OpenCode Go only. Runtime: GLM-5.3;
development comparison: GLM-5.3-Flash; judge: Kimi K3.1 Pro. The requested fresh
60-case baseline/improved pair is pending: `OPENCODE_API_KEY` is unavailable in
the agent's process, and no key file was read. The README provides isolated
user-run `--output-dir` commands. This does not turn the fake checks below into
live measurements; historical provider results remain archived under their actual
configuration. The cancelled alternate-provider rerun made no calls. After this
policy change, the full offline suite passes 1,461 tests; live-provider and isolated
output-directory regression tests are included. The original HTTP/browser status
below is unchanged.

## Results

| Check | Result | Evidence and scope |
| --- | --- | --- |
| Ruff lint and format | PASS | Repository check commands; 192 files checked for formatting. |
| Full offline suite | PASS | 1,456 tests, including contracts, architecture, catalog/data, API, assistant, SDK boundaries and evaluation harness. |
| Installed dependencies | PASS | `uv --cache-dir .uv-system-check pip check --python .venv/Scripts/python.exe`: 31 packages compatible. No install. |
| Catalog integration matrix | PASS | 302 in-process HTTP turns through real default retrieval/tool wiring and mock API, with scripted models. |
| Separate assistant/API over TCP | PASS | 12 flow groups against two ephemeral loopback uvicorn services; actual HTTP client between services. |
| Widget JavaScript syntax | PASS | `node --check widget/meridian-chat.js` and Node syntax checks for both inline HTML scripts; external script paths exist. |
| Browser interaction/rendering | BLOCKED | Browser host unavailable; native Chrome fallback stopped because Computer Use could not confidently determine the current URL. No bypass or alternative browser automation attempted. |
| Live model routing, accuracy and latency | NOT RUN | AGENTS.md reserves live run/eval/judge commands for the user. Offline results cannot establish these. |

## Catalog integration matrix

A read-only synthetic probe used the assistant's real default retriever, plan
validation, tool executor and renderer plus the actual mock API in process:

- 208 product replies: all 52 products, each of the four label sections. Both
  displayed text and cited source text matched the catalog verbatim.
- 52 availability replies: every SKU returned stock for both stores.
- 26 disjoint product comparisons: all four rows matched the selected records.
- 16 policy replies: every policy section retrieved by title and rendered verbatim.

The model outputs were scripted; this checks the cooperation of the components,
not whether a live model chooses the correct product or plan.

## Actual HTTP checks

A disposable Python probe bound two ephemeral loopback sockets and ran the real
assistant and mock API under uvicorn. The assistant used explicit fake settings,
scripted `FakeSender`, its real startup index and an actual HTTP API client.
Twelve assertion groups passed:

1. Both services started; demo, widget assets/fixtures, OpenAPI and API docs loaded.
2. Product directions followed retrieval and rendering into verbatim cited text.
3. A comparison returned four rows and eight cited product sections.
4. Availability reached the separate API service and returned both stores with
   a timestamped source.
5. Store information used the requested store ID and a timestamped API source.
6. Delivery policy text matched its retrieved source exactly.
7. Order form bypassed models; verified replies exposed only status, delivery
   estimate and item count. Session isolation, a newly typed order number,
   identical wrong-contact/unknown-order failures and five-attempt lockout worked.
8. Medical warnings were cited; international phone text stayed out of model
   requests and ticket summary. No ticket existed before confirmation; repeat
   confirmation returned one ticket. Reads without the staff header returned 401.
9. Prescription/injection refusals offered handoff. An ambiguous spray question
   omitted label text rather than selecting oral-tablet directions.
10. Recognized recurrence/throat emergencies made zero model calls. An exhausted
    fake model produced fixed fallback. Old offer confirmation returned 409 without
    a ticket; the current emergency ticket retained emergency urgency.
11. A real HTTP test timeout became a safe lookup failure with no factual sources.
12. Cross-origin preflight worked on chat, verification and handoff; malformed
    requests returned validation errors.

All disposable servers and sockets were stopped in cleanup. These were backend
requests, not browser actions; CORS response checks do not replace a real embedded
widget interaction test.

## Defect found and fixed

An SDK completion with `choices=[]` raised `IndexError` and caused `/chat` to
return 500 after one request. [Issue 31](issues/31-empty-completion-fallback.md)
adds a two-line guard using the existing `TransportError` retry/fallback path.
Both new tests failed before the guard and passed after it:

- `tests/assistant/test_llm.py::test_empty_choices_then_a_valid_completion_recovers`
- `tests/assistant/test_app.py::test_repeated_empty_sdk_choices_get_the_fixed_fallback_after_one_retry`

The latter checks one retry, HTTP 200, the fixed fallback, no product facts or
sources, and a valid pharmacist offer. No real provider was contacted.

## Reproduction and remaining acceptance

Run the standard checks (`make check`, or the three direct virtualenv commands
listed in Makefile). This Windows sandbox needs pytest's cache disabled and a
fresh workspace temporary directory, for example:

```powershell
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider --basetemp .pytest-verification --tb=short
node --check widget/meridian-chat.js
```

Remove only that session's temporary directory after the test run: fingerprint
tests deliberately write synthetic `.py` fixtures there, which a later repository
lint would otherwise scan. The global uv cache also needed a workspace override;
these were environment restrictions, not product failures.

Browser acceptance remains open:

- Serve the repository statically, then open `widget/preview.html`: expect 20/20
  examples. Open `widget/handoff-test.html`: expect PASS 8/8 for its deferred-fetch
  handoff/retry/concurrency scenarios. Neither fixture was executed in a browser
  during this verification.
- The user runs `make run` and follows the README demo: product/source chip,
  stock/store answers, private order form and wrong contact, safety refusal,
  confirmed pharmacist ticket, emergency banner, keyboard/Enter/Escape and focus.
- Check embedding from another origin in a browser. Real HTTP preflight checks
  passed, but browser rendering, focus, ARIA announcements and interaction still
  need observation.

The failed-handoff preview's missing retry callback is an existing disclosed
limitation, not evidence about the live retry flow. Saved evaluation reports,
cases, judge/calibration and protected configuration/contracts remained unchanged.
No claim of universal safety, live-model reliability or completed UI acceptance
follows from this report.
