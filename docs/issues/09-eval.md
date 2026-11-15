Builder: Claude · Review: CI and the user's read · Starts after: 2 and 3
Folders: `eval/`, `tests/eval/`, `assistant/settings.py`, `tests/assistant/test_settings.py`, `tests/assistant/test_llm.py`, `.env.example`. A narrow README setup correction is allowed. Adds the make targets `eval-dev`, `eval-baseline`, `eval`, `eval-compare` and `judge-calibrate`.
Plan sections: Evaluation; Architecture (Model calls); Module map and rules.

User amendment (2026-11-15): use the Groq API exclusively. The runtime remains
`openai/gpt-oss-120b`, the judge is `qwen/qwen3.8-27b`, and the development comparison
uses `openai/gpt-oss-20b` with the same Qwen judge. All support strict structured
outputs; no tools are sent. Both roles use the existing `GROQ_API_KEY` and Groq URL;
OpenAI API configuration is removed. `MERIDIAN_RUNTIME_MODEL` selects either runtime
through settings alone. Pin the runtime model in every eval target. The user also
authorized live runs and independent AI labeling; report AI provenance and the lack
of independent human validation. These changes supersede the original provider and
human-label requirements below; contracts, dependencies and PLAN stay unchanged.

User amendment 2 (2026-11-15): `make run` may use the user's OpenCode Go subscription
instead of Groq, chosen in `.env` (`MERIDIAN_RUNTIME_PROVIDER=opencode` and
`OPENCODE_API_KEY`). Only Go-plan models that OpenCode lists with structured output on its
chat-completions API and "low" reasoning effort are accepted: `glm-5.3-flash` (default) and
`deepseek-v4.1-flash`. Groq stays the default runtime; the judge and every eval target stay
on Groq, so the measured results and the calibration are unchanged.

User amendment 3 (2026-11-15), superseding the defaults of amendments 1 and 2: OpenCode Go
becomes the default for every role. The runtime is `glm-5.3-flash`; `make eval-compare` runs
the development set on `deepseek-v4.1-flash` and writes `eval/results/dev-compare.md` beside
the GLM run; the judge is `kimi-k3.1-pro` (another model family), recalibrated on the same 20
pairs with the prompt unchanged. All use `OPENCODE_API_KEY`; Groq stays selectable for the
runtime only. The held-out test results stay as measured on Groq GPT-OSS 120B with the Groq
Qwen judge and are not run again; the README says so, and the Qwen calibration is kept as
`eval/results/calibration-groq-qwen.*`. Folders also: `tests/assistant/test_app.py` and
`tests/assistant/test_launcher.py`, whose missing-key checks follow the default key.

The harness, the metrics, the judge, the report and drafted cases for the user to label. One pull request; the three parts below are its order of work. Keep the loader, the runner, each metric, the judge and the report in separate modules, and make each metric a pure function over recorded results.

Acceptance criteria, part (a)
- [ ] Loader: one JSON record per line, holding the turns (customer messages and scripted actions: submit the order form, confirm a handoff, send the API timeout header) and the expectations (reply type, risk label, whether the card is offered, the gold sources that should be retrieved, strings that must and must not appear, the tool that must be called). A malformed record fails with its line number.
- [ ] Runner: it drives the assistant in-process, case by case and turn by turn, and records each reply, its sources, the retrieved records, its flags and its stage timings.
- [ ] Each metric is computed exactly as the plan's table defines it: answer accuracy, retrieval success, groundedness with the count of fact-free replies, escalation precision and recall, emergency recall, cross-customer leaks, and p50 and p95 latency without judge time.
- [ ] Every run writes its raw results as JSON and a short Markdown summary to `eval/results/` (`dev`, `baseline`, `improved`), listing every failed case with its reason.
- [ ] Report: `eval/REPORT.md` shows the baseline and the improved run side by side, with answer accuracy as the headline and retrieval success beside it, the cases that changed between them, every failed case with its reason, and every safety miss by case, as raw counts and percentages.
- [ ] `make eval-dev` runs the development set. `make eval-baseline` and `make eval` run the test set with `MERIDIAN_EXACT_MATCH=0` and `1`. All three use the live models, and each target sets `MERIDIAN_LLM` and the match flag itself as make variables, so nothing but the keys has to be in `.env`. The harness itself is tested offline with the runtime and the judge both faked.

Acceptance criteria, part (b)
- [ ] The judge runs Qwen 3.8 27B on Groq, through the shared model client's judge role, with strict structured outputs only. Its one job: given the customer's question and the reply as displayed, return whether the records and sections shown answer the question.
- [ ] The judge scores only replies that show catalog or policy text, and its verdict is one condition of answer accuracy. Judge time is never counted in latency.
- [ ] `eval/judge/calibration.jsonl` holds 20 drafted question-and-reply pairs for the user to label, about half of them showing deliberately wrong evidence (the wrong product, or the wrong section), built from the catalog and apart from both case sets.
- [ ] `make judge-calibrate` runs the judge on those pairs and prints the agreement and each disagreement; the report includes that result. The judge prompt lives in `eval/judge/` and is not changed after calibration.
- [ ] `make eval-compare` runs the development set with Groq-hosted GPT-OSS 20B as the runtime, by settings alone, and writes `eval/results/dev-groq20b.md` with accuracy, latency and cost beside the GPT-OSS 120B run. The Qwen judge stays fixed.

Acceptance criteria, part (c)
- [ ] Drafted cases for the user to label: 12 in `eval/cases/dev.jsonl` and 60 in `eval/cases/test.jsonl`, following the plan's slice table, with at least ten multi-turn test cases. The product cases phrased with a brand name or an everyday word are the user's own questions from `eval/cases/handwritten_questions.md`, wrapped in the case format without changing a word.
- [ ] Development cases cover the same slices with different products and phrasings, never paraphrases of test cases.
- [ ] The cases are drafted without reading `catalog/aliases.yaml`, and their gold sources use real SKUs from `catalog/products.json`. A builder that also built issue 5, 6 or 7 hands the drafting to a fresh subagent, tells it not to open `catalog/aliases.yaml`, `assistant/retrieval/`, `assistant/prompts/` or `assistant/safety/`, and checks `eval/cases/test.jsonl` only through the loader, never by reading it.

Tests: the loader on a good and a malformed record; the runner on scripted fake responses; each metric on a few hand-built results with known answers, including one failing case per metric; a faked judge verdict flipping a case's accuracy; the calibration run on faked verdicts; the report's sections. Done when `make check` passes.
Follow the Session protocol in AGENTS.md.
