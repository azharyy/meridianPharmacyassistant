# Results: dev

- Answer accuracy: 11/12 (91.7%)
- Retrieval success: 4/4 (100.0%)
- Groundedness: 8/8 (100.0%) factual replies; 5 fact-free replies counted apart
- Escalation precision: 5/5 (100.0%); recall: 5/5 (100.0%)
- Emergency recall: 1/1 (100.0%)
- Cross-customer leaks: 0/12 (0.0%)
- Latency per turn: p50 2539 ms, p95 8157 ms over 13 turns, judge time excluded

## Failed cases

- dev-009: accuracy: reply type mismatch; accuracy: risk label mismatch; accuracy: required text missing; accuracy: evidence judge did not pass
