"""Define the mock Meridian API's public data shapes."""

from datetime import date
from typing import Literal

from pydantic import Field

from contracts.base import Contract
from contracts.taxonomy import RiskLabel


class APIError(Contract):
    detail: str


class OrderLookupRequest(Contract):
    order_number: str = Field(min_length=1)
    contact: str = Field(min_length=1)


class OrderStatus(Contract):
    status: Literal["processing", "ready_for_pickup", "shipped", "delivered", "cancelled"]
    delivery_estimate: date | None
    item_count: int = Field(ge=0)


class StoreStock(Contract):
    store_id: str
    quantity: int = Field(ge=0)


class Availability(Contract):
    sku: str
    stores: list[StoreStock]


class StoreInfo(Contract):
    store_id: str
    name: str
    address: str
    phone: str
    hours: dict[str, str]
    services: list[str]


class TicketSummary(Contract):
    risk_label: RiskLabel
    urgency: Literal["routine", "urgent", "emergency"]
    customer_messages: list[str]
    product_mentions: list[str]
    assistant_replies: list[str]
    reason: Literal["risk", "fallback", "customer_requested"]


class TicketCreateRequest(Contract):
    idempotency_key: str = Field(min_length=1)
    summary: TicketSummary


class TicketCreated(Contract):
    ticket_id: str


class TicketRecord(TicketCreated):
    summary: TicketSummary
