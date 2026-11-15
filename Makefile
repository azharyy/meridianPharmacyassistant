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

# A target-specific variable, so `make run` uses the live model with no shell syntax.
run: export MERIDIAN_LLM := live
run: | .venv  ## Start the API on port 8001 and the assistant on port 8000. Needs GROQ_API_KEY.
	$(PY) -m assistant.launcher
