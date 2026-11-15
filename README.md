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
| `MERIDIAN_RUNTIME_MODEL` | Optional | `glm-5.3-flash` (default) or `deepseek-v4.1-flash` |
| `MERIDIAN_RUNTIME_PROVIDER` | Optional | `opencode` (default) or `groq`, for `make run` only; the eval targets always use OpenCode Go |
| `GROQ_API_KEY` | Only with `MERIDIAN_RUNTIME_PROVIDER=groq` | A Groq API key, starting with `gsk_`. With `groq` the runtime is GPT-OSS 120B (or `openai/gpt-oss-20b`) |
| `MERIDIAN_STAFF_KEY` | Optional | The header value for reading a ticket back in the demo. Default: `dev-staff-key` |

Format: one `NAME=value` per line, with no quotes, no spaces around `=` and no `export`.

Every model call goes to OpenCode Go and uses only models included in the Go plan: the
assistant runs on GLM-5.3-Flash, the development comparison on DeepSeek V4.1 Flash, and
the eval judge is Kimi K3.1 Pro, from a different model family than both. They are the
Go models OpenCode lists with structured output on its chat-completions API; every call
uses strict structured outputs. OpenCode describes Go as built for coding agents and
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

## Where things live

## Guardrail design

## Evaluation

## AI usage

## Limitations and next steps
