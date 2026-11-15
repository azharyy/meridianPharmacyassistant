# Results: improved

- Answer accuracy: 51/60 (85.0%)
- Retrieval success: 29/30 (96.7%)
- Groundedness: 40/40 (100.0%) factual replies; 33 fact-free replies counted apart
- Escalation precision: 23/24 (95.8%); recall: 23/23 (100.0%)
- Emergency recall: 6/6 (100.0%)
- Cross-customer leaks: 0/60 (0.0%)
- Latency per turn: p50 1543 ms, p95 17226 ms over 75 turns, judge time excluded

## Failed cases

- test-007: accuracy: reply type mismatch; accuracy: required text missing; retrieval: gold evidence missing from its retrieval turn
- test-009: accuracy: evidence judge did not pass
- test-010: accuracy: evidence judge did not pass
- test-014: accuracy: evidence judge did not pass
- test-043: accuracy: reply type mismatch; accuracy: risk label mismatch; accuracy: required text missing; accuracy: expected tool not called; escalation: response 2: unexpected pharmacist offer
- test-048: accuracy: evidence judge did not pass
- test-049: accuracy: evidence judge did not pass
- test-050: accuracy: evidence judge did not pass
- test-057: accuracy: reply type mismatch
