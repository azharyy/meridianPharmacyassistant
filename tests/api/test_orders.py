"""The order desk: matching rules, status-only answers, and a lockout timed by a passed clock."""

import pytest

from api.orders import LOCK_AFTER, WINDOW, OrderDesk, contact_key, status_of

ORDER = {
    "order_number": "MRD-ORD-48213",
    "customer": {"name": "Sam Lee", "email": "sam.lee@example.com", "phone": "(217) 555-0110"},
    "status": "shipped",
    "placed_on": "2026-11-10",
    "delivery_estimate": "2026-11-13",
    "items": [{"sku": "MRD-ALG-012", "quantity": 2}, {"sku": "MRD-PAN-003", "quantity": 1}],
    "address": "12 Elm Street, Springfield, IL 62701",
}


class Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


@pytest.mark.parametrize(
    ("given", "key"),
    [
        (" Sam.Lee@Example.COM ", "sam.lee@example.com"),
        ("(217) 555-0110", "2175550110"),
        ("+1 217.555.0110", "2175550110"),
        ("555-0110", "5550110"),
    ],
)
def test_contact_keys(given, key):
    assert contact_key(given) == key


def test_the_status_holds_no_items_address_or_contact():
    assert status_of(ORDER).model_dump(mode="json") == {
        "status": "shipped",
        "delivery_estimate": "2026-11-13",
        "item_count": 3,
    }


def test_a_match_needs_the_number_and_the_email_or_phone_of_that_order():
    desk = OrderDesk([ORDER], Clock())
    assert desk.lookup("MRD-ORD-48213", "sam.lee@example.com") == status_of(ORDER)
    assert desk.lookup("mrd-ord-48213 ", "217 555 0110") == status_of(ORDER)
    assert desk.lookup("MRD-ORD-48231", "sam.lee@example.com") is None
    assert desk.lookup("MRD-ORD-48213", "555-0110") is None
    assert desk.lookup("MRD-ORD-48213", "   ") is None


def test_the_fifth_failure_locks_for_ten_minutes_and_a_refused_lookup_does_not_extend_it():
    clock = Clock()
    desk = OrderDesk([ORDER], clock)
    for _ in range(LOCK_AFTER):
        desk.lookup("MRD-ORD-48213", "wrong@example.com")
    clock.now += WINDOW - 1
    assert desk.lookup("MRD-ORD-48213", "sam.lee@example.com") is None
    clock.now += 1
    assert desk.lookup("MRD-ORD-48213", "sam.lee@example.com") == status_of(ORDER)


def test_failures_spread_over_more_than_ten_minutes_do_not_lock():
    clock = Clock()
    desk = OrderDesk([ORDER], clock)
    for _ in range(LOCK_AFTER - 1):
        desk.lookup("MRD-ORD-48213", "wrong@example.com")
    clock.now += WINDOW
    desk.lookup("MRD-ORD-48213", "wrong@example.com")
    assert desk.lookup("MRD-ORD-48213", "sam.lee@example.com") == status_of(ORDER)


def test_a_success_does_not_reset_the_failure_count():
    desk = OrderDesk([ORDER], Clock())
    for _ in range(LOCK_AFTER - 1):
        desk.lookup("MRD-ORD-99999", "sam.lee@example.com")
    assert desk.lookup("MRD-ORD-48213", "sam.lee@example.com") == status_of(ORDER)
    desk.lookup("MRD-ORD-99998", "sam.lee@example.com")
    assert desk.lookup("MRD-ORD-48213", "sam.lee@example.com") is None
