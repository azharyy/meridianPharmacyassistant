"""Capture actual API tool calls and validated response evidence without recording form inputs."""

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field

import httpx
from pydantic import TypeAdapter, ValidationError

from contracts.api import Availability, OrderStatus, StoreInfo


def tool_name(request: httpx.Request) -> str | None:
    path = request.url.path
    if request.method == "POST":
        return {"/v1/orders/lookup": "lookup_order", "/v1/tickets": "create_ticket"}.get(path)
    if request.method == "GET":
        if path.startswith("/v1/products/") and path.endswith("/availability"):
            return "check_availability"
        if path == "/v1/stores" or path.startswith("/v1/stores/"):
            return "get_store_info"
    return None


@dataclass
class APICapture:
    calls: list[str] = field(default_factory=list)
    evidence: dict[str, dict] = field(default_factory=dict)

    def request(self, request: httpx.Request) -> None:
        name = tool_name(request)
        if name is not None:
            self.calls.append(name)

    def response(self, response: httpx.Response) -> None:
        """Invalid API bodies are left to the client; never retain their unvalidated fields."""
        if not response.is_success:
            return
        name = tool_name(response.request)
        shapes = {"lookup_order": OrderStatus, "check_availability": Availability}
        shape = shapes.get(name)
        if name == "get_store_info":
            shape = list[StoreInfo] if response.request.url.path == "/v1/stores" else StoreInfo
        if shape is None:
            return
        try:
            response.read()
            result = TypeAdapter(shape).validate_json(response.content)
        except (ValidationError, httpx.TransportError):
            return
        self.keep(result)

    def keep(self, result: Availability | OrderStatus | StoreInfo | list[StoreInfo]) -> None:
        if isinstance(result, list):
            for store in result:
                self.keep(store)
            return
        if isinstance(result, OrderStatus):
            source_id = "api:orders"
        elif isinstance(result, Availability):
            source_id = f"api:availability/{result.sku}"
        else:
            source_id = f"api:stores/{result.store_id}"
        self.evidence[source_id] = result.model_dump(mode="json")


@contextmanager
def capture_api(http: httpx.Client) -> Iterator[APICapture]:
    """Observe this run without replacing existing hooks or retaining request bodies."""
    capture = APICapture()
    previous = {kind: list(http.event_hooks[kind]) for kind in ("request", "response")}
    http.event_hooks["request"].append(capture.request)
    http.event_hooks["response"].append(capture.response)
    try:
        yield capture
    finally:
        for kind, hooks in previous.items():
            http.event_hooks[kind] = hooks
