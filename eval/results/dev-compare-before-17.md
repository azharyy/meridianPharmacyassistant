# Development runtime comparison

The development cases, exact matching, prompts, policy and judge are the same; settings select the runtime model.
Case expectations are AI labels assigned on the user's instruction; independent human validation remains pending.

| Metric | opencode glm-5.3-flash | opencode glm-5.3 |
| --- | --- | --- |
| Answer accuracy | 11/12 (91.7%) | 12/12 (100.0%) |
| Latency p50 / p95 | 2539 ms / 8157 ms | 1365 ms / 2083 ms |
| Estimated runtime cost (USD) | at least $0.00201285 (1 attempt without usage) | $0.01637696 |

Cost is estimated from actual provider prompt, cached-input, cache-write and completion token counts. Completion totals already include reasoning tokens. Rate-limited (429) attempts return no completion and count as unbilled. Any other attempt without usage, such as a timeout, is counted but not priced, so that cost reads 'at least'. Unknown pricing and unsupported cache writes make cost unavailable. Judge calls are excluded from both runtime cost and stage latency. On an OpenCode Go plan this usage counts against each model's monthly allowance instead of being billed per token.

Pricing verified 2026-11-15, USD per million tokens:

- [opencode glm-5.3-flash](https://opencode.ai/docs/go/): input $0.15, cached input $0.03, cache write unsupported, output $0.5.
- [opencode glm-5.3](https://opencode.ai/docs/go/): input $1.4, cached input $0.26, cache write unsupported, output $4.4.

## Failed opencode glm-5.3 cases

None.
