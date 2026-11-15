"""Write data/orders.json and data/stock.json from a fixed seed: what `make seed-data` runs.

The same seed and base date give the same files, byte for byte. The orders carry the traps the
eval needs: two customers with the same name, a cancelled order, and look-alike order numbers
(two digits swapped) that belong to different customers. The mock API (issue 4) serves them and
returns an order's status, delivery estimate and item count only: never its items, address or
contact. All names, emails (reserved example domains) and phones (555-01xx) are fictional.

orders.json is a list of {"order_number", "customer": {"name", "email", "phone"}, "status",
"placed_on", "delivery_estimate", "items": [{"sku", "quantity"}], "address"}; the item count is
the sum of the quantities. stock.json is a list of {"sku", "store_id", "quantity"}, one row per
SKU per store.
"""

import json
import random
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SEED = 48213
BASE_DATE = date(2026, 11, 16)  # orders are dated around this day, never around today
ORDER_COUNT = 20
STORE_IDS = ("store-001", "store-002")
STREETS = ("Elm Street", "Oak Avenue", "Maple Drive", "Lake Road", "Cedar Lane", "Park Place")
CUSTOMERS = [
    ("Maria Garcia", "maria.garcia@example.com", "(217) 555-0110"),
    ("Maria Garcia", "mgarcia@example.org", "(217) 555-0123"),  # same name, another customer
    ("James Okafor", "james.okafor@example.net", "(217) 555-0131"),
    ("Priya Natarajan", "priya.n@example.com", "(217) 555-0135"),
    ("Tom Becker", "tbecker@example.org", "(217) 555-0146"),
    ("Aisha Rahman", "aisha.rahman@example.com", "(217) 555-0152"),
    ("Daniel Kim", "dkim@example.net", "(217) 555-0158"),
    ("Sofia Rossi", "sofia.rossi@example.com", "(217) 555-0163"),
    ("Liam O'Brien", "liam.obrien@example.org", "(217) 555-0169"),
    ("Grace Mensah", "grace.mensah@example.net", "(217) 555-0174"),
    ("Hiro Tanaka", "hiro.tanaka@example.com", "(217) 555-0181"),
    ("Elena Petrova", "elena.p@example.org", "(217) 555-0195"),
]
# Look-alike order numbers, each with the customer who owns it: two digits swapped each time.
LOOK_ALIKES = {"MRD-ORD-48213": 0, "MRD-ORD-48231": 1, "MRD-ORD-48123": 2}
STATUSES = (
    "shipped",
    "processing",
    "delivered",
    "ready_for_pickup",
    "shipped",
    "cancelled",
    "delivered",
    "processing",
)


def order_numbers(rng: random.Random) -> list[str]:
    numbers = list(LOOK_ALIKES)
    while len(numbers) < ORDER_COUNT:
        number = f"MRD-ORD-{rng.randint(10000, 99999)}"
        if number not in numbers:
            numbers.append(number)
    return numbers


def delivery_estimate(status: str, placed_on: date, rng: random.Random) -> str | None:
    if status in ("cancelled", "ready_for_pickup"):
        return None
    return (placed_on + timedelta(days=rng.randint(2, 4))).isoformat()


def order(number: str, owner: int, status: str, skus: list[str], rng: random.Random) -> dict:
    name, email, phone = CUSTOMERS[owner]
    placed_on = BASE_DATE - timedelta(days=rng.randint(0, 20))
    items = [
        {"sku": sku, "quantity": rng.randint(1, 3)} for sku in rng.sample(skus, rng.randint(1, 3))
    ]
    street = (
        f"{rng.randint(10, 999)} {rng.choice(STREETS)}, Springfield, IL 6270{rng.randint(1, 4)}"
    )
    return {
        "order_number": number,
        "customer": {"name": name, "email": email, "phone": phone},
        "status": status,
        "placed_on": placed_on.isoformat(),
        "delivery_estimate": delivery_estimate(status, placed_on, rng),
        "items": items,
        "address": street,
    }


def build_orders(skus: list[str], rng: random.Random) -> list[dict]:
    owners = [*LOOK_ALIKES.values(), *(i % len(CUSTOMERS) for i in range(3, ORDER_COUNT))]
    statuses = [STATUSES[i % len(STATUSES)] for i in range(ORDER_COUNT)]
    return [
        order(number, owner, status, skus, rng)
        for number, owner, status in zip(order_numbers(rng), owners, statuses, strict=True)
    ]


def build_stock(skus: list[str], rng: random.Random) -> list[dict]:
    """Stock for every SKU at both stores; about one row in seven is out of stock."""
    return [
        {
            "sku": sku,
            "store_id": store_id,
            "quantity": 0 if rng.random() < 0.15 else rng.randint(1, 40),
        }
        for sku in skus
        for store_id in STORE_IDS
    ]


def build(products: list[dict]) -> tuple[list[dict], list[dict]]:
    """Orders and stock for the catalog. Each has its own seeded generator."""
    skus = [product["sku"] for product in products]
    return build_orders(skus, random.Random(SEED)), build_stock(skus, random.Random(SEED + 1))


def write(path: Path, rows: list[dict]) -> None:
    path.write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8", newline="\n")


def main(products: Path = ROOT / "catalog" / "products.json", data: Path = ROOT / "data") -> None:
    orders, stock = build(json.loads(products.read_text(encoding="utf-8")))
    data.mkdir(parents=True, exist_ok=True)
    write(data / "orders.json", orders)
    write(data / "stock.json", stock)
    print(f"wrote {len(orders)} orders and {len(stock)} stock rows to {data}")


if __name__ == "__main__":
    main()
