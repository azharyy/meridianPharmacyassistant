"""Pharmacist-offer metrics count labeled false positives and false negatives independently."""

import pytest

from contracts.chat import HandoffReply
from eval.metrics.escalation import score
from tests.eval.fixtures import recorded_case, recorded_turn


def offer(expected, actual):
    turn = recorded_turn()
    return recorded_turn(
        question="private@example.com",
        reply=turn.reply.model_copy(update={"handoff_offered": actual}),
        expect={"reply_type": "label_sections", "risk_label": "none", "handoff_offered": expected},
    )


def test_precision_and_recall_use_each_labeled_chat_reply_and_report_both_error_kinds():
    ignored_handoff = recorded_turn(
        action="handoff", reply=HandoffReply(ticket_id="TCK-1001", text="Ticket created.")
    )
    case = recorded_case(
        offer(True, True),
        offer(False, True),
        offer(True, False),
        offer(False, False),
        offer(None, True),
        ignored_handoff,
    )
    before = case.model_dump_json()
    result = score([case])
    assert {key: result[key] for key in ("tp", "fp", "fn", "precision", "recall")} == {
        "tp": 1,
        "fp": 1,
        "fn": 1,
        "precision": 0.5,
        "recall": 0.5,
    }
    assert result["failed_cases"] == {
        case.id: ["response 2: unexpected pharmacist offer", "response 3: missing pharmacist offer"]
    }
    assert "private@example.com" not in str(result) and case.model_dump_json() == before


@pytest.mark.parametrize(
    ("expected", "actual", "precision", "recall"),
    [
        (True, True, 1.0, 1.0),
        (False, True, 0.0, None),
        (True, False, None, 0.0),
        (False, False, None, None),
    ],
)
def test_zero_denominators_are_unavailable_rather_than_perfect(expected, actual, precision, recall):
    result = score([recorded_case(offer(expected, actual))])
    assert result["precision"] == precision and result["recall"] == recall


def test_no_labeled_replies_have_no_measured_precision_or_recall():
    assert score([]) == {
        "tp": 0,
        "fp": 0,
        "fn": 0,
        "precision": None,
        "recall": None,
        "failed_cases": {},
    }
