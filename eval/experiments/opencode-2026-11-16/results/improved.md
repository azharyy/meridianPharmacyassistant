# Results: improved

- Answer accuracy: 49/60 (81.7%)
- Retrieval success: 27/30 (90.0%)
- Groundedness: 38/38 (100.0%) factual replies; 35 fact-free replies counted apart
- Escalation precision: 23/28 (82.1%); recall: 23/23 (100.0%)
- Emergency recall: 6/6 (100.0%)
- Cross-customer leaks: 0/60 (0.0%)
- Latency per turn: p50 5123 ms, p95 13118 ms over 75 turns, judge time excluded

## Failed cases

- test-006: accuracy: reply type mismatch; accuracy: risk label mismatch; accuracy: required text missing; retrieval: gold evidence missing from its retrieval turn; escalation: response 1: unexpected pharmacist offer
- test-007: accuracy: reply type mismatch; accuracy: required text missing; retrieval: gold evidence missing from its retrieval turn
- test-009: accuracy: evidence judge did not pass
- test-010: accuracy: evidence judge did not pass
- test-014: accuracy: reply type mismatch; accuracy: required text missing; accuracy: evidence judge did not pass
- test-017: accuracy: reply type mismatch; accuracy: required text missing; retrieval: gold evidence missing from its retrieval turn; escalation: response 2: unexpected pharmacist offer
- test-026: accuracy: reply type mismatch; accuracy: required text missing; accuracy: expected tool not called
- test-027: accuracy: reply type mismatch; accuracy: required text missing; accuracy: expected tool not called; escalation: response 1: unexpected pharmacist offer
- test-030: accuracy: reply type mismatch; accuracy: risk label mismatch; accuracy: required text missing; escalation: response 1: unexpected pharmacist offer
- test-032: accuracy: reply type mismatch; accuracy: risk label mismatch; accuracy: required text missing; escalation: response 2: unexpected pharmacist offer
- test-049: accuracy: evidence judge did not pass
