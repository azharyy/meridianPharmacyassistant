"""Evaluation API traces retain actual tools and response facts, never private form inputs."""

import httpx
import pytest

from assistant import api_client
from contracts.api import OrderLookupRequest
from eval.tracing import capture_api

STATUS = {"status": "shipped", "delivery_estimate": "2026-11-17", "item_count": 2}
STORE = {
    "store_id": "store-001",
    "name": "Downtown",
    "address": "A public store address",
    "phone": "(217) 555-0142",
    "hours": {"Sunday": "Closed"},
    "services": [],
}
STOCK = {
    "sku": "MRD-ALG-012",
    "stores": [{"store_id": STORE["store_id"], "store_name": STORE["name"], "quantity": 12}],
}


@pytest.mark.parametrize(
    ("method", "path", "body", "tool", "evidence"),
    [
        ("POST", "/v1/orders/lookup", STATUS, "lookup_order", {"api:orders": STATUS}),
        ("GET", "/v1/stores", [STORE], "get_store_info", {"api:stores/store-001": STORE}),
        ("GET", "/v1/stores/store-001", STORE, "get_store_info", {"api:stores/store-001": STORE}),
        (
            "GET",
            "/v1/products/MRD-ALG-012/availability",
            STOCK,
            "check_availability",
            {"api:availability/MRD-ALG-012": STOCK},
        ),
        ("POST", "/v1/tickets", {"ticket_id": "TCK-1001"}, "create_ticket", {}),
    ],
)
def test_successful_tools_capture_only_their_validated_response(method, path, body, tool, evidence):
    http = httpx.Client(
        base_url="http://api.test",
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json=body)),
    )
    with capture_api(http) as capture:
        http.request(method, path, json={"contact": "private@example.com"})
    assert capture.calls == [tool] and capture.evidence == evidence
    assert "private@example.com" not in str(capture)


@pytest.mark.parametrize(
    "body",
    [
        {**STATUS, "address": "Private customer address"},
        {**STATUS, "items": ["Private medicine"]},
        {"unexpected": "Private customer data"},
    ],
)
def test_invalid_order_responses_never_enter_the_recorded_evidence(body):
    http = httpx.Client(
        base_url="http://api.test",
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json=body)),
    )
    with capture_api(http) as capture:
        http.post("/v1/orders/lookup", json={"contact": "private@example.com"})
    assert capture.calls == ["lookup_order"] and capture.evidence == {}
    assert "Private" not in str(capture) and "private@example.com" not in str(capture)


def test_failed_reads_record_both_real_attempts_without_inventing_evidence():
    http = httpx.Client(
        base_url="http://api.test",
        transport=httpx.MockTransport(lambda request: httpx.Response(504)),
    )
    with capture_api(http) as capture:
        with pytest.raises(api_client.APIUnavailable):
            api_client.get_availability(http, "MRD-ALG-012")
    assert capture.calls == ["check_availability"] * 2 and capture.evidence == {}


def test_existing_hooks_survive_and_are_restored_even_when_a_request_fails():
    calls = []

    def fail(request):
        raise httpx.ReadTimeout("timeout", request=request)

    http = httpx.Client(
        base_url="http://api.test",
        transport=httpx.MockTransport(fail),
        event_hooks={"request": [lambda request: calls.append("existing")]},
    )
    before = {kind: list(hooks) for kind, hooks in http.event_hooks.items()}
    with pytest.raises(httpx.ReadTimeout), capture_api(http) as capture:
        http.post(
            "/v1/orders/lookup",
            json=OrderLookupRequest(
                order_number="MRD-ORD-48213", contact="private@example.com"
            ).model_dump(),
        )
    assert http.event_hooks == before and calls == ["existing"]
    assert capture.calls == ["lookup_order"] and capture.evidence == {}
