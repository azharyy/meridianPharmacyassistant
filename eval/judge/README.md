# Judge calibration

The judge is Groq-hosted `qwen/qwen3.8-27b`, using strict structured outputs and
the same `GROQ_API_KEY` as the GPT-OSS runtime. Its reasoning setting is `none`.

The 20 catalog question-and-reply pairs were labeled by a fresh, independent AI
agent on the user's instruction. It saw only each question and displayed reply,
without the judge prompt, intended draft classification or runtime implementation.
Ten labels are true and ten are false. Independent human validation remains pending.

`make judge-calibrate` measures the live judge's agreement with these supplied AI
labels, records every disagreement and saves the prompt's SHA256. The prompt stays
frozen after calibration. This agreement must not be described as human calibration.
