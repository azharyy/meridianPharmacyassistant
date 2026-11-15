# Results: dev

- Answer accuracy: 4/12 (33.3%)
- Retrieval success: 2/4 (50.0%)
- Groundedness: 4/4 (100.0%) factual replies; 9 fact-free replies counted apart
- Escalation precision: 5/9 (55.6%); recall: 5/5 (100.0%)
- Emergency recall: 1/1 (100.0%)
- Cross-customer leaks: 0/12 (0.0%)
- Latency per turn: p50 199 ms, p95 1392 ms over 13 turns, judge time excluded

## Failed cases

- dev-004: accuracy: reply type mismatch; accuracy: required text missing; accuracy: expected tool not called; escalation: response 1: unexpected pharmacist offer
- dev-005: accuracy: reply type mismatch; accuracy: required text missing; escalation: response 1: unexpected pharmacist offer
- dev-007: accuracy: reply type mismatch; accuracy: risk label mismatch; accuracy: required text missing
- dev-008: accuracy: reply type mismatch; accuracy: risk label mismatch; accuracy: required text missing; retrieval: gold evidence missing from its retrieval turn
- dev-009: accuracy: reply type mismatch; accuracy: risk label mismatch; accuracy: required text missing
- dev-010: accuracy: reply type mismatch; accuracy: risk label mismatch; accuracy: required text missing
- dev-011: accuracy: reply type mismatch; accuracy: required text missing; escalation: response 1: unexpected pharmacist offer
- dev-012: accuracy: reply type mismatch; accuracy: required text missing; retrieval: gold evidence missing from its retrieval turn; escalation: response 1: unexpected pharmacist offer
