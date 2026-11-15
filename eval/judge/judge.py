"""Ask the judge whether the records and sections a reply shows answer the customer's question."""

from pathlib import Path

from assistant.llm import ModelClient, ModelUnavailable
from contracts.base import Contract
from eval.display import displayed, needs_judge
from eval.runner import RecordedCase

PROMPT = (Path(__file__).parent / "prompt.txt").read_text(encoding="utf-8")


class Verdict(Contract):
    answers_question: bool


def verdict(judge: ModelClient, question: str, reply: str) -> bool:
    """One structured call: the question and the reply as displayed, marked as data."""
    messages = [
        {"role": "system", "content": PROMPT},
        {
            "role": "user",
            "content": f"<question>\n{question}\n</question>\n<reply>\n{reply}\n</reply>",
        },
    ]
    return judge.complete(messages, Verdict).answers_question


def judge_cases(judge: ModelClient, cases: list[RecordedCase]) -> None:
    """Score each reply that shows catalog or policy text, after the run, outside its timings."""
    for case in cases:
        for turn in case.turns:
            if not needs_judge(turn.reply):
                continue
            try:
                turn.judge_correct = verdict(judge, turn.question, displayed(turn.reply))
            except ModelUnavailable as error:
                turn.judge_error = str(error)  # no verdict, so accuracy fails the turn
