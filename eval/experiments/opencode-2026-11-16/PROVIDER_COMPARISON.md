# Historical Groq and current OpenCode results

New OpenCode runs measured 2026-11-16 on the current fixed code. This compares preserved Groq runs with newly completed OpenCode runs. No Groq calls were made for this experiment. Original results were not overwritten.

## Held-out metrics

| Metric | Groq baseline (archived) | Groq improved (archived) | OpenCode baseline (new) | OpenCode improved (new) |
| --- | --- | --- | --- | --- |
| Answer accuracy | 50/60 (83.3%) | 51/60 (85.0%) | 46/60 (76.7%) | 49/60 (81.7%) |
| Retrieval success | 29/30 (96.7%) | 29/30 (96.7%) | 26/30 (86.7%) | 27/30 (90.0%) |
| Groundedness | 40/40 (100.0%), 33 fact-free apart | 40/40 (100.0%), 33 fact-free apart | 35/35 (100.0%), 38 fact-free apart | 38/38 (100.0%), 35 fact-free apart |
| Escalation precision | 23/25 (92.0%) | 23/24 (95.8%) | 23/30 (76.7%) | 23/28 (82.1%) |
| Escalation recall | 23/23 (100.0%) | 23/23 (100.0%) | 23/23 (100.0%) | 23/23 (100.0%) |
| Emergency recall | 6/6 (100.0%) | 6/6 (100.0%) | 6/6 (100.0%) | 6/6 (100.0%) |
| Cross-customer leaks | 0/60 (0.0%) | 0/60 (0.0%) | 0/60 (0.0%) | 0/60 (0.0%) |
| Latency p50 / p95 | 2609 ms / 25545 ms | 1543 ms / 17226 ms | 4971 ms / 16859 ms | 5123 ms / 13118 ms |

The new exact-matching run scored 49/60 versus 46/60 for its keyword baseline, a net gain of three cases in one sequential pair. Retrieval rose from 26/30 to 27/30. This is an observed pair, not a statistically established improvement.

Compared with the archived improved run, current accuracy is two cases lower (81.7% versus 85.0%), while p95 is lower (13.118 s versus 17.226 s). Current accuracy, escalation precision (82.1%) and p95 still miss the project targets of 90%, 85% and four seconds. Groundedness, required-offer recall, emergency recall and zero-leak targets pass on these labeled cases.

## Comparison limits and configuration

This is a historical-versus-current comparison, not a controlled provider-only A/B. The case and judge-prompt fingerprints match, but runtime model, judge model and implementation differ. Provider/service variability, timeouts and model nondeterminism also affect one sequential pair. Do not attribute a score change solely to the API provider.

| Configuration | Archived Groq | New OpenCode |
| --- | --- | --- |
| Runtime | groq / openai/gpt-oss-120b | opencode / glm-5.3 |
| Judge | groq / qwen/qwen3.8-27b | opencode / kimi-k3.1-pro |
| Implementation SHA256 | `2c526d6c47a6e0cfbfae03972548efb1e014ccc68722a7719c69eb14b4bc1264` | `fd2bc0923298f08819cd390b07e8a5bcd3b725c738940e014ee6a2d5669e3a50` |
| Case SHA256 | `a1961a2b425465521d3d69221151d2c61c2269276ec4308ec08f158248b15d02` | `a1961a2b425465521d3d69221151d2c61c2269276ec4308ec08f158248b15d02` |
| Judge prompt SHA256 | `f3d18cdf3851611ad835e7ccc5e658dbd1754ed5ed64e068a5f9dd61523a3a1a` | `f3d18cdf3851611ad835e7ccc5e658dbd1754ed5ed64e068a5f9dd61523a3a1a` |

Both variants within each provider pair have matching configuration metadata and the expected false/true retrieval flags. All four raw files contain the same 60 case IDs. The new files record live OpenCode mode and actual usage; source fingerprints remained valid when the user requested continuation, so no successful run was restarted.

## Live calibration and development checks

- Kimi K3.1 Pro: 20/20 calibration agreement against the existing AI labels. Independent human label review remains pending.
- GLM-5.3 development: 12/12 accuracy; p50 5.166 s, p95 12.400 s.
- GLM-5.3-Flash development: 10/12 accuracy; p50 5.897 s, p95 13.534 s. Failed cases: dev-003 and dev-009. Both models had 7/7 grounded factual replies, full labeled escalation/emergency recall and zero leaks.
- Full offline suite: 1,461 tests pass, plus Ruff lint/format. Offline tests always use fakes; these live evaluations are separate.

The baseline contains four fallback replies in total; the runtime log identified three as exhausted provider timeouts. Improved contains two fallback replies, both observed as exhausted provider timeouts. All remain in the results and latency. There was no resampling, prompt/alias tuning, gold-label change or model substitution to improve the scores.

## Credential loading and artifacts

The existing project credential worked when loaded through `uv run --env-file .env`. The earlier missing-key claim came from inspecting only the inherited process environment, which had not loaded the project file. No key values were displayed or copied. Every new model request used the configured OpenCode endpoint; calibration and runtime roles were explicitly pinned.

- [New paired report](REPORT.md)
- [New baseline raw data](results/baseline.json) and [summary](results/baseline.md)
- [New improved raw data](results/improved.json) and [summary](results/improved.md)
- [New calibration](results/calibration.md)
- [New development model comparison](results/dev-compare.md)
- [Archived paired report](../../REPORT.md)
- [Archived baseline raw data](../../results/baseline.json) and [improved raw data](../../results/improved.json)

For another experiment, use a fresh nested output directory and the README commands. Preserve this run, the archives and any failed attempts; never replace a valid score merely because a later run might look better.
