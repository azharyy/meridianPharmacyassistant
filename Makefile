# Meridian Pharmacy Assistant: one entry point for every routine task.
# Recipes call the virtualenv directly, so `make check` needs no network.

# The path is absolute and quoted so the same recipes run from Git Bash, PowerShell
# and cmd on Windows, and from a folder with spaces in its name.
ifeq ($(OS),Windows_NT)
PY := "$(CURDIR)/.venv/Scripts/python.exe"
else
PY := "$(CURDIR)/.venv/bin/python"
endif

# Load .env if there is one. Keys go there as NAME=value, without quotes.
ifneq (,$(wildcard .env))
include .env
export
endif

.PHONY: check fmt contracts run fetch-labels seed-data

.venv:
	uv sync --frozen

check: | .venv  ## Lint, format check and offline tests. No key, no network.
	$(PY) -m ruff check .
	$(PY) -m ruff format --check .
	$(PY) -m pytest -q

fmt: | .venv  ## Format the code and apply safe lint fixes.
	$(PY) -m ruff format .
	$(PY) -m ruff check --fix .

contracts: | .venv  ## Regenerate the contract snapshots. Commit them in a PR of their own.
	$(PY) -m tests.contracts.snapshots

fetch-labels: | .venv  ## Fetch OTC label samples from openFDA into catalog/raw/. Needs the network.
	$(PY) -m scripts.fetch_labels

seed-data: | .venv  ## Regenerate data/orders.json and data/stock.json from the fixed seed.
	$(PY) -m scripts.seed_data

# A target-specific variable, so `make run` uses the live model with no shell syntax.
run: export MERIDIAN_LLM := live
run: | .venv  ## Start the API on port 8001 and the assistant on port 8000. Needs the runtime's key.
	$(PY) -m assistant.launcher

.PHONY: eval-dev eval-baseline eval

eval-dev eval-baseline eval: export MERIDIAN_LLM := live
eval-dev eval-baseline eval: export MERIDIAN_RUNTIME_PROVIDER := groq
eval-dev eval-baseline eval: export MERIDIAN_RUNTIME_MODEL := openai/gpt-oss-120b
eval-dev eval: export MERIDIAN_EXACT_MATCH := 1
eval-baseline: export MERIDIAN_EXACT_MATCH := 0

eval-dev: | .venv  ## Run labeled development cases with live runtime and judge models.
	$(PY) -m eval.cli dev

eval-baseline: | .venv  ## Run the labeled test set with keyword retrieval alone.
	$(PY) -m eval.cli baseline

eval: | .venv  ## Run the same labeled test set with exact matching enabled.
	$(PY) -m eval.cli improved

.PHONY: judge-calibrate

judge-calibrate: export MERIDIAN_LLM := live
judge-calibrate: export MERIDIAN_RUNTIME_PROVIDER := groq
judge-calibrate: export MERIDIAN_RUNTIME_MODEL := openai/gpt-oss-120b
judge-calibrate: | .venv  ## Check the Groq Qwen judge against the 20 labeled pairs.
	$(PY) -m eval.cli calibrate

.PHONY: eval-compare

eval-compare: export MERIDIAN_LLM := live
eval-compare: export MERIDIAN_RUNTIME_PROVIDER := groq
eval-compare: export MERIDIAN_RUNTIME_MODEL := openai/gpt-oss-20b
eval-compare: export MERIDIAN_EXACT_MATCH := 1
eval-compare: | .venv  ## Compare Groq 20B with the saved matching Groq 120B development run.
	$(PY) -m eval.cli dev-groq20b
