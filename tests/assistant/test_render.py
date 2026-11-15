"""The renderer builds replies from templates and record text only, and the fallback from policy."""

import pytest

from assistant import policy, templates
from assistant.render import render, render_fallback, render_risk
from contracts.chat import ChatReply, TextBlock
from contracts.plan import CatalogPlan
from contracts.taxonomy import LabelSection, ReplyType, RiskLabel
from tests.assistant.fixtures import PLAN, PRODUCTS


def strings(value) -> list[str]:
    """Every string in a JSON value."""
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [s for item in value.values() for s in strings(item)]
    if isinstance(value, list):
        return [s for item in value for s in strings(item)]
    return []


def allowed_strings() -> set[str]:
    """Record text, template wording, and the IDs and enum values a reply carries."""
    record_text = {value for p in PRODUCTS for value in p.model_dump(mode="json").values()}
    titles = set(templates.SECTION_TITLES.values())
    source_titles = {
        templates.LABEL_SOURCE_TITLE.format(name=p.name, section=t)
        for p in PRODUCTS
        for t in titles
    }
    ids = {f"{p.sku}#{s.value}" for p in PRODUCTS for s in LabelSection}
    enums = {e.value for e in (*ReplyType, *LabelSection)} | {"label_section", "text"}
    return {str(v) for v in record_text} | titles | source_titles | ids | enums


def test_the_cited_answer_is_the_label_section_word_for_word():
    reply = render(PLAN, PRODUCTS, RiskLabel.NONE, None)
    assert reply.reply_type is ReplyType.LABEL_SECTIONS
    [block] = reply.blocks
    assert (block.sku, block.section, block.title) == ("MRD-ALG-012", "directions", "Directions")
    assert block.text == PRODUCTS[0].directions
    [source] = reply.sources
    assert (source.id, source.text) == ("MRD-ALG-012#directions", PRODUCTS[0].directions)
    assert source.title == "Meridian All Day Allergy: Directions"
    assert (reply.handoff_offered, reply.emergency) == (False, False)


def test_the_reply_holds_only_template_and_record_text():
    reply = render(PLAN, PRODUCTS, RiskLabel.NONE, None)
    shown = strings(reply.model_dump(mode="json"))
    assert set(shown) <= allowed_strings()


def test_the_fallback_is_the_policys_fixed_reply_with_the_card():
    reply = render_fallback()
    assert reply == ChatReply(
        reply_type=ReplyType.FALLBACK,
        blocks=[{"type": "text", "text": policy.FALLBACK_TEXT}],
        sources=[],
        handoff_offered=True,
        emergency=False,
    )
    assert "call 911" in reply.blocks[0].text


def test_a_plan_naming_a_record_that_was_not_retrieved_gets_the_fallback():
    stray = CatalogPlan(
        reply_type="label_sections",
        records=[{"record_id": "MRD-ALG-999", "sections": ["directions"]}],
        tool=None,
    )
    assert render(stray, PRODUCTS, RiskLabel.NONE, None) == render_fallback()


def test_a_reply_type_this_issue_does_not_build_yet_gets_the_fallback():
    plan = PLAN.model_copy(update={"reply_type": ReplyType.COMPARISON})
    assert render(plan, PRODUCTS, RiskLabel.NONE, None) == render_fallback()


RISKS = [
    RiskLabel.EMERGENCY,
    RiskLabel.MEDICAL_ADVICE,
    RiskLabel.DOSING_BEYOND_LABEL,
    RiskLabel.PRESCRIPTION,
    RiskLabel.PROMPT_INJECTION,
]


@pytest.mark.parametrize("risk", RISKS)
def test_each_risk_reply_is_its_fixed_text_first_and_offers_the_card(risk):
    reply = render_risk(risk, None)
    assert reply.blocks == [TextBlock(type="text", text=policy.POLICY[risk].text)]
    assert reply.reply_type in policy.POLICY[risk].reply_types
    assert (reply.handoff_offered, reply.sources) == (True, [])
    assert reply.emergency is (risk is RiskLabel.EMERGENCY)


def test_the_911_reply_comes_first_and_the_card_after_it():
    reply = render_risk(RiskLabel.EMERGENCY, PRODUCTS[0])
    assert reply.blocks[0].text == policy.EMERGENCY_TEXT and len(reply.blocks) == 1
    assert reply.handoff_offered and reply.emergency


@pytest.mark.parametrize(
    ("risk", "section"),
    [
        (RiskLabel.MEDICAL_ADVICE, LabelSection.WARNINGS),
        (RiskLabel.DOSING_BEYOND_LABEL, LabelSection.DIRECTIONS),
    ],
)
def test_a_named_product_adds_only_the_section_the_label_allows(risk, section):
    reply = render_risk(risk, PRODUCTS[0])
    [_, block] = reply.blocks
    assert (block.section, block.text) == (section, getattr(PRODUCTS[0], section.value))
    assert [source.id for source in reply.sources] == [f"MRD-ALG-012#{section.value}"]


def test_a_prescription_refusal_shows_no_label_even_for_a_named_product():
    assert render_risk(RiskLabel.PRESCRIPTION, PRODUCTS[0]) == render_risk(
        RiskLabel.PRESCRIPTION, None
    )


def test_a_turn_without_risk_has_no_fixed_reply():
    with pytest.raises(ValueError):
        render_risk(RiskLabel.NONE, None)
