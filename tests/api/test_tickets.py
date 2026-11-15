"""One ticket per idempotency key; a repeat returns the original ticket."""

from api.tickets import TicketDesk
from contracts.api import TicketCreateRequest

SUMMARY = {
    "risk_label": "none",
    "urgency": "routine",
    "customer_messages": ["Please let me talk to a pharmacist."],
    "product_mentions": [],
    "assistant_replies": [],
    "reason": "customer_requested",
}


def request(key: str, **summary) -> TicketCreateRequest:
    return TicketCreateRequest(idempotency_key=key, summary=SUMMARY | summary)


def test_the_same_key_returns_the_first_ticket_even_with_another_summary():
    desk = TicketDesk()
    first = desk.create(request("session-0001:1"))
    again = desk.create(request("session-0001:1", urgency="urgent"))
    assert first == again
    assert desk.count() == 1
    assert desk.get(first.ticket_id).summary.urgency == "routine"


def test_new_keys_get_new_tickets_and_unknown_ids_are_none():
    desk = TicketDesk()
    ids = [desk.create(request(f"session-0001:{n}")).ticket_id for n in (1, 2)]
    assert ids == ["TCK-1001", "TCK-1002"]
    assert desk.get("TCK-9999") is None
