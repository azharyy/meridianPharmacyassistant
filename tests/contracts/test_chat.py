"""Validate chat boundaries, the nine block types and the forms a source may take."""

from typing import get_args

import pytest
from pydantic import TypeAdapter, ValidationError

from contracts.chat import (
    Block,
    ChatReply,
    ChatRequest,
    HandoffReply,
    HandoffRequest,
    OrderFormRequest,
    Source,
)

SESSION = "session-0001"
OFFER_ID = "4a9be9da-e6f6-4bda-a66f-6fa7aa514a3f"
OFFER_BOUNDARIES = [
    (
        ChatReply,
        {
            "reply_type": "fallback",
            "blocks": [],
            "sources": [],
            "handoff_offered": True,
            "emergency": False,
        },
    ),
    (HandoffRequest, {"session_id": SESSION, "confirmed": True}),
]
DIRECTIONS = "Synthetic directions text."
BLOCKS = [
    {"type": "text", "text": "Fixture text."},
    {
        "type": "label_section",
        "sku": "MRD-ALG-012",
        "name": "Sample",
        "section": "directions",
        "title": "Directions",
        "text": DIRECTIONS,
        "source_id": "MRD-ALG-012#directions",
    },
    {
        "type": "comparison",
        "products": [
            {"sku": "MRD-ALG-012", "name": "Sample A"},
            {"sku": "MRD-ALG-013", "name": "Sample B"},
        ],
        "rows": [{"section": "uses", "title": "Uses", "texts": ["Uses of A.", "Uses of B."]}],
    },
    {
        "type": "product_list",
        "products": [
            {
                "sku": "MRD-ALG-012",
                "name": "Sample",
                "uses": "Uses of A.",
                "source_id": "MRD-ALG-012#uses",
            }
        ],
    },
    {
        "type": "availability",
        "sku": "MRD-ALG-012",
        "name": "Sample",
        "stores": [
            {
                "store_id": "store-001",
                "store_name": "Sample store",
                "quantity": 3,
                "text": "In stock (3)",
            }
        ],
        "source_id": "api:availability/MRD-ALG-012",
    },
    {
        "type": "store_info",
        "store": {
            "store_id": "store-001",
            "name": "Sample store",
            "address": "1 Sample Street",
            "phone": "202-555-0100",
            "hours": {"Monday": "09:00-17:00"},
            "services": ["Pharmacist consultation"],
        },
        "source_id": "api:stores/store-001",
    },
    {
        "type": "policy_excerpt",
        "source_id": "policies/delivery.md#delivery-area",
        "title": "Delivery area",
        "text": "Synthetic policy text.",
    },
    {
        "type": "order_status",
        "text": "Your order has shipped.",
        "order": {"status": "shipped", "delivery_estimate": None, "item_count": 2},
        "source_id": "api:orders",
    },
    {
        "type": "order_form",
        "text": "Fixture text.",
        "order_number_label": "Order number",
        "contact_label": "Email or phone",
        "submit_label": "Check order",
    },
]


def block_types() -> set[str]:
    members = get_args(get_args(Block)[0])
    return {get_args(model.model_fields["type"].annotation)[0] for model in members}


def test_the_fixtures_cover_all_nine_block_types():
    assert len(block_types()) == 9
    assert {block["type"] for block in BLOCKS} == block_types()


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
                "id": "MRD-ALG-012#directions",
                "title": "Sample: Directions",
                "text": DIRECTIONS,
                "retrieved_at": None,
            },
            {
                "id": "api:orders",
                "title": "Order lookup",
                "text": None,
                "retrieved_at": "2026-11-15T10:42:00Z",
            },
        ],
    )
    assert ChatReply.model_validate_json(reply.model_dump_json()) == reply
    assert set(ChatReply.model_fields) == {
        "reply_type",
        "blocks",
        "sources",
        "handoff_offered",
        "emergency",
        "offer_id",
    }


@pytest.mark.parametrize(
    "source_id",
    [
        "MRD-ALG-012#directions",
        "policies/delivery.md#delivery-area",
        "policies/pharmacist-services.md#consultations",
        "api:stores/store-001",
        "api:availability/MRD-ALG-012",
        "api:orders",
    ],
)
def test_source_ids_take_the_plans_three_forms(source_id):
    assert Source(id=source_id, title="Title", text=None, retrieved_at=None).id == source_id


