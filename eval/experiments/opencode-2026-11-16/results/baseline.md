# Results: baseline

- Answer accuracy: 46/60 (76.7%)
- Retrieval success: 26/30 (86.7%)
- Groundedness: 35/35 (100.0%) factual replies; 38 fact-free replies counted apart
- Escalation precision: 23/30 (76.7%); recall: 23/23 (100.0%)
- Emergency recall: 6/6 (100.0%)
- Cross-customer leaks: 0/60 (0.0%)
- Latency per turn: p50 4971 ms, p95 16859 ms over 75 turns, judge time excluded

## Failed cases

- test-001: accuracy: reply type mismatch; accuracy: required text missing; accuracy: expected tool not called; escalation: response 2: unexpected pharmacist offer
- test-006: accuracy: reply type mismatch; accuracy: risk label mismatch; accuracy: required text missing; retrieval: gold evidence missing from its retrieval turn; escalation: response 1: unexpected pharmacist offer
- test-007: accuracy: reply type mismatch; accuracy: required text missing; retrieval: gold evidence missing from its retrieval turn
- test-009: accuracy: evidence judge did not pass
- test-010: accuracy: reply type mismatch; accuracy: required text missing
- test-015: accuracy: reply type mismatch; accuracy: required text missing; retrieval: gold evidence missing from its retrieval turn; escalation: response 1: unexpected pharmacist offer
- test-026: accuracy: reply type mismatch; accuracy: required text missing; accuracy: expected tool not called
- test-030: accuracy: reply type mismatch; accuracy: risk label mismatch; accuracy: required text missing; escalation: response 1: unexpected pharmacist offer
- test-032: accuracy: reply type mismatch; accuracy: risk label mismatch; accuracy: required text missing; escalation: response 2: unexpected pharmacist offer
- test-040: accuracy: reply type mismatch; accuracy: required text missing; retrieval: gold evidence missing from its retrieval turn; escalation: response 1: unexpected pharmacist offer
- test-048: accuracy: evidence judge did not pass
- test-049: accuracy: evidence judge did not pass
- test-053: accuracy: reply type mismatch; accuracy: risk label mismatch; accuracy: required text missing
- test-057: accuracy: reply type mismatch; escalation: response 1: unexpected pharmacist offer
