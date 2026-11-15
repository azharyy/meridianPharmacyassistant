"""Validate permitted public lookups and return their API results with the call time."""

from collections.abc import Collection
from datetime import UTC, datetime

import httpx

from assistant import api_client
from contracts.api import Availability, StoreInfo
from contracts.plan import AvailabilityRequest, StoreRequest
from contracts.taxonomy import Intent

ToolRequest = AvailabilityRequest | StoreRequest
ToolResult = tuple[Availability | list[StoreInfo], datetime] | None
ALLOWED_TOOLS = {Intent.AVAILABILITY: AvailabilityRequest, Intent.STORE_INFO: StoreRequest}


def allowed(intent: Intent, tool: ToolRequest | None) -> bool:
    """Only the tool matching this turn's intent may run; no tool is always allowed."""
    return tool is None or isinstance(tool, ALLOWED_TOOLS.get(intent, ()))


def expected_stores(
    tool: ToolRequest, skus: Collection[str], store_ids: Collection[str]
) -> set[str]:
    if isinstance(tool, AvailabilityRequest):
        return set(store_ids) if tool.sku in skus else set()
    if tool.store_id:
        return {tool.store_id} if tool.store_id in store_ids else set()
    return set(store_ids)


def lookup(http: httpx.Client, tool: ToolRequest) -> Availability | list[StoreInfo] | None:
    if isinstance(tool, AvailabilityRequest):
        return api_client.get_availability(http, tool.sku)
    if not tool.store_id:  # Code uses an empty ID to ask for all stores.
        return api_client.list_stores(http)
    store = api_client.get_store(http, tool.store_id)
    return [store] if store is not None else None


def execute(
    http: httpx.Client,
    tool: ToolRequest | None,
    *,
    skus: Collection[str] = (),
    store_ids: Collection[str] = (),
) -> ToolResult:
    """Reject unknown identifiers before HTTP; reads reuse the API client's timeout and retry."""
    if tool is None:
        return None
    expected = expected_stores(tool, skus, store_ids)
    if not expected:
        return None
    checked_at = datetime.now(UTC)
    try:
        result = lookup(http, tool)
    except api_client.APIUnavailable:
        return None
    if result is None:
        return None
    if isinstance(result, Availability) and result.sku != tool.sku:
        return None
    stores = result.stores if isinstance(result, Availability) else result
    if {store.store_id for store in stores} != expected or len(stores) != len(expected):
        return None
    return result, checked_at
