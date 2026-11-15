"""Call the mock Meridian API: the only code in the assistant that does, one function per endpoint.

Reads (availability, stores) are retried once on a timeout, a lost connection or a server error,
including the 504 that the test header asks for. The order lookup is not retried, because the
API counts every failed lookup towards its lockout. Neither is ticket creation: issue 7 retries
that itself, with the same idempotency key. The staff-only ticket read is not here, because the
assistant never holds the staff key.
"""

from urllib.parse import quote

import httpx
from pydantic import TypeAdapter, ValidationError

from assistant.settings import Settings
from contracts.api import (
    Availability,
    OrderLookupRequest,
    OrderStatus,
    StoreInfo,
    TicketCreated,
    TicketCreateRequest,
)

TIMEOUT = 3.0  # seconds for one request


class APIUnavailable(Exception):
    """The API timed out, couldn't be reached or failed. The caller shows a fixed reply."""


def connect(settings: Settings) -> httpx.Client:
    return httpx.Client(base_url=settings.api_url, timeout=TIMEOUT)


def send(
    http: httpx.Client, method: str, path: str, retry: bool, **kwargs
) -> httpx.Response | None:
    """One request, tried twice when `retry` is set. None for a 404; APIUnavailable on failure."""
    for _attempt in range(2 if retry else 1):
        try:
            response = http.request(method, path, **kwargs)
        except httpx.TransportError:
            continue
        if response.status_code == 404:
            return None
        if response.is_success:
            return response
        if response.status_code < 500:
            break  # a client error won't change on a retry
    raise APIUnavailable(f"{method} {path} failed")


def parse(shape: object, response: httpx.Response | None):
    """The body as `shape`, a contract model or a type such as list[StoreInfo]."""
    if response is None:
        raise APIUnavailable("unexpected 404")
    try:
        return TypeAdapter(shape).validate_json(response.content)
    except ValidationError as error:
        raise APIUnavailable("the API's answer didn't match the contract") from error


def segment(value: str) -> str:
    """A path segment with every reserved character escaped, so a value can't change the path."""
    return quote(value, safe="")


def lookup_order(http: httpx.Client, request: OrderLookupRequest) -> OrderStatus | None:
    """The order's status when the number and contact match one order; None for any mismatch."""
    response = send(http, "POST", "/v1/orders/lookup", retry=False, json=request.model_dump())
    return None if response is None else parse(OrderStatus, response)


def get_availability(http: httpx.Client, sku: str) -> Availability | None:
    response = send(http, "GET", f"/v1/products/{segment(sku)}/availability", retry=True)
    return None if response is None else parse(Availability, response)


def list_stores(http: httpx.Client) -> list[StoreInfo]:
    return parse(list[StoreInfo], send(http, "GET", "/v1/stores", retry=True))


def get_store(http: httpx.Client, store_id: str) -> StoreInfo | None:
    response = send(http, "GET", f"/v1/stores/{segment(store_id)}", retry=True)
    return None if response is None else parse(StoreInfo, response)


def create_ticket(http: httpx.Client, request: TicketCreateRequest) -> TicketCreated:
    body = request.model_dump(mode="json")
    return parse(TicketCreated, send(http, "POST", "/v1/tickets", retry=False, json=body))
