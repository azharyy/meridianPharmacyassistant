"""Declare the mock Meridian API endpoints as typed 501 stubs."""

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

app = FastAPI(title="Meridian API", version="0.1.0", responses={501: {"model": APIError}})
TestHeader = Annotated[str | None, Header(alias="X-Meridian-Test")]
StaffHeader = Annotated[str | None, Header(alias="X-Staff-Key")]


@app.post("/v1/orders/lookup", response_model=OrderStatus, responses={404: {"model": APIError}})
def lookup_order(request: OrderLookupRequest, test: TestHeader = None) -> OrderStatus:
    raise HTTPException(status_code=501, detail="not_implemented")


@app.get(
    "/v1/products/{sku}/availability",
    response_model=Availability,
    responses={404: {"model": APIError}},
)
def get_availability(sku: str, test: TestHeader = None) -> Availability:
    raise HTTPException(status_code=501, detail="not_implemented")


@app.get("/v1/stores", response_model=list[StoreInfo])
def list_stores(test: TestHeader = None) -> list[StoreInfo]:
    raise HTTPException(status_code=501, detail="not_implemented")


@app.get("/v1/stores/{store_id}", response_model=StoreInfo, responses={404: {"model": APIError}})
def get_store(store_id: str, test: TestHeader = None) -> StoreInfo:
    raise HTTPException(status_code=501, detail="not_implemented")


@app.post("/v1/tickets", response_model=TicketCreated, status_code=201)
def create_ticket(request: TicketCreateRequest, test: TestHeader = None) -> TicketCreated:
    raise HTTPException(status_code=501, detail="not_implemented")


@app.get(
    "/v1/tickets/{ticket_id}",
    response_model=TicketRecord,
    responses={401: {"model": APIError}, 404: {"model": APIError}},
)
def get_ticket(
    ticket_id: str, staff_key: StaffHeader = None, test: TestHeader = None
) -> TicketRecord:
    raise HTTPException(status_code=501, detail="not_implemented")
