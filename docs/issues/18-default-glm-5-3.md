# Make GLM-5.3 the default runtime model

From `docs/FIXES.md` section D, step 3. After issue 17 the user ran `make eval-dev` and
`make eval-compare` on main a8e60ac (2026-11-16). Both models scored 12/12 on the
development cases. GLM-5.3 had p95 1928 ms against GLM-5.3-Flash's 10209 ms, at an
estimated $0.01696942 against $0.00267615 per run, with a $15 monthly Go allowance against
$60. Both runs' metrics and summaries reproduce from their stored traces. On those results
the user chose "Switch to GLM-5.3". Branch: `default-glm-5-3`. No attribution in commits
or the pull request.

Scope:
- `assistant/settings.py`: GLM-5.3 becomes the default and GLM-5.3-Flash the comparison.
- `Makefile`: the eval and calibration targets pin GLM-5.3; `eval-compare` pins GLM-5.3-Flash.
- `.env.example` comments.
- `README.md`.
- `eval/results/`: the two new development runs, plus the two earlier ones archived as
  `dev-before-17.*` and `dev-compare-before-17.*`.
- Mirrored tests.

No prompts, policy, contracts, dependencies, cases or held-out results.

Acceptance criteria:
- [ ] 1. With no `MERIDIAN_RUNTIME_MODEL`, the runtime is GLM-5.3. GLM-5.3-Flash stays
  selectable, and Groq is unchanged. `make eval-dev` and the held-out targets pin GLM-5.3,
  `eval-compare` pins GLM-5.3-Flash, and the CLI's model guard follows. Prove it in
  `tests/assistant/test_settings.py` and `tests/eval/test_cli.py`. The full offline suite
  stays green.
- [ ] 2. The new runs are committed, the earlier development runs are kept under their new
  names, and the README names each configuration, run and number. It also says that
  GLM-5.3-Flash's 12/12 came from the model labeling dev-009 correctly this time, not from
  issue 17, and that the held-out set has not been measured on GLM-5.3. Every path in the
  README resolves.

A later `make eval-dev` writes a GLM-5.3 run to `eval/results/dev.json`, and `make eval-compare`
then compares GLM-5.3-Flash against it.
