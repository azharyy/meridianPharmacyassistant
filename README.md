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
GROQ_API_KEY=gsk_your_key_here
```

| Variable | Needed for | What it is |
| --- | --- | --- |
| `GROQ_API_KEY` | `make run` and all eval targets | One Groq API key, starting with `gsk_`, serves the assistant and judge. Groq's free plan is enough to try the demo |
| `MERIDIAN_STAFF_KEY` | Optional | The header value for reading a ticket back in the demo. Default: `dev-staff-key` |

Format: one `NAME=value` per line, with no quotes, no spaces around `=` and no `export`.

The assistant uses Groq-hosted GPT-OSS 120B; the eval judge uses Qwen 3.8 27B.
The development comparison uses GPT-OSS 20B with the same Qwen judge. All calls
use the Groq API and strict structured outputs. An OpenAI API key is unused.

```bash
make run          # then open http://localhost:8000/demo
```

If a key is missing, `make run` stops and names the variable it needs.

<!-- The sections below are written at the end of the build. -->

## Architecture

## Where things live

## Guardrail design

## Evaluation

## AI usage

## Limitations and next steps
