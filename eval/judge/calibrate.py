"""Run the judge on labeled calibration pairs and measure agreement with the supplied labels."""

from hashlib import sha256
from pathlib import Path
from typing import Literal

from pydantic import Field, StrictBool

from assistant.llm import ModelClient
from contracts.base import Contract
from eval.judge.judge import PROMPT, verdict

PAIRS = Path(__file__).parent / "calibration.jsonl"
# Recorded with each calibration, so the report shows a prompt changed after it.
PROMPT_SHA256 = sha256(PROMPT.encode()).hexdigest()


class Pair(Contract):
    id: str = Field(min_length=1)
    question: str = Field(min_length=1)
    reply: str = Field(min_length=1)  # the reply as displayed
    drafted_as: Literal["right evidence", "wrong product", "wrong section"]
    label: StrictBool | None  # do the shown sections answer the question?


def load_pairs(path: Path = PAIRS) -> list[Pair]:
    lines = path.read_text(encoding="utf-8").splitlines()
    return [Pair.model_validate_json(line) for line in lines if line.strip()]


def calibrate(judge: ModelClient, pairs: list[Pair]) -> dict:
    """Agreement with the supplied labels as raw counts, and every disagreement."""
    if not pairs or any(pair.label is None for pair in pairs):
        raise ValueError("label every calibration pair true or false before calibrating")
    disagreements = []
    for pair in pairs:
        answer = verdict(judge, pair.question, pair.reply)
        if answer != pair.label:
            disagreements.append({"id": pair.id, "label": pair.label, "judge": answer})
    agreed = len(pairs) - len(disagreements)
    return {
        "agreed": agreed,
        "total": len(pairs),
        "rate": agreed / len(pairs),
        "disagreements": disagreements,
        "prompt_sha256": PROMPT_SHA256,
    }


def summary(result: dict) -> str:
    lines = [f"Judge agreement: {result['agreed']}/{result['total']} ({result['rate']:.1%})"]
    lines += [
        f"- {item['id']}: labeled {item['label']}, the judge said {item['judge']}"
        for item in result["disagreements"]
    ]
    return "\n".join(lines)
