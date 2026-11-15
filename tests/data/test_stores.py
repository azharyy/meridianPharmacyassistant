"""Two stores, each a valid store record with an address, a phone, hours by weekday and services."""

import re
from pathlib import Path

import yaml

from contracts.api import StoreInfo

STORES = yaml.safe_load(
    (Path(__file__).resolve().parents[2] / "data" / "stores.yaml").read_text(encoding="utf-8")
)
WEEK = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def test_two_stores_each_a_valid_store_record():
    assert [store["store_id"] for store in STORES] == ["store-001", "store-002"]
    for store in STORES:
        assert StoreInfo.model_validate(store).model_dump() == store


def test_hours_cover_every_weekday_in_week_order():
    for store in STORES:
        assert list(store["hours"]) == WEEK
        assert all(isinstance(hours, str) and hours.strip() for hours in store["hours"].values())


def test_each_store_has_an_address_a_fictional_phone_and_services():
    for store in STORES:
        assert store["address"].strip()
        assert re.fullmatch(r"\(\d{3}\) 555-01\d\d", store["phone"])
        assert store["services"] and all(service.strip() for service in store["services"])
