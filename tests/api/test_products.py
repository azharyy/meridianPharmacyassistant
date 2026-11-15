"""Stock by store, with each store's name; nothing for a SKU the catalog doesn't hold."""

from api.products import StockRoom
from contracts.api import StoreInfo

STORES = {
    store_id: StoreInfo(
        store_id=store_id,
        name=name,
        address="1 Main St",
        phone="(217) 555-0100",
        hours={},
        services=[],
    )
    for store_id, name in (("store-001", "Downtown"), ("store-002", "Riverside"))
}
ROWS = [
    {"sku": "MRD-ALG-012", "store_id": "store-001", "quantity": 4},
    {"sku": "MRD-ALG-012", "store_id": "store-002", "quantity": 0},
]


def test_availability_names_each_store():
    availability = StockRoom(ROWS, STORES).availability("MRD-ALG-012")
    assert availability.model_dump() == {
        "sku": "MRD-ALG-012",
        "stores": [
            {"store_id": "store-001", "store_name": "Downtown", "quantity": 4},
            {"store_id": "store-002", "store_name": "Riverside", "quantity": 0},
        ],
    }


def test_an_unknown_sku_has_no_availability():
    assert StockRoom(ROWS, STORES).availability("MRD-ALG-999") is None
