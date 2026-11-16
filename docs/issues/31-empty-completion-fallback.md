# Handle empty SDK completion choices

Found during issue30 system verification, authorized by the user's request to
make the assembled project work correctly. Branch: `codex/empty-completion-fallback`.
Scope: `assistant/llm.py`, mirrored `tests/assistant/test_llm.py`,
`tests/assistant/test_app.py`. No dependencies, contracts, prompts or eval data.

Acceptance:
- [x] 1. An SDK response with choices=[] raises the existing TransportError,
  allowing one retry. Empty then valid succeeds; repeated empty produces the
  existing fixed HTTP fallback/offer rather than 500. Tests use synthetic SDK
  HTTP transport only. Full offline checks green; update HANDOFF and commit.

Issue30 verification artifacts are documented but remain outside this fix commit.
