"""Validate every example reply against the contract, and keep the examples true to the policy.

The widget's preview page draws these files, so each must be a reply the assistant could send.
"""

import json
from pathlib import Path
from typing import get_args

import pytest

from assistant import policy
from contracts.chat import Block, ChatReply, HandoffReply
from contracts.taxonomy import LabelSection, ReplyType

EXAMPLES = Path(__file__).resolve().parents[2] / "contracts" / "examples"
REPLIES = sorted((EXAMPLES / "replies").glob("*.json"))
ORDER_FORM = {
    "type": "order_form",
    "text": policy.ORDER_FORM_TEXT,
    "order_number_label": policy.ORDER_NUMBER_LABEL,
    "contact_label": policy.ORDER_CONTACT_LABEL,
    "submit_label": policy.ORDER_SUBMIT_LABEL,
}


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def reply(path: Path) -> ChatReply:
    return ChatReply.model_validate(load(path))


def citations(block) -> dict[str, str | None]:
    """Each source a block cites, with the text the block shows from it (None for API data)."""
    if block.type == "comparison":
        return {
            f"{product.sku}#{row.section}": row.texts[i]
            for row in block.rows
            for i, product in enumerate(block.products)
        }
    if block.type == "product_list":
        return {product.source_id: product.uses for product in block.products}
    if block.type in ("label_section", "policy_excerpt"):
        return {block.source_id: block.text}
    return {block.source_id: None} if hasattr(block, "source_id") else {}


def fixed_reply(reply_type: ReplyType) -> tuple[str, bool] | None:
    """The policy's fixed text and card for a reply type, if it has one."""
    for rule in policy.POLICY.values():
        if rule.text and reply_type in rule.reply_types:
            return rule.text, rule.handoff_offered
    fixed = policy.FIXED_REPLIES.get(reply_type)
    return (fixed.text, fixed.handoff_offered) if fixed else None


def allowed_sections(reply_type: ReplyType) -> set[LabelSection]:
    rules = [rule for rule in policy.POLICY.values() if reply_type in rule.reply_types]
    return set().union(*(rule.sections for rule in rules))


def test_one_example_per_reply_type():
    assert [path.stem for path in REPLIES] == sorted(reply_type.value for reply_type in ReplyType)


@pytest.mark.parametrize("path", REPLIES, ids=lambda path: path.stem)
def test_each_example_is_a_valid_reply_of_its_type(path):
    example = reply(path)
    assert example.reply_type == path.stem
    assert example.emergency is (example.reply_type is ReplyType.EMERGENCY)
    assert example.model_dump(mode="json") == load(path)


@pytest.mark.parametrize("path", REPLIES, ids=lambda path: path.stem)
def test_only_examples_with_a_pharmacist_card_have_an_offer_identity(path):
    example = reply(path)
    assert (example.offer_id is not None) is example.handoff_offered


@pytest.mark.parametrize("path", REPLIES, ids=lambda path: path.stem)
def test_every_fact_shown_is_its_cited_sources_text(path):
    example = reply(path)
    sources = {source.id: source for source in example.sources}
    cited: dict[str, str | None] = {}
    for block in example.blocks:
        cited |= citations(block)
    assert set(cited) == set(sources)
    for source_id, shown in cited.items():
        assert shown is None or shown == sources[source_id].text


def test_sources_hold_the_exact_text_or_the_lookup_time():
    for path in REPLIES:
        for source in reply(path).sources:
            live = source.id.startswith("api:")
            assert (source.text is None, source.retrieved_at is not None) == (live, live)


def test_the_examples_show_every_block_type():
    members = get_args(get_args(Block)[0])
    expected = {get_args(model.model_fields["type"].annotation)[0] for model in members}
    assert {block["type"] for path in REPLIES for block in load(path)["blocks"]} == expected


@pytest.mark.parametrize("path", REPLIES, ids=lambda path: path.stem)
def test_fixed_texts_and_the_card_follow_the_policy(path):
    example = reply(path)
    fixed = fixed_reply(example.reply_type)
    if fixed is None:  # a cited answer or the order form: no fixed text first, and no card
        assert not example.handoff_offered
        return
    text, handoff = fixed
    assert example.blocks[0].text == text
    assert example.handoff_offered is handoff


@pytest.mark.parametrize("path", REPLIES, ids=lambda path: path.stem)
def test_label_sections_shown_are_ones_the_policy_allows(path):
    example = reply(path)
    shown = {block.section for block in example.blocks if block.type == "label_section"}
    shown |= {
        row.section for block in example.blocks if block.type == "comparison" for row in block.rows
    }
    assert shown <= allowed_sections(example.reply_type)


def test_every_order_form_uses_the_policys_words():
    forms = [b for path in REPLIES for b in load(path)["blocks"] if b["type"] == "order_form"]
    assert len(forms) == 2
    assert all(form == ORDER_FORM for form in forms)


def test_handoff_examples_show_a_ticket_or_a_retry():
    created = HandoffReply.model_validate(load(EXAMPLES / "handoff" / "created.json"))
    failed = HandoffReply.model_validate(load(EXAMPLES / "handoff" / "failed.json"))
    assert created.text == policy.HANDOFF_CREATED_TEXT.format(ticket_id=created.ticket_id)
    assert (failed.ticket_id, failed.text) == (None, policy.HANDOFF_FAILED_TEXT)
