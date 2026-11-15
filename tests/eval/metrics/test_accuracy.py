"""Accuracy requires every turn, displayed string, actual tool and relevant judge verdict."""

import pytest

from eval.metrics.accuracy import score
from tests.eval.fixtures import recorded_case, recorded_turn

EXPECT = {"reply_type": "label_sections", "risk_label": "none", "handoff_offered": False}


def test_known_pass_fail_counts_and_every_turn_must_pass():
    good = recorded_case(id="good")
    bad_turn = recorded_turn(judge_correct=False)
    bad = recorded_case(recorded_turn(), bad_turn, id="bad")
    result = score([good, bad])
    assert (result["passed"], result["total"], result["rate"]) == (1, 2, 0.5)
    assert result["failed_cases"] == {"bad": ["evidence judge did not pass"]}


@pytest.mark.parametrize(
    "changes",
    [
        {"expect": {"reply_type": "off_topic", "risk_label": "none", "handoff_offered": False}},
        {"risk": "medical_advice"},
        {"judge_correct": None},
        {"tools": ["get_store_info"], "expect": {**EXPECT, "tool": "check_availability"}},
    ],
)
def test_each_failed_label_tool_or_missing_judge_fails_its_case(changes):
    assert score([recorded_case(recorded_turn(**changes))])["passed"] == 0


def test_the_card_and_unexpected_calls_are_not_accuracy_conditions():
    # The plan's accuracy has no card condition (escalation measures it), and only
    # asks that the expected tool was called.
    expect = {**EXPECT, "handoff_offered": True}
    turn = recorded_turn(expect=expect, tools=["get_store_info"])
    assert score([recorded_case(turn)])["passed"] == 1


def test_required_and_forbidden_text_use_displayed_blocks_and_safe_failure_reasons():
    turn = recorded_turn()
    turn.expect.must_contain = [turn.reply.blocks[0].text]
    assert score([recorded_case(turn)])["passed"] == 1
    turn.expect.must_contain = [turn.reply.sources[0].id]
    turn.expect.must_not_contain = [turn.reply.blocks[0].text]
    result = score([recorded_case(turn)])
    assert result["passed"] == 0
    reasons = str(result["failed_cases"])
    assert "required text missing" in reasons and "forbidden text appeared" in reasons
    assert turn.reply.blocks[0].text not in reasons


def test_retries_count_as_one_expected_tool_kind_and_rejected_requests_do_not():
    turn = recorded_turn(tools=["check_availability"] * 2)
    turn.expect.tool = "check_availability"
    assert score([recorded_case(turn)])["passed"] == 1
    turn.tools = []
    turn.requested_tool = "check_availability"
    assert score([recorded_case(turn)])["passed"] == 0


def test_empty_results_have_no_rate_and_empty_conversations_cannot_pass():
    assert score([])["rate"] is None
    case = recorded_case().model_copy(update={"turns": []})
    assert score([case])["passed"] == 0
