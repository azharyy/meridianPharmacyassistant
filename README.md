# Meridian Pharmacy Assistant

A guard-railed customer-support assistant for a fictional pharmacy storefront. It
answers product, stock, store and order questions from real data, shows the
source behind every answer, and hands anything medical to a pharmacist.

**Status:** in progress. The build plan is in [docs/PLAN.md](docs/PLAN.md).

All data is synthetic or public sample data. Not medical advice.

## Setup

You need Python 3.11, [uv](https://docs.astral.sh/uv/) and GNU `make`. On Windows,
run the commands in Git Bash and install make with `winget install -e --id ezwinports.make`.

```bash
git clone <this-repo-url>
cd <the-folder-it-created>
uv sync --frozen
make check        # lint and offline tests; needs no key and no network
```

### The `.env` file

Running the assistant needs an API key, which goes in a file named `.env` in the
repo root. The file is gitignored and must never be committed. Create it by
copying `.env.example`:

```bash
cp .env.example .env
```

Then fill it in:

```
OPENCODE_API_KEY=your_opencode_key_here
```

| Variable | Needed for | What it is |
| --- | --- | --- |
| `OPENCODE_API_KEY` | `make run` and all eval targets | An API key from [opencode.ai/auth](https://opencode.ai/auth), used with an OpenCode Go subscription. It serves the assistant and the judge |
| `MERIDIAN_RUNTIME_MODEL` | Optional | `glm-5.3-flash` (default) or `glm-5.3` |
| `MERIDIAN_RUNTIME_PROVIDER` | Optional | `opencode` (default) or `groq`, for `make run` only; the eval targets always use OpenCode Go |
| `GROQ_API_KEY` | Only with `MERIDIAN_RUNTIME_PROVIDER=groq` | A Groq API key, starting with `gsk_`. With `groq` the runtime is GPT-OSS 120B (or `openai/gpt-oss-20b`) |
| `MERIDIAN_STAFF_KEY` | Optional | The header value for reading a ticket back in the demo. Default: `dev-staff-key` |

Format: one `NAME=value` per line, with no quotes, no spaces around `=` and no `export`.

Every model call goes to OpenCode Go and uses only models included in the Go plan: the
assistant runs on GLM-5.3-Flash, the development comparison on its larger sibling GLM-5.3,
and the eval judge is Kimi K3.1 Pro, from a different model family than both. They are Go
models OpenCode lists with structured output on its chat-completions API; every call uses
strict structured outputs. DeepSeek V4.1 Flash is listed the same way but rejected every
such request with HTTP 400, so it is not offered. OpenCode describes Go as built for coding agents and
monitors its traffic. An OpenAI API key is unused.

The held-out results in [`eval/REPORT.md`](eval/REPORT.md) were measured before this
change, on Groq-hosted GPT-OSS 120B with a Groq Qwen 3.8 27B judge (its calibration is
kept in `eval/results/calibration-groq-qwen.md`). The test set was not run again on the
new default, so those numbers describe the Groq configuration.

```bash
make run          # then open http://localhost:8000/demo
```

If a key is missing, `make run` stops and names the variable it needs.

<!-- The sections below are written at the end of the build. -->

## Architecture

Two small FastAPI services and a widget. The **assistant** (`assistant/`, port 8000)
serves the widget and answers it. The **mock Meridian API** (`api/`, port 8001) owns
orders, stock, stores and tickets; the assistant reaches it only over HTTP, through
`assistant/api_client.py`. `make run` starts both (`assistant/launcher.py`).

### One turn, eight steps

Every chat message runs the same pipeline of plain functions, called top to bottom in
`assistant/pipeline.py`. Only the router and the catalog agent call a model; every other
step is plain code.

```mermaid
flowchart TD
    message([Customer message]) --> emergency{"1 Emergency rules (code)"}
    emergency -- current emergency --> e911["Fixed 911 reply, then the pharmacist card"]
    emergency -- no --> redact["2 Redaction (code)"]
    redact --> router["3 Router (model)"]
    router -- risk label other than none --> risk["The policy table's fixed reply and the card"]
    router -- order question --> order["The order form, or the status verified earlier"]
    router -- store question --> review
    router -- product or policy question --> retrieve["4 Retrieval (code)"]
    retrieve --> agent["5 Catalog agent (model)"]
    agent --> review{"6 Safety reviewer (code)"}
    review -- rejected --> fallback["The fallback reply and the card"]
    review -- accepted --> tools["7 Tool executor (code)"]
    tools --> render["8 Renderer (code)"]
```

| Step | Module | Model | What it does |
| --- | --- | --- | --- |
| 1. Emergency rules | `assistant/safety/emergency.py` | No | Patterns for a current emergency, the customer's or someone else's: an overdose, trouble breathing, chest pain, unconsciousness, a seizure, throat swelling, self-harm. Guards let a past event or a question about a label warning through. A match returns the fixed 911 reply at once, with the pharmacist card |
| 2. Redaction | `assistant/redaction.py` | No | Emails, phone numbers and order numbers typed into the chat become `[email]`, `[phone]` and `[order number]` before the model, the session or the logs see them |
| 3. Router | `assistant/router.py` | Yes | One structured-output call over the redacted conversation: intent, risk label, products mentioned, label sections asked about, store topic. It never sees retrieved text. Pattern rules in `assistant/safety/injection.py` back up its prompt-injection label, and the more restrictive label wins |
| 4. Retrieval | `assistant/retrieval/` | No | Exact SKU, name, ingredient and alias matching first (`catalog/aliases.yaml`), then keyword search over an in-memory SQLite FTS5 index of label sections and policy pages. Returns up to five whole records |
| 5. Catalog agent | `assistant/catalog_agent.py` | Yes | Reads the question and the retrieved records, marked as data, and returns a plan: which records and sections answer it, and at most one tool request. Never text |
| 6. Safety reviewer | `assistant/safety/reviewer.py` | No | Rejects a plan that names a record that wasn't retrieved, a section the record doesn't have, or a reply type or section the risk label doesn't allow. A rejected plan becomes the fallback reply |
| 7. Tool executor | `assistant/tools.py` | No | Runs the requested lookup only when the turn's intent allows that tool (stock for an availability question, store details for a store question) and the SKU or store exists. Reads time out after 3 s and are retried once |
| 8. Renderer | `assistant/render.py` | No | Builds the reply from templates, record text copied word for word and API results, attaches the sources, and sets `handoff_offered` from the policy table |

Shorter paths, all in `assistant/pipeline.py`:

- A risk label other than `none` gets the policy table's fixed reply. For medical advice
  or dosing beyond the label it adds the named product's warnings or directions, word for
  word. The catalog agent doesn't run.
- An order question gets the order form, or the status already verified in this session.
  No model sees order data.
- A store question skips retrieval and the catalog agent: its plan goes to the reviewer
  and then to the store lookup.

When a reply shows a pharmacist card, code records that card as the session's current
offer and stamps the offer's ID on the reply.

### Routes

| Service | Route | What it does |
| --- | --- | --- |
| Assistant | `POST /chat` | One customer message; returns the reply's blocks, its sources, `handoff_offered`, `emergency` and `offer_id` |
| Assistant | `POST /orders/verify` | The order form: an order number and an email or phone. Plain code, no model |
| Assistant | `POST /handoff` | Confirms a pharmacist card by its `offer_id`, or the header button with `null`. HTTP 409 for an out-of-date card |
| Assistant | `GET /widget/...`, `GET /demo` | The widget's files and the demo storefront |
| Mock API | `POST /v1/orders/lookup` | Status, delivery estimate and item count, only when the number and the contact match |
| Mock API | `GET /v1/products/{sku}/availability`, `GET /v1/stores`, `GET /v1/stores/{store_id}` | Stock and store details |
| Mock API | `POST /v1/tickets`, `GET /v1/tickets/{ticket_id}` | Creates a ticket, one per idempotency key; reads it back only with the `X-Staff-Key` header |

The shapes are frozen in `contracts/` (`contracts/chat.py`, `contracts/api.py`), with
example payloads in `contracts/examples/` and snapshots in `contracts/schemas.json` and
`contracts/meridian-api.json`.

### Why the parts are separate

| Component | Uses a model | Can reach | Why it is separate |
| --- | --- | --- | --- |
| Emergency rules | No | The raw message | Instant, and it still works when the model is down |
| Router | Yes | The redacted conversation | It decides intent and risk without reading retrieved text, so an instruction planted in a document can't change a safety decision |
| Catalog agent | Yes | Retrieved records; may request the stock or store lookup | It reads untrusted text but has no path to orders |
| Order agent (`assistant/orders.py`) | No | The order API, with the form's details | The model never sees order data and can't choose an order |
| Safety reviewer | No | The plan | A check the model can't argue with |
| Tool executor | No | The public lookups | Only the tool the turn's intent allows runs, and only for a real SKU or store |
| Renderer | No | Templates, records, API results | The only component that produces what the customer reads |
| Escalation (`assistant/escalation.py`) | No | The ticket API | Code decides when the card appears; a ticket exists only once the customer confirms |

## Where things live

## Guardrail design

## Evaluation

## AI usage

## Limitations and next steps
