"""Keep model plans limited to evidence selection and public tools."""

import pytest
from pydantic import ValidationError

from contracts.plan import CatalogPlan

PAYLOAD = {
    "reply_type": "label_sections",
    "records": [{"record_id": "MRD-ALG-012", "sections": ["warnings"]}],
    "tool": None,
}


@pytest.mark.parametrize(
    "tool",
    [
        None,
        {"name": "check_availability", "sku": "MRD-ALG-012"},
        {"name": "get_store_info", "store_id": "store-001"},
    ],
)
def test_plan_and_single_tool(tool):
    payload = PAYLOAD | {"tool": tool}
    assert CatalogPlan.model_validate(payload).model_dump(mode="json") == payload


@pytest.mark.parametrize(
    "changes",
    [
        {"tool": [{"name": "get_store_info", "store_id": "store-001"}] * 2},
        {"tool": {"name": "order_lookup", "order_number": "MRD-ORD-48213"}},
        {"tool": {"name": "check_availability", "store_id": "store-001"}},
        {"records": [{"record_id": "MRD-ALG-012", "sections": ["invented"]}]},
        {"records": [{"record_id": "MRD-ALG-012", "sections": [], "text": "invented"}]},
        {"reply_text": "model prose"},
        {"handoff_offered": True},
    ],
)
def test_plan_rejects_extra_powers(changes):
    with pytest.raises(ValidationError):
        CatalogPlan.model_validate(PAYLOAD | changes)


def test_policy_selection_uses_the_whole_section():
    record = {"record_id": "policies/delivery.md#delivery-area", "sections": []}
    assert (
        CatalogPlan(**(PAYLOAD | {"records": [record]})).records[0].record_id == record["record_id"]
    )
