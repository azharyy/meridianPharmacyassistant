"""Hold the policy table and every fixed reply: what each risk label allows, in exact words.

Prompts and eval labels follow this table. Its rows run from the most restrictive label to
the least, so when several labels apply to one turn, the one listed first wins. Only code
reads `handoff_offered` from here; a model never sets it.
"""

from dataclasses import dataclass

from contracts.taxonomy import LabelSection, ReplyType, RiskLabel

# Worded to work whether the person in danger is the customer or someone else.
EMERGENCY_TEXT = (
    "If you or someone with you may be having a medical emergency, call 911 now. "
    "For a possible poisoning or overdose, you can also call Poison Help at 1-800-222-1222. "
    "If you or someone you know is thinking about self-harm, call or text 988."
)
MEDICAL_ADVICE_TEXT = (
    "I can't diagnose a condition or say whether a medicine is right for you. "
    "A pharmacist can help with that."
)
DOSING_BEYOND_LABEL_TEXT = (
    "I can only share what the label's directions say, and I can't advise going beyond them. "
    "A pharmacist can help with your question."
)
PRESCRIPTION_TEXT = (
    "Questions about prescription medicines are for our pharmacists to answer. "
    "A pharmacist can help with that."
)
PROMPT_INJECTION_TEXT = (
    "I can't help with that request. I can answer questions about our products, stores, "
    "policies and your orders."
)
FALLBACK_TEXT = "Sorry, I can't answer right now. If this is an emergency, call 911."
OFF_TOPIC_TEXT = (
    "I can only help with Meridian Pharmacy questions: our products and their labels, stock, "
    "stores, policies and your orders."
)
NOT_FOUND_TEXT = "I couldn't find that in the Meridian catalog."
LOOKUP_FAILED_TEXT = "Sorry, I couldn't check that right now. Please try again in a moment."
ORDER_FORM_TEXT = (
    "To keep your order private, please enter your order number and the email or phone number "
    "on the order in this form, not in the chat."
)
ORDER_NUMBER_LABEL = "Order number"
ORDER_CONTACT_LABEL = "Email or phone number"
ORDER_SUBMIT_LABEL = "Check order"
# The one message for every failed check: an unknown order, a wrong contact, a lockout or a
# timeout all read the same, so nothing reveals which orders exist.
ORDER_NOT_VERIFIED_TEXT = (
    "We couldn't confirm an order with those details. Please check the order number and the "
    "email or phone number, and try again."
)
HANDOFF_CREATED_TEXT = (
    "Your request has gone to a Meridian pharmacist. Your request number is {ticket_id}."
)
HANDOFF_FAILED_TEXT = "Sorry, your request didn't go through. Please try again."
# For a card that a newer one replaced, or that the session never showed: nothing is sent.
HANDOFF_STALE_TEXT = (
    "That card is out of date, so nothing was sent. If this is an emergency, call 911. "
    "To reach a pharmacist, use the newest card or the Talk to a pharmacist button."
)


@dataclass(frozen=True)
class Rule:
    """What a turn with one risk label may end in."""

    reply_types: frozenset[ReplyType]
    sections: frozenset[LabelSection]  # the label sections the reply may show
    text: str | None  # the fixed text shown first; None for the cited answer
    handoff_offered: bool


@dataclass(frozen=True)
class FixedReply:
    """A reply that doesn't depend on a risk label."""

    text: str
    handoff_offered: bool


# The cited answers: what a turn labeled `none` may end in.
ANSWERS = frozenset(
    {
        ReplyType.LABEL_SECTIONS,
        ReplyType.COMPARISON,
        ReplyType.PRODUCT_LIST,
        ReplyType.AVAILABILITY,
        ReplyType.STORE_INFO,
        ReplyType.POLICY,
        ReplyType.ORDER_STATUS,
        ReplyType.ORDER_FORM,
        ReplyType.ORDER_NOT_VERIFIED,
        ReplyType.OFF_TOPIC,
        ReplyType.NOT_FOUND,
        ReplyType.LOOKUP_FAILED,
    }
)
NO_SECTIONS: frozenset[LabelSection] = frozenset()

POLICY: dict[RiskLabel, Rule] = {
    RiskLabel.EMERGENCY: Rule(
        frozenset({ReplyType.EMERGENCY}), NO_SECTIONS, EMERGENCY_TEXT, handoff_offered=True
    ),
    RiskLabel.PROMPT_INJECTION: Rule(
        frozenset({ReplyType.PROMPT_INJECTION}),
        NO_SECTIONS,
        PROMPT_INJECTION_TEXT,
        handoff_offered=True,
    ),
    RiskLabel.PRESCRIPTION: Rule(
        frozenset({ReplyType.PRESCRIPTION}), NO_SECTIONS, PRESCRIPTION_TEXT, handoff_offered=True
    ),
    RiskLabel.MEDICAL_ADVICE: Rule(
        frozenset({ReplyType.MEDICAL_ADVICE}),
        frozenset({LabelSection.WARNINGS}),
        MEDICAL_ADVICE_TEXT,
        handoff_offered=True,
    ),
    RiskLabel.DOSING_BEYOND_LABEL: Rule(
        frozenset({ReplyType.DOSING_BEYOND_LABEL}),
        frozenset({LabelSection.DIRECTIONS}),
        DOSING_BEYOND_LABEL_TEXT,
        handoff_offered=True,
    ),
    RiskLabel.NONE: Rule(ANSWERS, frozenset(LabelSection), None, handoff_offered=False),
}

FIXED_REPLIES: dict[ReplyType, FixedReply] = {
    ReplyType.FALLBACK: FixedReply(FALLBACK_TEXT, handoff_offered=True),
    ReplyType.OFF_TOPIC: FixedReply(OFF_TOPIC_TEXT, handoff_offered=False),
    ReplyType.NOT_FOUND: FixedReply(NOT_FOUND_TEXT, handoff_offered=False),
    ReplyType.LOOKUP_FAILED: FixedReply(LOOKUP_FAILED_TEXT, handoff_offered=False),
    ReplyType.ORDER_NOT_VERIFIED: FixedReply(ORDER_NOT_VERIFIED_TEXT, handoff_offered=False),
}


def most_restrictive(first: RiskLabel, *others: RiskLabel) -> RiskLabel:
    """The label whose reply wins when several apply to one turn."""
    return min((first, *others), key=list(POLICY).index)
