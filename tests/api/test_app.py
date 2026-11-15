"""Every API path over HTTP: order privacy, the lockout, stock, stores, tickets, the test header."""

import json
from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient

from api.app import app, create_app
from api.orders import status_of

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
ORDERS = {
    order["order_number"]: order
    for order in json.loads((DATA / "orders.json").read_text(encoding="utf-8"))
}
PRODUCTS = json.loads((ROOT / "catalog" / "products.json").read_text(encoding="utf-8"))
STOCK = json.loads((DATA / "stock.json").read_text(encoding="utf-8"))
STORES = yaml.safe_load((DATA / "stores.yaml").read_text(encoding="utf-8"))
STAFF = "test-staff-key"
NOT_FOUND = {"detail": "not_found"}
MARIA = ORDERS["MRD-ORD-48213"]["customer"]  # Maria Garcia
OTHER_MARIA = ORDERS["MRD-ORD-48231"]["customer"]  # another Maria Garcia, look-alike number
JAMES = ORDERS["MRD-ORD-48123"]["customer"]
SUMMARY = {
    "risk_label": "medical_advice",
    "urgency": "urgent",
    "customer_messages": ["Can I take this while pregnant?"],
    "product_mentions": ["Meridian All Day Allergy"],
    "assistant_replies": ["medical_advice"],
    "reason": "risk",
}
TICKET = {"idempotency_key": "session-0001:1", "summary": SUMMARY}


class Clock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def api(clock: Clock | None = None) -> TestClient:
    return TestClient(create_app(DATA, clock or Clock(), staff_key=STAFF))


def lookup(client: TestClient, order_number: str, contact: str):
    body = {"order_number": order_number, "contact": contact}
    return client.post("/v1/orders/lookup", json=body)


def test_a_verified_lookup_returns_status_estimate_and_item_count_only():
    response = lookup(api(), "MRD-ORD-48213", MARIA["email"])
    assert response.status_code == 200
    assert response.json() == status_of(ORDERS["MRD-ORD-48213"]).model_dump(mode="json")
    assert set(response.json()) == {"status", "delivery_estimate", "item_count"}


@pytest.mark.parametrize(
    "contact", [" Maria.Garcia@EXAMPLE.com ", "217.555.0110", "+1 (217) 555-0110", "2175550110"]
)
def test_the_email_ignores_case_and_spaces_and_the_phone_its_punctuation(contact):
    assert lookup(api(), "MRD-ORD-48213", contact).status_code == 200


FAILURES = {
    "unknown_order": ("MRD-ORD-99999", MARIA["email"]),
    "wrong_contact": ("MRD-ORD-48213", "someone@example.com"),
    "partial_contact": ("MRD-ORD-48213", "555-0110"),
    "another_customers_contact": ("MRD-ORD-48213", JAMES["email"]),
    "look_alike_number": ("MRD-ORD-48231", MARIA["email"]),
    "same_name_other_customer": ("MRD-ORD-48213", OTHER_MARIA["email"]),
}


@pytest.mark.parametrize(("order_number", "contact"), FAILURES.values(), ids=FAILURES)
def test_every_failure_gets_the_same_404(order_number, contact):
    response = lookup(api(), order_number, contact)
    assert (response.status_code, response.json()) == (404, NOT_FOUND)


def test_an_unknown_order_and_a_wrong_contact_answer_byte_for_byte_the_same():
    unknown = lookup(api(), "MRD-ORD-99999", MARIA["email"])
    wrong = lookup(api(), "MRD-ORD-48213", "someone@example.com")
    assert (unknown.status_code, unknown.content) == (wrong.status_code, wrong.content)
    assert unknown.headers["content-type"] == wrong.headers["content-type"]


def test_a_cancelled_order_reads_cancelled():
    cancelled = next(order for order in ORDERS.values() if order["status"] == "cancelled")
    response = lookup(api(), cancelled["order_number"], cancelled["customer"]["phone"])
    assert response.json() == {
        "status": "cancelled",
        "delivery_estimate": None,
        "item_count": sum(item["quantity"] for item in cancelled["items"]),
    }


def test_no_lookup_answer_holds_an_item_a_name_a_contact_or_an_address():
    names = {product["sku"]: product["name"] for product in PRODUCTS}
    client = api()
    for order in ORDERS.values():
        text = lookup(client, order["order_number"], order["customer"]["email"]).text
        private = [order["address"], *order["customer"].values()]
        private += [item["sku"] for item in order["items"]]
        private += [names[item["sku"]] for item in order["items"]]
        assert [value for value in private if value in text] == []


def test_six_wrong_numbers_for_one_contact_lock_out_even_the_right_one_for_ten_minutes():
    clock = Clock()
    client = api(clock)
    for n in range(6):
        assert lookup(client, f"MRD-ORD-1000{n}", MARIA["email"]).status_code == 404
    refused = lookup(client, "MRD-ORD-48213", MARIA["email"])
    assert (refused.status_code, refused.json()) == (404, NOT_FOUND)
    clock.now += 599
    assert lookup(client, "MRD-ORD-48213", MARIA["email"]).status_code == 404
    clock.now += 1  # ten minutes after the fifth failure
    assert lookup(client, "MRD-ORD-48213", MARIA["email"]).status_code == 200


