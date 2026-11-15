"""Freeze product fields and allow whole product and policy retrieval records."""

from decimal import Decimal
from typing import get_type_hints

import pytest
from pydantic import TypeAdapter, ValidationError

from contracts.catalog import PolicyRecord, ProductRecord, Retriever

PRODUCT = {
    "sku": "MRD-ALG-012",
    "name": "Meridian sample",
    "category": "allergy",
    "form": "tablet",
    "strength": "sample strength",
    "price": "5.99",
    "active_ingredients": "Fixture ingredient.",
    "uses": "Fixture uses.",
    "warnings": "Complete fixture warnings.",
    "directions": "Fixture directions.",
    "source_set_id": "synthetic-label",
    "source_date": "2026-11-14",
}


def test_product_has_exact_plan_fields_and_preserves_text():
    assert set(ProductRecord.model_fields) == {
        "sku",
        "name",
        "category",
        "form",
        "strength",
        "price",
        "active_ingredients",
        "uses",
        "warnings",
        "directions",
        "source_set_id",
        "source_date",
    }
    product = ProductRecord(**PRODUCT)
    assert product.price == Decimal("5.99")
    assert product.model_dump(mode="json") == PRODUCT


@pytest.mark.parametrize(
    "changes",
    [
        {"price": "-1"},
        {"price": "NaN"},
        {"warnings": ""},
        {"source_date": "invalid"},
        {"manufacturer": "unwanted"},
        {"sku": "MRD-ALG-12"},
        {"sku": "ALG-012"},
        {"sku": "mrd-alg-012"},
    ],
)
def test_invalid_product(changes):
    with pytest.raises(ValidationError):
        ProductRecord(**(PRODUCT | changes))


def test_retrieval_returns_whole_products_and_policy_sections():
    result_type = get_type_hints(Retriever.search)["return"]
    policy = {
        "source_id": "policies/delivery.md#delivery-area",
        "title": "Delivery area",
        "text": "Complete synthetic policy section.",
    }
    records = TypeAdapter(result_type).validate_python([PRODUCT, policy])
    assert records == [ProductRecord(**PRODUCT), PolicyRecord(**policy)]
    assert records[0].warnings == PRODUCT["warnings"]
    assert records[1].text == policy["text"]
