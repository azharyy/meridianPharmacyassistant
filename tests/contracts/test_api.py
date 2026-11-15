"""Validate public API data and the limited order response."""

import pytest
from pydantic import ValidationError

from contracts.api import (
    OrderLookupRequest,
    OrderStatus,
    StoreStock,
    TicketCreateRequest,
    TicketSummary,
)


def test_order_status_has_only_public_fields():
    assert set(OrderStatus.model_fields) == {"status", "delivery_estimate", "item_count"}
    order = {"status": "shipped", "delivery_estimate": "2026-11-16", "item_count": 2}
    assert OrderStatus(**order).model_dump(mode="json") == order
    for field in ("items", "address", "contact", "order_number"):
        with pytest.raises(ValidationError, match="extra_forbidden"):
            OrderStatus(**order, **{field: "private"})


def test_counts_cannot_be_negative():
    with pytest.raises(ValidationError):
        OrderStatus(status="cancelled", delivery_estimate=None, item_count=-1)
    with pytest.raises(ValidationError):
        StoreStock(store_id="store-001", store_name="Meridian Downtown", quantity=-1)


def test_stock_names_the_store():
    stock = StoreStock(store_id="store-001", store_name="Meridian Downtown", quantity=0)
    assert stock.store_name == "Meridian Downtown"
    with pytest.raises(ValidationError, match="store_name"):
        StoreStock(store_id="store-001", quantity=0)


@pytest.mark.parametrize("field,limit", [("order_number", 64), ("contact", 254)])
def test_order_lookup_input_is_bounded(field, limit):
    request = {"order_number": "MRD-ORD-48213", "contact": "sample@example.com"}
    assert OrderLookupRequest(**(request | {field: "x" * limit}))
    with pytest.raises(ValidationError):
        OrderLookupRequest(**(request | {field: "x" * (limit + 1)}))


def test_ticket_summary_is_structured_and_rejects_private_extra_fields():
    summary = {
        "risk_label": "medical_advice",
        "urgency": "urgent",
        "customer_messages": ["[EMAIL] needs a pharmacist."],
        "product_mentions": ["Meridian Allergy Relief"],
        "assistant_replies": ["I cannot advise on a personal medical situation."],
        "reason": "risk",
    }
    ticket = TicketCreateRequest(idempotency_key="session-offer", summary=summary)
    assert ticket.summary.model_dump(mode="json") == summary
    for field in ("contact", "order_number", "address"):
        with pytest.raises(ValidationError, match="extra_forbidden"):
            TicketSummary(**summary, **{field: "private"})
    with pytest.raises(ValidationError):
        TicketCreateRequest(idempotency_key="session-offer", summary="unstructured text")
