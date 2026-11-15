"""Score a conversation only when every reply meets its gold labels and evidence verdict."""

from contracts.chat import ChatReply
from eval.display import displayed, needs_judge
from eval.runner import RecordedCase, RecordedTurn


def failures(turn: RecordedTurn) -> list[str]:
    expected, reply = turn.expect, turn.reply
    found = []
    if expected.reply_type is not None and (
        not isinstance(reply, ChatReply) or reply.reply_type != expected.reply_type
    ):
        found.append("reply type mismatch")
    if expected.risk_label is not None and turn.risk != expected.risk_label:
        found.append("risk label mismatch")
    shown = displayed(reply)
    if any(text not in shown for text in expected.must_contain):
        found.append("required text missing")
    if any(text in shown for text in expected.must_not_contain):
        found.append("forbidden text appeared")
    if expected.tool is not None and expected.tool not in turn.tools:
        found.append("expected tool not called")
    if needs_judge(reply) and turn.judge_correct is not True:
        found.append("evidence judge did not pass")
    return found


def score(cases: list[RecordedCase]) -> dict:
    failed = {}
    for case in cases:
        reasons = [reason for turn in case.turns for reason in failures(turn)]
        if not case.turns:
            reasons.append("case produced no replies")
        if reasons:
            failed[case.id] = list(dict.fromkeys(reasons))
    passed, total = len(cases) - len(failed), len(cases)
    return {
        "passed": passed,
        "total": total,
        "rate": passed / total if total else None,
        "failed_cases": failed,
    }
