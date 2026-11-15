"""Validate chat boundaries and all nine block discriminators."""

import pytest
from pydantic import TypeAdapter, ValidationError

from contracts.chat import (
    Block,
    ChatReply,
    ChatRequest,
    HandoffReply,
    HandoffRequest,
    OrderFormRequest,
)

PRODUCT = dict(
    sku="MRD-TEST-001",
    name="Sample",
    **dict.fromkeys(
        ("active_ingredients", "uses", "warnings", "directions"), "Synthetic fixture text."
    ),
)
BLOCKS = [
    {"type": "text", "text": "Fixture text."},
    {
        "type": "label_section",
        "sku": "MRD-TEST-001",
        "name": "Sample",
        "section": "uses",
        "text": "Synthetic fixture text.",
        "source_id": "MRD-TEST-001#uses",
    },
    {"type": "comparison", "products": [PRODUCT, PRODUCT | {"sku": "MRD-TEST-002"}]},
    {
        "type": "product_list",
        "products": [
            {
                "sku": "MRD-TEST-001",
                "name": "Sample",
                "uses": "Synthetic fixture text.",
                "source_id": "MRD-TEST-001#uses",
            }
        ],
    },
    {
        "type": "availability",
        "availability": {
            "sku": "MRD-TEST-001",
            "stores": [{"store_id": "store-001", "store_name": "Sample store", "quantity": 3}],
        },
    },
    {
        "type": "store_info",
        "stores": [
            {
                "store_id": "store-001",
                "name": "Sample store",
                "address": "1 Sample Street",
                "phone": "202-555-0100",
                "hours": {"monday": "09:00-17:00"},
                "services": ["Pharmacist consultation"],
            }
        ],
    },
    {
        "type": "policy_excerpt",
        "source_id": "policies/delivery.md#area",
        "title": "Delivery area",
        "text": "Synthetic policy text.",
    },
    {
        "type": "order_status",
        "order": {"status": "shipped", "delivery_estimate": None, "item_count": 2},
    },
    {
        "type": "order_form",
        "text": "Fixture text.",
        "order_number_label": "Order number",
        "contact_label": "Email or phone",
        "submit_label": "Check order",
    },
]


@pytest.mark.parametrize("block", BLOCKS, ids=lambda block: block["type"])
def test_nine_block_types(block):
    assert TypeAdapter(Block).validate_python(block).model_dump(mode="json") == block


def test_reply_round_trip_and_source_metadata():
    reply = ChatReply(
        reply_type="label_sections",
        blocks=[BLOCKS[1]],
        handoff_offered=False,
        emergency=False,
        sources=[
            {
                "id": "MRD-TEST-001#uses",
                "title": "Sample uses",
                "text": "Synthetic fixture text.",
                "retrieved_at": None,
            }
        ],
    )
    assert ChatReply.model_validate_json(reply.model_dump_json()) == reply
    assert set(ChatReply.model_fields) == {
        "reply_type",
        "blocks",
        "sources",
        "handoff_offered",
        "emergency",
    }


def test_requests_and_confirmed_handoff():
    assert ChatRequest(session_id="s1", message="Hello").message == "Hello"
    assert (
        OrderFormRequest(
            session_id="s1", order_number="MRD-ORD-48213", contact="sample@example.com"
        ).session_id
        == "s1"
    )
    assert HandoffRequest(session_id="s1", confirmed=True).confirmed is True
    assert HandoffReply(ticket_id="ticket-001").ticket_id == "ticket-001"
    for payload in ({"session_id": "s1"}, {"session_id": "s1", "confirmed": False}):
        with pytest.raises(ValidationError):
            HandoffRequest(**payload)


def test_unknown_blocks_and_extra_order_data_are_rejected():
    for block in (
        {"type": "html", "text": "<script>"},
        BLOCKS[7] | {"order": BLOCKS[7]["order"] | {"address": "private"}},
    ):
        with pytest.raises(ValidationError):
            TypeAdapter(Block).validate_python(block)
