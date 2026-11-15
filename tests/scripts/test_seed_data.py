"""Seeded orders and stock: identical on every run, with the three order traps and full stock."""

import json
import re
from itertools import combinations
from pathlib import Path

from scripts import seed_data

ROOT = Path(__file__).resolve().parents[2]
PRODUCTS = json.loads((ROOT / "catalog" / "products.json").read_text(encoding="utf-8"))
ORDERS = json.loads((ROOT / "data" / "orders.json").read_text(encoding="utf-8"))
STOCK = json.loads((ROOT / "data" / "stock.json").read_text(encoding="utf-8"))
SKUS = [product["sku"] for product in PRODUCTS]


def digits(order: dict) -> str:
    return order["order_number"].removeprefix("MRD-ORD-")


def test_running_twice_writes_identical_files(tmp_path):
    products = ROOT / "catalog" / "products.json"
    seed_data.main(products, tmp_path / "first")
    seed_data.main(products, tmp_path / "second")
    for name in ("orders.json", "stock.json"):
        assert (tmp_path / "first" / name).read_bytes() == (tmp_path / "second" / name).read_bytes()


def test_the_committed_files_are_what_the_seed_gives():
    assert seed_data.build(PRODUCTS) == (ORDERS, STOCK)


def test_about_twenty_orders_for_about_twelve_customers():
    customers = {order["customer"]["email"] for order in ORDERS}
    assert 18 <= len(ORDERS) <= 22
    assert 10 <= len(customers) <= 14


def test_order_numbers_are_unique_and_look_like_mrd_ord_48213():
    numbers = [order["order_number"] for order in ORDERS]
    assert len(set(numbers)) == len(numbers)
    assert all(re.fullmatch(r"MRD-ORD-\d{5}", number) for number in numbers)


def test_two_different_customers_share_a_name():
    by_name: dict[str, set[str]] = {}
    for order in ORDERS:
        by_name.setdefault(order["customer"]["name"], set()).add(order["customer"]["email"])
    assert any(len(emails) > 1 for emails in by_name.values())


def test_there_is_a_cancelled_order_with_no_delivery_estimate():
    cancelled = [order for order in ORDERS if order["status"] == "cancelled"]
    assert cancelled and all(order["delivery_estimate"] is None for order in cancelled)


def test_look_alike_order_numbers_belong_to_different_customers():
    look_alikes = [
        (a, b)
        for a, b in combinations(ORDERS, 2)
        if sorted(digits(a)) == sorted(digits(b))
        and sum(x != y for x, y in zip(digits(a), digits(b), strict=True)) == 2
    ]
    assert any(a["customer"]["email"] != b["customer"]["email"] for a, b in look_alikes)


def test_orders_hold_catalog_items_and_fictional_contacts():
    for order in ORDERS:
        assert order["items"] and all(item["sku"] in SKUS for item in order["items"])
        assert all(item["quantity"] >= 1 for item in order["items"])
        assert re.fullmatch(r"[\w.]+@example\.(com|org|net)", order["customer"]["email"])
        assert re.fullmatch(r"\(217\) 555-01\d\d", order["customer"]["phone"])


def test_a_stock_row_for_every_sku_at_both_stores_with_some_out_of_stock():
    rows = {(row["sku"], row["store_id"]): row["quantity"] for row in STOCK}
    assert len(rows) == len(STOCK) == 2 * len(SKUS)
    assert set(rows) == {(sku, store) for sku in SKUS for store in seed_data.STORE_IDS}
    assert all(quantity >= 0 for quantity in rows.values())
    assert any(quantity == 0 for quantity in rows.values())
