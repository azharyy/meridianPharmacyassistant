"""Check the policy table against the plan's Safety policy, and every fixed text."""

import pytest

from assistant import policy
from assistant.policy import FIXED_REPLIES, POLICY, most_restrictive
from contracts.taxonomy import LabelSection, ReplyType, RiskLabel

RISK_ROWS = [
    (RiskLabel.EMERGENCY, ReplyType.EMERGENCY, set()),
    (RiskLabel.PROMPT_INJECTION, ReplyType.PROMPT_INJECTION, set()),
    (RiskLabel.PRESCRIPTION, ReplyType.PRESCRIPTION, set()),
    (RiskLabel.MEDICAL_ADVICE, ReplyType.MEDICAL_ADVICE, {LabelSection.WARNINGS}),
    (RiskLabel.DOSING_BEYOND_LABEL, ReplyType.DOSING_BEYOND_LABEL, {LabelSection.DIRECTIONS}),
]


def test_every_risk_label_has_a_policy_row():
    assert set(POLICY) == set(RiskLabel)


def test_emergency_text_names_911_first_then_poison_help_and_988():
    text = policy.EMERGENCY_TEXT
    assert text.index("911") < text.index("1-800-222-1222") < text.index("988")


def test_fallback_says_call_911_and_offers_a_pharmacist():
    assert "call 911" in policy.FALLBACK_TEXT
    assert FIXED_REPLIES[ReplyType.FALLBACK] == policy.FixedReply(
        policy.FALLBACK_TEXT, handoff_offered=True
    )


@pytest.mark.parametrize(("label", "reply_type", "sections"), RISK_ROWS)
def test_each_risk_label_gets_its_fixed_reply_and_the_card(label, reply_type, sections):
    rule = POLICY[label]
    assert rule.reply_types == {reply_type}
    assert rule.sections == sections
    assert rule.text
    assert rule.handoff_offered


def test_one_refusal_per_label():
    refusals = [rule.text for label, rule in POLICY.items() if label is not RiskLabel.NONE]
    assert len(set(refusals)) == len(refusals) == len(RISK_ROWS)


def test_a_turn_without_risk_gets_a_cited_answer_and_no_card():
    rule = POLICY[RiskLabel.NONE]
    assert (rule.text, rule.handoff_offered) == (None, False)
    assert rule.sections == set(LabelSection)
    assert not rule.reply_types & {reply_type for _, reply_type, _ in RISK_ROWS}
    assert ReplyType.FALLBACK not in rule.reply_types


def test_every_reply_type_has_a_place_in_the_policy():
    allowed = set().union(*(rule.reply_types for rule in POLICY.values()))
    assert allowed | set(FIXED_REPLIES) == set(ReplyType)


@pytest.mark.parametrize(
    ("reply_type", "text"),
    [
        (ReplyType.OFF_TOPIC, policy.OFF_TOPIC_TEXT),
        (ReplyType.NOT_FOUND, policy.NOT_FOUND_TEXT),
        (ReplyType.LOOKUP_FAILED, policy.LOOKUP_FAILED_TEXT),
        (ReplyType.ORDER_NOT_VERIFIED, policy.ORDER_NOT_VERIFIED_TEXT),
    ],
)
def test_fixed_replies_without_risk_offer_no_card(reply_type, text):
    assert FIXED_REPLIES[reply_type] == policy.FixedReply(text, handoff_offered=False)


def test_most_restrictive_label_wins():
    assert list(POLICY) == [
        RiskLabel.EMERGENCY,
        RiskLabel.PROMPT_INJECTION,
        RiskLabel.PRESCRIPTION,
        RiskLabel.MEDICAL_ADVICE,
        RiskLabel.DOSING_BEYOND_LABEL,
        RiskLabel.NONE,
    ]
    assert most_restrictive(RiskLabel.NONE, RiskLabel.EMERGENCY) is RiskLabel.EMERGENCY
    assert most_restrictive(RiskLabel.MEDICAL_ADVICE, RiskLabel.PROMPT_INJECTION) is (
        RiskLabel.PROMPT_INJECTION
    )
    assert most_restrictive(RiskLabel.DOSING_BEYOND_LABEL, RiskLabel.MEDICAL_ADVICE) is (
        RiskLabel.MEDICAL_ADVICE
    )
    assert most_restrictive(RiskLabel.NONE) is RiskLabel.NONE


def test_handoff_texts_show_the_ticket_or_offer_a_retry():
    assert "TCK-1042" in policy.HANDOFF_CREATED_TEXT.format(ticket_id="TCK-1042")
    assert "try again" in policy.HANDOFF_FAILED_TEXT


def test_order_form_wording_is_complete():
    for text in (
        policy.ORDER_FORM_TEXT,
        policy.ORDER_NUMBER_LABEL,
        policy.ORDER_CONTACT_LABEL,
        policy.ORDER_SUBMIT_LABEL,
    ):
        assert text.strip() == text and text