@pytest.mark.parametrize(
    "source_id",
    [
        "MRD-ALG-012#dosage",
        "MRD-ALG-12#uses",
        "MRD-ALG-012",
        "policies/delivery#delivery-area",
        "policies/../secrets.md#area",
        "api:orders/MRD-ORD-48213",
        "https://example.com/label",
    ],
)
def test_other_source_ids_are_rejected(source_id):
    with pytest.raises(ValidationError):
        Source(id=source_id, title="Title", text=None, retrieved_at=None)


def test_requests_and_confirmed_handoff():
    assert ChatRequest(session_id=SESSION, message="Hello").store_id is None
    request = ChatRequest(session_id=SESSION, message="Hello", store_id="store-001")
    assert request.store_id == "store-001"
    form = OrderFormRequest(
        session_id=SESSION, order_number="MRD-ORD-48213", contact="sample@example.com"
    )
    assert form.contact == "sample@example.com"
    assert HandoffRequest(session_id=SESSION, confirmed=True).confirmed is True
    for payload in ({"session_id": SESSION}, {"session_id": SESSION, "confirmed": False}):
        with pytest.raises(ValidationError):
            HandoffRequest(**payload)


def test_handoff_reply_says_whether_the_ticket_was_created():
    created = HandoffReply(ticket_id="TCK-1042", text="Your request number is TCK-1042.")
    failed = HandoffReply(ticket_id=None, text="Your request didn't go through.")
    assert (created.ticket_id, failed.ticket_id) == ("TCK-1042", None)
    with pytest.raises(ValidationError, match="text"):
        HandoffReply(ticket_id="TCK-1042")


@pytest.mark.parametrize("model,payload", OFFER_BOUNDARIES)
@pytest.mark.parametrize("offer_id", [OFFER_ID, None])
def test_offer_identity_round_trips_on_both_http_boundaries(model, payload, offer_id):
    value = model(**payload, offer_id=offer_id)
    assert value.offer_id == offer_id
    assert value.model_dump(mode="json")["offer_id"] == offer_id
    assert model.model_validate_json(value.model_dump_json()) == value


@pytest.mark.parametrize("model,payload", OFFER_BOUNDARIES)
def test_omitted_offer_identity_remains_backward_compatible(model, payload):
    assert model(**payload).offer_id is None


@pytest.mark.parametrize("model,payload", OFFER_BOUNDARIES)
@pytest.mark.parametrize(
    "offer_id",
    [
        "",
        "card-1",
        OFFER_ID.upper(),
        OFFER_ID.replace("-4bda-", "-3bda-"),
        OFFER_ID.replace("-a66f-", "-766f-"),
        1,
        True,
        {},
        [],
    ],
)
def test_offer_identity_rejects_noncanonical_uuid4_and_wrong_types(model, payload, offer_id):
    with pytest.raises(ValidationError):
        model(**payload, offer_id=offer_id)


@pytest.mark.parametrize("session_id", ["s1", "sample@example.com", "a" * 65, "with spaces"])
def test_session_id_is_an_opaque_token(session_id):
    with pytest.raises(ValidationError):
        ChatRequest(session_id=session_id, message="Hello")


@pytest.mark.parametrize(
    "changes", [{"message": ""}, {"message": "x" * 2001}, {"store_id": "Store 1"}]
)
def test_chat_input_is_bounded(changes):
    request = {"session_id": SESSION, "message": "x" * 2000}
    assert ChatRequest(**request)
    with pytest.raises(ValidationError):
        ChatRequest(**(request | changes))


@pytest.mark.parametrize(
    "changes",
    [
        {"products": BLOCKS[2]["products"][:1]},
        {"rows": [{"section": "uses", "title": "Uses", "texts": ["Only one product."]}]},
        {"rows": []},
    ],
)
def test_comparison_is_two_products_side_by_side(changes):
    with pytest.raises(ValidationError):
        TypeAdapter(Block).validate_python(BLOCKS[2] | changes)


def test_unknown_blocks_and_extra_order_data_are_rejected():
    for block in (
        {"type": "html", "text": "<script>"},
        BLOCKS[7] | {"order": BLOCKS[7]["order"] | {"address": "private"}},
    ):
        with pytest.raises(ValidationError):
            TypeAdapter(Block).validate_python(block)
