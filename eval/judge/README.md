# Judge calibration

The judge is `kimi-k3.1-pro` on OpenCode Go, using strict structured outputs and the
same `OPENCODE_API_KEY` as the runtime. Its reasoning effort is `low`. It comes from a
different model family than both runtimes, GLM-5.3-Flash and GLM-5.3.

The held-out runs in `eval/REPORT.md` used the earlier Groq-hosted `qwen/qwen3.8-27b`
judge; its calibration on the same pairs and prompt is kept in
`eval/results/calibration-groq-qwen.md`.

The 20 catalog question-and-reply pairs were labeled by a fresh, independent AI
agent on the user's instruction. It saw only each question and displayed reply,
without the judge prompt, intended draft classification or runtime implementation.
Ten labels are true and ten are false. Independent human validation remains pending.

`make judge-calibrate` measures the live judge's agreement with these supplied AI
labels, records every disagreement and saves the prompt's SHA256. The prompt stays
frozen after calibration. This agreement must not be described as human calibration.
