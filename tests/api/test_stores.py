"""The stores load from data/stores.yaml as contract records, keyed by ID in file order."""

from pathlib import Path

from api.stores import load_stores

DATA = Path(__file__).resolve().parents[2] / "data"


def test_both_stores_load_in_file_order():
    stores = load_stores(DATA / "stores.yaml")
    assert list(stores) == ["store-001", "store-002"]
    assert stores["store-001"].name == "Meridian Downtown"
    assert stores["store-002"].hours["Sunday"] == "Closed"
