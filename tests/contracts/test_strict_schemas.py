"""Guard the strict structured-output subset for both model schemas."""

import pytest

from contracts.plan import CatalogPlan
from contracts.router import RouterOutput


def assert_strict_schema(node):
    if isinstance(node, dict):
        if node.get("type") == "object":
            assert node.get("additionalProperties") is False
            assert set(node.get("required", [])) == set(node["properties"])
        assert "default" not in node
        for child in node.values():
            assert_strict_schema(child)
    elif isinstance(node, list):
        for child in node:
            assert_strict_schema(child)


@pytest.mark.parametrize("model", [RouterOutput, CatalogPlan])
def test_model_schema_is_strict(model):
    assert_strict_schema(model.model_json_schema())


@pytest.mark.parametrize("model,field", [(RouterOutput, "store_topic"), (CatalogPlan, "tool")])
def test_optional_value_is_required_and_nullable(model, field):
    schema = model.model_json_schema()
    assert field in schema["required"]
    assert {"type": "null"} in schema["properties"][field]["anyOf"]


@pytest.mark.parametrize(
    "change", [{"required": []}, {"additionalProperties": True}, {"default": {}}]
)
def test_strict_check_detects_nested_drift(change):
    schema = CatalogPlan.model_json_schema()
    schema["$defs"]["RecordSelection"].update(change)
    with pytest.raises(AssertionError):
        assert_strict_schema(schema)
