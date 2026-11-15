"""Declare the mock Meridian API endpoints as typed stubs that answer 501 until issue 4.

The OpenAPI spec is frozen in contracts/meridian-api.json. It documents what the finished
API returns, so the stubs' 501 is not in it. Issue 4 replaces each body and keeps every
name, docstring and decorator, so the spec stays identical.
"""

from typing import Annotated

from fastapi import FastAPI, Header, HTTPException

from contracts.api import (
    APIError,
    Availability,
    OrderLookupRequest,
    OrderStatus,
    StoreInfo,
    TicketCreated,
    TicketCreateRequest,
    TicketRecord,
)

TIMEOUT = {504: {"model": APIError, "description": "The test header asked for a timeout"}}
app = FastAPI(title="Meridian API", version="0.1.0", responses=TIMEOUT)
TestHeader = Annotated[
    str | None,
    Header(
        alias="X-Meridian-Test",
        description="Test only. `timeout` makes the endpoint answer 504 at once.",
    ),
]
StaffHeader = Annotated[
    str | None, Header(alias="X-Staff-Key", description="Staff only. Needed to read a ticket.")
]


def not_implemented() -> HTTPException:
    return HTTPException(status_code=501, detail="not_implemented")


@app.post("/v1/orders/lookup", response_model=OrderStatus, responses={404: {"model": APIError}})
def lookup_order(request: OrderLookupRequest, test: TestHeader = None) -> OrderStatus:
    """Status, delivery estimate and item count, only when the order number and the email or
    phone both match one order. Every failure, including a lockout after five failed tries
    for one contact or one order number, gets the same 404 status and body."""
    raise not_implemented()


@app.get(
    "/v1/products/{sku}/availability",
    response_model=Availability,
    responses={404: {"model": APIError}},
)
def get_availability(sku: str, test: TestHeader = None) -> Availability:
    """Stock of one product at each store. An unknown SKU gets a 404."""
    raise not_implemented()


@app.get("/v1/stores", response_model=list[StoreInfo])
def list_stores(test: TestHeader = None) -> list[StoreInfo]:
    """Every store's address, phone, hours by weekday and services."""
    raise not_implemented()


@app.get("/v1/stores/{store_id}", response_model=StoreInfo, responses={404: {"model": APIError}})
def get_store(store_id: str, test: TestHeader = None) -> StoreInfo:
    """One store's address, phone, hours by weekday and services. An unknown store gets a 404."""
    raise not_implemented()


@app.post("/v1/tickets", response_model=TicketCreated, status_code=201)
def create_ticket(request: TicketCreateRequest, test: TestHeader = None) -> TicketCreated:
    """Create a pharmacist ticket. The same idempotency key returns the same ticket, with the
    same 201, and never creates a second one."""
    raise not_implemented()


@app.get(
    "/v1/tickets/{ticket_id}",
    response_model=TicketRecord,
    responses={401: {"model": APIError}, 404: {"model": APIError}},
)
def get_ticket(
    ticket_id: str, staff_key: StaffHeader = None, test: TestHeader = None
) -> TicketRecord:
    """Read a ticket back. Without the right X-Staff-Key header the answer is 401."""
    raise not_implemented()
