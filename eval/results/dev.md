# Results: dev

- Answer accuracy: 9/12 (75.0%)
- Retrieval success: 4/4 (100.0%)
- Groundedness: 7/7 (100.0%) factual replies; 6 fact-free replies counted apart
- Escalation precision: 5/5 (100.0%); recall: 5/5 (100.0%)
- Emergency recall: 1/1 (100.0%)
- Cross-customer leaks: 0/12 (0.0%)
- Latency per turn: p50 1676 ms, p95 13342 ms over 13 turns, judge time excluded

## Failed cases

- dev-003: accuracy: reply type mismatch
- dev-008: accuracy: evidence judge did not pass
- dev-012: accuracy: evidence judge did not pass
