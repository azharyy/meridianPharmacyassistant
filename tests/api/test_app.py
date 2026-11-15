"""Check all API stubs and the declared request, response and header shapes."""

import pytest
from fastapi.testclient import TestClient

from api.app import app

SUMMARY = {
    "risk_label": "none",
    "urgency": "routine",
    "customer_messages": ["Please let me talk to a pharmacist."],
    "product_mentions": [],
    "assistant_replies": [],
    "reason": "customer_requested",
}
ENDPOINTS = [
    ("post", "/v1/orders/lookup", "OrderStatus", {404}),
    ("get", "/v1/products/{sku}/availability", "Availability", {404}),
    ("get", "/v1/stores", "StoreInfo", set()),
    ("get", "/v1/stores/{store_id}", "StoreInfo", {404}),
    ("post", "/v1/tickets", "TicketCreated", set()),
    ("get", "/v1/tickets/{ticket_id}", "TicketRecord", {401, 404}),
]
CLIENT = TestClient(app)


@pytest.mark.parametrize("method,path,model,errors", ENDPOINTS)
def test_every_stub_returns_typed_501(method, path, model, errors):
    body = None
    if path == "/v1/orders/lookup":
        body = {"order_number": "MRD-ORD-48213", "contact": "sample@example.test"}
    elif path == "/v1/tickets":
        body = {"idempotency_key": "session-1-offer-1", "summary": SUMMARY}
    url = path.format(sku="MRD-ALG-012", store_id="store-001", ticket_id="ticket-001")
    response = CLIENT.request(method, url, json=body, headers={"X-Meridian-Test": "timeout"})
    assert response.status_code == 501
    assert response.json() == {"detail": "not_implemented"}


@pytest.mark.parametrize("method,path,model,errors", ENDPOINTS)
def test_openapi_declares_typed_success_errors_and_headers(method, path, model, errors):
    operation = app.openapi()["paths"][path][method]
    status = "201" if model == "TicketCreated" else "200"
    schema = operation["responses"][status]["content"]["application/json"]["schema"]
    if path == "/v1/stores":
        assert schema["type"] == "array"
        schema = schema["items"]
    assert schema["$ref"] == f"#/components/schemas/{model}"
    for code in errors | {504}:
        error = operation["responses"][str(code)]["content"]["application/json"]["schema"]
        assert error["$ref"] == "#/components/schemas/APIError"
    # The spec documents the finished API, so the stubs' 501 must not be in it.
    assert "501" not in operation["responses"]
    headers = {p["name"]: p for p in operation["parameters"] if p["in"] == "header"}
    assert headers["X-Meridian-Test"]["required"] is False
    if model == "TicketRecord":
        assert headers["X-Staff-Key"]["required"] is False


@pytest.mark.parametrize(
    "path,body",
    [
        ("/v1/orders/lookup", {"order_number": "MRD-ORD-48213"}),
        ("/v1/orders/lookup", {"order_number": "MRD-ORD-48213", "contact": ""}),
        ("/v1/tickets", {"summary": SUMMARY}),
        ("/v1/tickets", {"idempotency_key": "key", "summary": {}}),
        ("/v1/tickets", {"idempotency_key": "", "summary": SUMMARY}),
    ],
)
def test_malformed_requests_are_rejected(path, body):
    assert CLIENT.post(path, json=body).status_code == 422


def test_openapi_declares_only_the_six_endpoints_and_typed_bodies():
    spec = app.openapi()
    assert {(method, path) for path, methods in spec["paths"].items() for method in methods} == {
        (method, path) for method, path, _, _ in ENDPOINTS
    }
    for path, model in (
        ("/v1/orders/lookup", "OrderLookupRequest"),
        ("/v1/tickets", "TicketCreateRequest"),
    ):
        body = spec["paths"][path]["post"]["requestBody"]
        assert body["required"] is True
        assert (
            body["content"]["application/json"]["schema"]["$ref"] == f"#/components/schemas/{model}"
        )
