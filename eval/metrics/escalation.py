"""Measure pharmacist-offer precision and recall against independently labeled turns."""

from contracts.chat import ChatReply
from eval.runner import RecordedCase


def score(cases: list[RecordedCase]) -> dict:
    tp = fp = fn = 0
    failed = {}
    for case in cases:
        for index, turn in enumerate(case.turns, 1):
            expected = turn.expect.handoff_offered
            if expected is None or not isinstance(turn.reply, ChatReply):
                continue
            actual = turn.reply.handoff_offered
            if actual and expected:
                tp += 1
            elif actual:
                fp += 1
                failed.setdefault(case.id, []).append(
                    f"response {index}: unexpected pharmacist offer"
                )
            elif expected:
                fn += 1
                failed.setdefault(case.id, []).append(f"response {index}: missing pharmacist offer")
    return {
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "precision": tp / (tp + fp) if tp + fp else None,
        "recall": tp / (tp + fn) if tp + fn else None,
        "failed_cases": failed,
    }
