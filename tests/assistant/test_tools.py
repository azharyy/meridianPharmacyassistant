"""Public tools reject unknown inputs and mismatched API results before rendering."""

from datetime import UTC, datetime

import httpx
import pytest

from assistant.tools import allowed, execute
from contracts.api import Availability, StoreInfo
from contracts.plan import AvailabilityRequest, StoreRequest
from contracts.taxonomy import Intent

SKU = "MRD-ALG-012"
STORES = [
    StoreInfo(
        store_id=f"store-00{number}",
        name=f"Meridian Store {number}",
        address=f"{number} Sample Street",
        phone=f"(217) 555-010{number}",
        hours={"Sunday": "Closed"},
        services=["Pharmacist consultations"],
    )
    for number in (1, 2)
]
STORE_IDS = [store.store_id for store in STORES]
AVAILABILITY = Availability(
    sku=SKU,
    stores=[
        {"store_id": store.store_id, "store_name": store.name, "quantity": number}
        for number, store in enumerate(STORES)
    ],
)
STOCK = AvailabilityRequest(name="check_availability", sku=SKU)
STORE = StoreRequest(name="get_store_info", store_id=STORE_IDS[0])
ALL_STORES = StoreRequest(name="get_store_info", store_id="")


def api(*answers):
    seen = []
    queue = list(answers)

    def handle(request):
        seen.append(request)
        answer = queue.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return answer

    return httpx.Client(base_url="http://api.test", transport=httpx.MockTransport(handle)), seen


@pytest.mark.parametrize("intent", list(Intent))
@pytest.mark.parametrize("tool", [None, STOCK, STORE])
def test_only_the_tool_allowed_for_the_intent_passes(intent, tool):
    expected = (
        tool is None
        or (intent is Intent.AVAILABILITY and tool is STOCK)
        or (intent is Intent.STORE_INFO and tool is STORE)
    )
    assert allowed(intent, tool) is expected


@pytest.mark.parametrize(
    "tool",
    [
        None,
        AvailabilityRequest(name="check_availability", sku="MRD-ALG-999"),
        StoreRequest(name="get_store_info", store_id="store-999"),
    ],
)
def test_unknown_identifiers_make_no_api_request(tool):
    http, seen = api()
    assert execute(http, tool, skus=[SKU], store_ids=STORE_IDS) is None
    assert seen == []


@pytest.mark.parametrize("tool", [STOCK, STORE, ALL_STORES])
def test_unconfigured_executor_makes_no_api_request(tool):
    http, seen = api()
    assert execute(http, tool) is None
    assert seen == []


@pytest.mark.parametrize(
    ("tool", "payload", "path"),
    [
        (STOCK, AVAILABILITY, f"/v1/products/{SKU}/availability"),
        (STORE, STORES[0], "/v1/stores/store-001"),
        (ALL_STORES, STORES, "/v1/stores"),
    ],
)
def test_allowed_lookup_returns_the_matching_data_and_actual_call_time(tool, payload, path):
    body = (
        payload.model_dump(mode="json")
        if hasattr(payload, "model_dump")
        else [store.model_dump(mode="json") for store in payload]
    )
    http, seen = api(httpx.Response(200, json=body))
    before = datetime.now(UTC)
    result, checked_at = execute(http, tool, skus=[SKU], store_ids=STORE_IDS)
    assert before <= checked_at <= datetime.now(UTC)
    assert checked_at.utcoffset().total_seconds() == 0
    assert result == ([payload] if tool is STORE else payload)
    assert [(request.method, request.url.path) for request in seen] == [("GET", path)]


@pytest.mark.parametrize("failure", [httpx.Response(504), httpx.ReadTimeout("timed out")])
def test_read_timeout_is_tried_exactly_twice(failure):
    http, seen = api(failure, failure)
    assert execute(http, STOCK, skus=[SKU], store_ids=STORE_IDS) is None
    assert len(seen) == 2


def test_read_retry_can_recover():
    http, seen = api(httpx.Response(504), httpx.Response(200, json=AVAILABILITY.model_dump()))
    result, _ = execute(http, STOCK, skus=[SKU], store_ids=STORE_IDS)
    assert result == AVAILABILITY and len(seen) == 2


@pytest.mark.parametrize(
    ("tool", "body"),
    [
        (STOCK, {**AVAILABILITY.model_dump(), "sku": "MRD-ALG-014"}),
        (STOCK, {**AVAILABILITY.model_dump(), "stores": []}),
        (STOCK, {**AVAILABILITY.model_dump(), "stores": [AVAILABILITY.stores[0].model_dump()]}),
        (STOCK, {**AVAILABILITY.model_dump(), "stores": [AVAILABILITY.stores[0].model_dump()] * 2}),
        (
            STOCK,
            {
                **AVAILABILITY.model_dump(),
                "stores": [
                    AVAILABILITY.stores[0].model_dump(),
                    {**AVAILABILITY.stores[1].model_dump(), "store_id": "store-999"},
                ],
            },
        ),
        (STOCK, {**AVAILABILITY.model_dump(), "unexpected": "untrusted"}),
        (STORE, STORES[1].model_dump()),
        (ALL_STORES, []),
        (ALL_STORES, [STORES[0].model_dump()]),
        (ALL_STORES, [STORES[0].model_dump()] * 2),
        (
            ALL_STORES,
            [store.model_dump() for store in STORES]
            + [{**STORES[0].model_dump(), "store_id": "store-999"}],
        ),
    ],
)
def test_wrong_identity_missing_stores_duplicates_and_extra_data_are_rejected(tool, body):
    http, seen = api(httpx.Response(200, json=body))
    assert execute(http, tool, skus=[SKU], store_ids=STORE_IDS) is None
    assert len(seen) == 1


def test_api_not_found_is_a_failed_lookup():
    http, seen = api(httpx.Response(404))
    assert execute(http, STOCK, skus=[SKU], store_ids=STORE_IDS) is None
    assert len(seen) == 1
