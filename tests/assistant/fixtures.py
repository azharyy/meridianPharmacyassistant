"""A two-product catalog and scripted model outputs, shared by the assistant's tests.

The label text is placeholder text, so no invented dosing text appears in the tests.
"""

from contracts.catalog import ProductRecord
from contracts.plan import CatalogPlan
from contracts.router import RouterOutput


def product(sku: str, name: str) -> ProductRecord:
    return ProductRecord(
        sku=sku,
        name=name,
        category="allergy",
        form="tablet",
        strength="10 mg",
        price="7.99",
        active_ingredients=f"Active ingredients of {name}, as printed on its label.",
        uses=f"Uses of {name}, as printed on its label.",
        warnings=f"Warnings of {name}, as printed on its label.",
        directions=f"Directions of {name}, as printed on its label.",
        source_set_id=f"fixture-{sku.lower()}",
        source_date="2026-01-01",
    )


PRODUCTS = [
    product("MRD-ALG-012", "Meridian All Day Allergy"),
    product("MRD-ALG-014", "Meridian 24-Hour Allergy"),
]
QUESTION = "How do I take Meridian All Day Allergy?"
ROUTED = RouterOutput(
    intent="product_info",
    risk_label="none",
    product_mentions=["Meridian All Day Allergy"],
    label_sections=["directions"],
    store_topic=None,
)
PLAN = CatalogPlan(
    reply_type="label_sections",
    records=[{"record_id": "MRD-ALG-012", "sections": ["directions"]}],
    tool=None,
)


def search(query: str, k: int) -> list[ProductRecord]:
    """The fixture retriever: both products, whatever the query."""
    return PRODUCTS[:k]
