"""Stock of one product at each store, from data/stock.json, with each store's name."""

import json
from pathlib import Path

from contracts.api import Availability, StoreInfo, StoreStock


class StockRoom:
    def __init__(self, rows: list[dict], stores: dict[str, StoreInfo]) -> None:
        self._by_sku: dict[str, list[StoreStock]] = {}
        for row in rows:
            stock = StoreStock(
                store_id=row["store_id"],
                store_name=stores[row["store_id"]].name,
                quantity=row["quantity"],
            )
            self._by_sku.setdefault(row["sku"], []).append(stock)

    @classmethod
    def from_file(cls, path: Path, stores: dict[str, StoreInfo]) -> "StockRoom":
        return cls(json.loads(path.read_text(encoding="utf-8")), stores)

    def availability(self, sku: str) -> Availability | None:
        """Stock by store, or None for a SKU the catalog doesn't hold."""
        stores = self._by_sku.get(sku)
        return None if stores is None else Availability(sku=sku, stores=stores)
