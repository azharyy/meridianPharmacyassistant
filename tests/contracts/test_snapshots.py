"""Fail when a contract schema or the API's OpenAPI drifts from the committed snapshot."""

import json

import pytest

from tests.contracts.snapshots import CONTRACTS, MODELS, current

STALE = "contracts/{} is out of date: a contract change needs `make contracts` in its own PR"


@pytest.mark.parametrize("name", sorted(current()))
def test_snapshot_matches_the_code(name):
    committed = (CONTRACTS / name).read_text(encoding="utf-8")
    assert json.loads(committed) == json.loads(current()[name]), STALE.format(name)
    assert committed == current()[name], f"contracts/{name}: run `make contracts` to reformat"


def test_snapshot_covers_both_model_facing_schemas_and_every_boundary_shape():
    schemas = json.loads(current()["schemas.json"])
    assert set(schemas) == {model.__name__ for model in MODELS}
    assert {"RouterOutput", "CatalogPlan", "ChatRequest", "ChatReply"} <= set(schemas)


def test_a_changed_schema_is_caught():
    committed = json.loads((CONTRACTS / "schemas.json").read_text(encoding="utf-8"))
    drifted = json.loads(current()["schemas.json"])
    drifted["CatalogPlan"]["properties"]["reply_text"] = {"type": "string"}
    assert drifted != committed
