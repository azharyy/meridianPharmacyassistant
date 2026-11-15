"""The stores' details, from data/stores.yaml: address, phone, hours by weekday and services."""

from pathlib import Path

import yaml

from contracts.api import StoreInfo


def load_stores(path: Path) -> dict[str, StoreInfo]:
    """Each store by its ID, in the file's order."""
    stores = [StoreInfo.model_validate(row) for row in yaml.safe_load(path.read_text("utf-8"))]
    return {store.store_id: store for store in stores}
