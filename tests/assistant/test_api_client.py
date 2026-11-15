"""The API client: one typed call per endpoint; reads are retried once, nothing else is."""

import json
from pathlib import Path

import httpx
import pytest

from assistant import api_client
from assistant.api_client import APIUnavailable
from assistant.settings import load_settings
from contracts.api import (
    Availability,
    OrderLookupRequest,
    OrderStatus,
    StoreInfo,
    TicketCreated,
    TicketCreateRequest,
)

ASSISTANT = Path(__file__).resolve().parents[2] / "assistant"
STATUS = {"status": "shipped", "delivery_estimate": "2026-11-17", "item_count": 2}
AVAILABILITY = {
    "sku": "MRD-ALG-012",
    "stores": [{"store_id": "store-001", "store_name": "Meridian Downtown", "quantity": 12}],
}
STORE = {
    "store_id": "store-001",
    "name": "Meridian Downtown",
    "address": "120 Harbor Street, Springfield",
    "phone": "(217) 555-0142",
    "hours": {"Monday": "08:00-21:00"},
    "services": ["Pharmacist consultation"],
}
LOOKUP = OrderLookupRequest(order_number="MRD-ORD-48213", contact="sam@example.com")
TICKET = TicketCreateRequest(
    idempotency_key="session-0001:1",
    summary={
        "risk_label": "medical_advice",
        "urgency": "urgent",
        "customer_messages": ["Can I take this while pregnant?"],
        "product_mentions": ["Meridian All Day Allergy"],
        "assistant_replies": ["medical_advice"],
        "reason": "risk",
    },
)
NOT_FOUND = httpx.Response(404, json={"detail": "not_found"})
TIMED_OUT = httpx.Response(504, json={"detail": "timeout"})


def api(*answers: httpx.Response | str) -> tuple[httpx.Client, list[httpx.Request]]:
    """A client whose requests are answered in turn; "drop" raises a connection error."""
    seen: list[httpx.Request] = []
    queue = list(answers)

    def handle(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        answer = queue.pop(0)
        if answer == "drop":
            raise httpx.ConnectError("refused", request=request)
        return answer

    return httpx.Client(base_url="http://api.test", transport=httpx.MockTransport(handle)), seen


def test_the_order_lookup_posts_the_form_and_returns_the_status_only():
    http, seen = api(httpx.Response(200, json=STATUS))
    assert api_client.lookup_order(http, LOOKUP) == OrderStatus(**STATUS)
    assert (seen[0].method, seen[0].url.path) == ("POST", "/v1/orders/lookup")
    assert json.loads(seen[0].content) == LOOKUP.model_dump()


def test_any_lookup_mismatch_is_none():
    http, _ = api(NOT_FOUND)
    assert api_client.lookup_order(http, LOOKUP) is None


@pytest.mark.parametrize(
    "call",
    [
        lambda http: api_client.lookup_order(http, LOOKUP),
        lambda http: api_client.create_ticket(http, TICKET),
    ],
    ids=["order_lookup", "ticket"],
)
def test_lookups_and_tickets_are_not_retried(call):
    http, seen = api(TIMED_OUT)
    with pytest.raises(APIUnavailable):
        call(http)
    assert len(seen) == 1


@pytest.mark.parametrize("first", [TIMED_OUT, "drop"], ids=["504", "connection"])
def test_reads_are_retried_once(first):
    http, seen = api(first, httpx.Response(200, json=AVAILABILITY))
    assert api_client.get_availability(http, "MRD-ALG-012") == Availability(**AVAILABILITY)
    assert [request.url.path for request in seen] == ["/v1/products/MRD-ALG-012/availability"] * 2


def test_reads_fail_after_one_retry():
    http, seen = api(TIMED_OUT, TIMED_OUT)
    with pytest.raises(APIUnavailable):
        api_client.list_stores(http)
    assert len(seen) == 2


def test_stores_and_unknown_skus_and_stores():
    http, _ = api(
        httpx.Response(200, json=[STORE]), httpx.Response(200, json=STORE), NOT_FOUND, NOT_FOUND
    )
    assert api_client.list_stores(http) == [StoreInfo(**STORE)]
    assert api_client.get_store(http, "store-001") == StoreInfo(**STORE)
    assert api_client.get_store(http, "store-999") is None
    assert api_client.get_availability(http, "MRD-ALG-999") is None


def test_a_ticket_is_created_with_its_idempotency_key():
    http, seen = api(httpx.Response(201, json={"ticket_id": "TCK-1042"}))
    assert api_client.create_ticket(http, TICKET) == TicketCreated(ticket_id="TCK-1042")
    assert json.loads(seen[0].content)["idempotency_key"] == "session-0001:1"


def test_a_value_cannot_change_the_path():
    http, seen = api(NOT_FOUND)
    api_client.get_availability(http, "../orders")
    assert seen[0].url.raw_path == b"/v1/products/..%2Forders/availability"


def test_an_answer_that_breaks_the_contract_is_unavailable():
    http, _ = api(httpx.Response(200, json={**STATUS, "address": "1 Private Lane"}))
    with pytest.raises(APIUnavailable):
        api_client.lookup_order(http, LOOKUP)


def test_connect_uses_the_api_url_from_settings():
    http = api_client.connect(load_settings({"MERIDIAN_API_URL": "http://api.example:9000"}))
    assert str(http.base_url).startswith("http://api.example:9000")


def test_only_the_api_client_calls_the_api():
    callers = [
        path.name
        for path in ASSISTANT.rglob("*.py")
        if path.name != "api_client.py" and "/v1/" in path.read_text(encoding="utf-8")
    ]
    assert not callers
