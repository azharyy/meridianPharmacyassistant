"""The order lookup: an order's status only when its number and its email or phone both match.

Every failure looks the same to the caller. Five failed lookups for one order number or one
contact lock it for ten minutes, so order numbers can't be tried one by one. The answer holds
the status, delivery estimate and item count only: never the items, address or contact.
"""

import json
import re
import threading
from collections.abc import Callable
from pathlib import Path

from contracts.api import OrderStatus

LOCK_AFTER = 5
WINDOW = 600.0  # seconds: failures count for ten minutes, and a lock lasts ten minutes


def order_key(order_number: str) -> str:
    return order_number.strip().upper()


def contact_key(contact: str) -> str:
    """An email ignoring case and surrounding spaces, or a phone ignoring punctuation."""
    contact = contact.strip()
    if "@" in contact:
        return contact.lower()
    digits = re.sub(r"\D", "", contact)
    return digits[-10:] if len(digits) > 10 else digits  # "+1 (217) 555-0110" is the same phone


def status_of(order: dict) -> OrderStatus:
    return OrderStatus(
        status=order["status"],
        delivery_estimate=order["delivery_estimate"],
        item_count=sum(item["quantity"] for item in order["items"]),
    )


def matches(order: dict, contact: str) -> bool:
    given = contact_key(contact)
    customer = order["customer"]
    return bool(given) and given in {contact_key(customer["email"]), contact_key(customer["phone"])}


class OrderDesk:
    """Answers lookups and keeps the failure counts and locks. The clock is passed in."""

    def __init__(self, orders: list[dict], clock: Callable[[], float]) -> None:
        self._orders = {order_key(order["order_number"]): order for order in orders}
        self._clock = clock
        self._failures: dict[str, list[float]] = {}
        self._locked_until: dict[str, float] = {}
        self._guard = threading.Lock()

    @classmethod
    def from_file(cls, path: Path, clock: Callable[[], float]) -> "OrderDesk":
        return cls(json.loads(path.read_text(encoding="utf-8")), clock)

    def lookup(self, order_number: str, contact: str) -> OrderStatus | None:
        """The order's status, or None for any failure: unknown, mismatched or locked."""
        keys = (f"order:{order_key(order_number)}", f"contact:{contact_key(contact)}")
        with self._guard:
            now = self._clock()
            if any(self._locked_until.get(key, float("-inf")) > now for key in keys):
                return None  # a refused lookup doesn't extend the lock
            order = self._orders.get(order_key(order_number))
            if order is not None and matches(order, contact):
                return status_of(order)  # a success doesn't reset the counts
            for key in keys:
                self._fail(key, now)
            return None

    def _fail(self, key: str, now: float) -> None:
        recent = [moment for moment in self._failures.get(key, []) if now - moment < WINDOW]
        recent.append(now)
        if len(recent) >= LOCK_AFTER:
            self._locked_until[key] = now + WINDOW
            recent = []
        self._failures[key] = recent
