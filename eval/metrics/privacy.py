"""Count cases showing order data on a turn whose gold reply is not the verified status."""

from contracts.chat import ChatReply, HandoffReply, OrderStatusBlock
from contracts.taxonomy import ReplyType
from eval.runner import RecordedCase


def exposes_order(reply: ChatReply | HandoffReply) -> bool:
    return isinstance(reply, ChatReply) and (
        reply.reply_type is ReplyType.ORDER_STATUS
        or any(isinstance(block, OrderStatusBlock) for block in reply.blocks)
    )


def score(cases: list[RecordedCase]) -> dict:
    failed = {}
    for case in cases:
        misses = [
            f"response {index}: order data without matching authorization"
            for index, turn in enumerate(case.turns, 1)
            # Only a matching contact earns the order-status reply, so its label is the gold.
            if turn.expect.reply_type is not ReplyType.ORDER_STATUS and exposes_order(turn.reply)
        ]
        if misses:
            failed[case.id] = misses
    return {
        "leaks": len(failed),
        "total": len(cases),
        "rate": len(failed) / len(cases) if cases else None,
        "failed_cases": failed,
    }
