"""The mock Meridian API: HTTP routes over the order, product, store and ticket modules.

The OpenAPI spec is frozen in contracts/meridian-api.json, so every route keeps its function
name, docstring and decorator. `create_app` builds the modules from the data files, the clock
and the staff key, so a test passes its own; `app` is what uvicorn and the snapshot use. The
test header `X-Meridian-Test: timeout` makes any endpoint answer 504 at once.
"""

import hmac
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse

from api import settings
from api.orders import OrderDesk
from api.products import StockRoom
from api.stores import load_stores
from api.tickets import TicketDesk
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


@dataclass(frozen=True)
class Desks:
    orders: OrderDesk
    stock: StockRoom
    stores: dict[str, StoreInfo]
    tickets: TicketDesk
    staff_key: str


def desks(request: Request) -> Desks:
    return request.app.state.desks


Service = Annotated[Desks, Depends(desks)]
router = APIRouter()


def not_found() -> HTTPException:
    return HTTPException(status_code=404, detail="not_found")


@router.post("/v1/orders/lookup", response_model=OrderStatus, responses={404: {"model": APIError}})
def lookup_order(
    request: OrderLookupRequest, service: Service, test: TestHeader = None
) -> OrderStatus:
    """Status, delivery estimate and item count, only when the order number and the email or
    phone both match one order. Every failure, including a lockout after five failed tries
    for one contact or one order number, gets the same 404 status and body."""
    status = service.orders.lookup(request.order_number, request.contact)
    if status is None:
        raise not_found()
    return status


@router.get(
    "/v1/products/{sku}/availability",
    response_model=Availability,
    responses={404: {"model": APIError}},
)
def get_availability(sku: str, service: Service, test: TestHeader = None) -> Availability:
    """Stock of one product at each store. An unknown SKU gets a 404."""
    availability = service.stock.availability(sku)
    if availability is None:
        raise not_found()
    return availability


@router.get("/v1/stores", response_model=list[StoreInfo])
def list_stores(service: Service, test: TestHeader = None) -> list[StoreInfo]:
    """Every store's address, phone, hours by weekday and services."""
    return list(service.stores.values())


@router.get("/v1/stores/{store_id}", response_model=StoreInfo, responses={404: {"model": APIError}})
def get_store(store_id: str, service: Service, test: TestHeader = None) -> StoreInfo:
    """One store's address, phone, hours by weekday and services. An unknown store gets a 404."""
    store = service.stores.get(store_id)
    if store is None:
        raise not_found()
    return store


@router.post("/v1/tickets", response_model=TicketCreated, status_code=201)
def create_ticket(
    request: TicketCreateRequest, service: Service, test: TestHeader = None
) -> TicketCreated:
    """Create a pharmacist ticket. The same idempotency key returns the same ticket, with the
    same 201, and never creates a second one."""
    return service.tickets.create(request)


@router.get(
    "/v1/tickets/{ticket_id}",
    response_model=TicketRecord,
    responses={401: {"model": APIError}, 404: {"model": APIError}},
)
def get_ticket(
    ticket_id: str, service: Service, staff_key: StaffHeader = None, test: TestHeader = None
) -> TicketRecord:
    """Read a ticket back. Without the right X-Staff-Key header the answer is 401."""
    if not hmac.compare_digest((staff_key or "").encode(), service.staff_key.encode()):
        raise HTTPException(status_code=401, detail="unauthorized")
    ticket = service.tickets.get(ticket_id)
    if ticket is None:
        raise not_found()
    return ticket


async def answer_test_timeout(request: Request, call_next):
    """`X-Meridian-Test: timeout` makes any endpoint answer 504 before it runs."""
    if request.headers.get("X-Meridian-Test", "").strip().lower() == "timeout":
        return JSONResponse(status_code=504, content={"detail": "timeout"})
    return await call_next(request)


def create_app(
    data: Path = settings.DATA,
    clock: Callable[[], float] = time.monotonic,
    staff_key: str | None = None,
) -> FastAPI:
    stores = load_stores(data / "stores.yaml")
    app = FastAPI(title="Meridian API", version="0.1.0", responses=TIMEOUT)
    app.state.desks = Desks(
        orders=OrderDesk.from_file(data / "orders.json", clock),
        stock=StockRoom.from_file(data / "stock.json", stores),
        stores=stores,
        tickets=TicketDesk(),
        staff_key=settings.staff_key() if staff_key is None else staff_key,
    )
    app.middleware("http")(answer_test_timeout)
    app.include_router(router)
    return app


app = create_app()
