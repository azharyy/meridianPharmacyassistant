# Development runtime comparison

The development cases, exact matching, prompts, policy and Qwen judge are the same; settings select the Groq runtime model.
Case expectations are AI labels assigned on the user's instruction; independent human validation remains pending.

| Metric | Groq GPT-OSS 120B | Groq GPT-OSS 20B |
| --- | --- | --- |
| Answer accuracy | 9/12 (75.0%) | 9/12 (75.0%) |
| Latency p50 / p95 | 1676 ms / 13342 ms | 6839 ms / 29221 ms |
| Estimated runtime cost (USD) | unavailable | unavailable |

Cost is estimated from actual provider prompt, cached-input, cache-write and completion token counts. Completion totals already include reasoning tokens. Missing or invalid usage, unknown pricing and unsupported cache writes make cost unavailable. Judge calls are excluded from both runtime cost and stage latency.

Pricing verified 2026-11-15, USD per million tokens:

- [groq openai/gpt-oss-120b](https://console.groq.com/docs/model/openai/gpt-oss-120b): input $0.15, cached input $0.075, cache write unsupported, output $0.6.
- [groq openai/gpt-oss-20b](https://console.groq.com/docs/model/openai/gpt-oss-20b): input $0.075, cached input $0.037, cache write unsupported, output $0.3.

## Failed GPT-OSS 20B cases

- dev-007: accuracy: reply type mismatch; accuracy: risk label mismatch; accuracy: required text missing
- dev-008: accuracy: reply type mismatch; accuracy: risk label mismatch; accuracy: required text missing; accuracy: evidence judge did not pass; escalation: response 1: missing pharmacist offer
- dev-012: accuracy: evidence judge did not pass
