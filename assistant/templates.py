"""Hold every reply template: the wording that frames record text and API results.

Fixed replies live in assistant/policy.py. Text a template frames is copied word for word.
"""

from contracts.taxonomy import LabelSection

SECTION_TITLES = {
    LabelSection.ACTIVE_INGREDIENTS: "Active ingredients",
    LabelSection.USES: "Uses",
    LabelSection.WARNINGS: "Warnings",
    LabelSection.DIRECTIONS: "Directions",
}
# The title of a label section's source chip, such as "Meridian All Day Allergy: Directions".
LABEL_SOURCE_TITLE = "{name}: {section}"
IN_STOCK = "In stock ({quantity})"
OUT_OF_STOCK = "Out of stock"
AVAILABILITY_SOURCE_TITLE = "Stock check"
STORE_SOURCE_TITLE = "Store details"
ORDER_SOURCE_TITLE = "Order status"
ORDER_STATUS = (
    "Your order is {status}. Estimated delivery: {delivery_estimate}. Items: {item_count}."
)
NO_DELIVERY_ESTIMATE = "not available"
ORDER_STATUSES = {
    "processing": "processing",
    "ready_for_pickup": "ready for pickup",
    "shipped": "shipped",
    "delivered": "delivered",
    "cancelled": "cancelled",
}
