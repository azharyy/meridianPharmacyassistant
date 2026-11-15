"""Replace emails, phone numbers and order numbers typed into the chat with placeholders.

Runs on every message before the model or the logs see it. Ages, doses, medicine names and
SKUs stay as typed: the router needs them, and none of them identifies a customer.
"""

import re

EMAIL = "[email]"
PHONE = "[phone]"
ORDER_NUMBER = "[order number]"

# Order numbers go first, so their digits are never read as a phone number. A phone number
# needs ten digits: a shorter pattern would also catch dose ranges such as "400-1200 mg".
PATTERNS = (
    (re.compile(r"\bMRD[\s-]*ORD[\s-]*\d+\b", re.IGNORECASE), ORDER_NUMBER),
    (re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+"), EMAIL),
    (
        re.compile(
            r"(?<![\w-])(?:\+?1[\s.-]?)?(?:\(\d{3}\)|\d{3})[\s.-]?\d{3}[\s.-]?\d{4}(?![\w-])"
        ),
        PHONE,
    ),
)


def redact(text: str) -> str:
    for pattern, placeholder in PATTERNS:
        text = pattern.sub(placeholder, text)
    return text