def test_five_wrong_contacts_for_one_order_number_lock_that_number():
    clock = Clock()
    client = api(clock)
    for n in range(5):
        lookup(client, "MRD-ORD-48213", f"guess{n}@example.com")
    assert lookup(client, "MRD-ORD-48213", MARIA["email"]).status_code == 404
    clock.now += 600
    assert lookup(client, "MRD-ORD-48213", MARIA["email"]).status_code == 200


def test_availability_lists_stock_by_store_with_each_stores_name():
    sku = PRODUCTS[0]["sku"]
    names = {store["store_id"]: store["name"] for store in STORES}
    expected = [
        {
            "store_id": row["store_id"],
            "store_name": names[row["store_id"]],
            "quantity": row["quantity"],
        }
        for row in STOCK
        if row["sku"] == sku
    ]
    assert api().get(f"/v1/products/{sku}/availability").json() == {"sku": sku, "stores": expected}


@pytest.mark.parametrize("path", ["/v1/products/MRD-ALG-999/availability", "/v1/stores/store-999"])
def test_an_unknown_sku_or_store_gets_a_404_with_the_error_body(path):
    response = api().get(path)
    assert (response.status_code, response.json()) == (404, NOT_FOUND)


def test_the_stores_come_from_the_data_file():
    client = api()
    assert client.get("/v1/stores").json() == STORES
    assert client.get("/v1/stores/store-002").json() == STORES[1]


def test_the_same_key_returns_the_same_ticket_and_never_a_second():
    client = api()
    first = client.post("/v1/tickets", json=TICKET)
    changed = TICKET | {"summary": SUMMARY | {"urgency": "routine"}}
    again = client.post("/v1/tickets", json=changed)
    other = client.post("/v1/tickets", json=TICKET | {"idempotency_key": "session-0001:2"})
    assert (first.status_code, again.status_code) == (201, 201)
    assert first.json() == again.json() == {"ticket_id": "TCK-1001"}
    assert other.json() == {"ticket_id": "TCK-1002"}
    read = client.get("/v1/tickets/TCK-1001", headers={"X-Staff-Key": STAFF}).json()
    assert read == {"ticket_id": "TCK-1001", "summary": SUMMARY}


@pytest.mark.parametrize(
    "body",
    [
        {"summary": SUMMARY},
        {"idempotency_key": "", "summary": SUMMARY},
        {"idempotency_key": "key", "summary": {"risk_label": "none"}},
        {"idempotency_key": "key", "summary": "free text"},
    ],
)
def test_a_ticket_needs_a_key_and_a_summary_that_passes_its_schema(body):
    assert api().post("/v1/tickets", json=body).status_code == 422


@pytest.mark.parametrize("headers", [{}, {"X-Staff-Key": "wrong"}, {"X-Staff-Key": ""}])
def test_reading_a_ticket_without_the_staff_key_is_401(headers):
    client = api()
    client.post("/v1/tickets", json=TICKET)
    response = client.get("/v1/tickets/TCK-1001", headers=headers)
    assert (response.status_code, response.json()) == (401, {"detail": "unauthorized"})


def test_staff_can_read_a_ticket_and_an_unknown_ticket_is_404():
    client = api()
    client.post("/v1/tickets", json=TICKET)
    assert client.get("/v1/tickets/TCK-1001", headers={"X-Staff-Key": STAFF}).status_code == 200
    unknown = client.get("/v1/tickets/TCK-9999", headers={"X-Staff-Key": STAFF})
    assert (unknown.status_code, unknown.json()) == (404, NOT_FOUND)


ENDPOINTS = [
    ("post", "/v1/orders/lookup"),
    ("get", "/v1/products/{sku}/availability"),
    ("get", "/v1/stores"),
    ("get", "/v1/stores/{store_id}"),
    ("post", "/v1/tickets"),
    ("get", "/v1/tickets/{ticket_id}"),
]
CALLS = [
    ("post", "/v1/orders/lookup", {"order_number": "MRD-ORD-48213", "contact": MARIA["email"]}),
    ("get", "/v1/products/MRD-ALG-012/availability", None),
    ("get", "/v1/stores", None),
    ("get", "/v1/stores/store-001", None),
    ("post", "/v1/tickets", TICKET),
    ("get", "/v1/tickets/TCK-1001", None),
]


@pytest.mark.parametrize(("method", "path", "body"), CALLS, ids=[c[1] for c in CALLS])
def test_the_timeout_header_makes_any_endpoint_answer_504_before_it_runs(method, path, body):
    client = api()
    headers = {"X-Meridian-Test": "timeout", "X-Staff-Key": STAFF}
    response = client.request(method, path, json=body, headers=headers)
    assert (response.status_code, response.json()) == (504, {"detail": "timeout"})
    assert client.app.state.desks.tickets.count() == 0


def test_the_spec_declares_six_typed_endpoints_with_504_and_no_501():
    spec = app.openapi()
    operations = [(method, path) for path, methods in spec["paths"].items() for method in methods]
    assert sorted(operations) == sorted(ENDPOINTS)
    for path, methods in spec["paths"].items():
        for operation in methods.values():
            assert "504" in operation["responses"] and "501" not in operation["responses"], path
