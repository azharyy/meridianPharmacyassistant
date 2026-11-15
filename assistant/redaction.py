"""Replace emails, phone numbers and order numbers typed into the chat with placeholders.

Runs on every message before the model or the logs see it. Ages, doses, medicine names and
SKUs stay as typed: the router needs them, and none of them identifies a customer.
"""

import re

EMAIL = "[email]"
PHONE = "[phone]"
ORDER_NUMBER = "[order number]"
NUMBER = "[number]"

# Emails go first, so no digits inside one are read as anything else; order numbers go before
# phone numbers for the same reason. A phone number needs ten digits: a shorter pattern would
# also catch dose ranges such as "400-1200 mg".
SEPARATOR = r"[\s./‐-―−﹣－-]*"  # dashes as phones and autocorrect type
NOT_A_DOSE = (
    r"(?!\s*(?:mg|mcg|g|ml|iu|units?|tablets?|caplets?|capsules?|pills?"
    r"|milligrams?|micrograms?|grams?|millilit(?:er|re)s?)\b)"
)
PATTERNS = (
    (re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+"), EMAIL),
    (
        re.compile(r"\b(?:MRD[\W_]{0,3}ORD[\W_]{0,3}\d+|ORD[\W_]{0,3}\d{4,})", re.IGNORECASE),
        ORDER_NUMBER,
    ),
    # Order numbers have five digits, so any bare five-digit number ("my order #48213,", a zip
    # code) is hidden too, under a neutral placeholder that doesn't suggest an order.
    (re.compile(rf"(?<![\d@])\d{{5}}(?!\d|@|\.\d){NOT_A_DOSE}", re.IGNORECASE), NUMBER),
    (
        re.compile(
            rf"(?<![\w-])(?:\+?1{SEPARATOR})?(?:\(\s*\d{{3}}\s*\)|\d{{3}})"
            rf"{SEPARATOR}\d{{3}}{SEPARATOR}\d{{4}}(?!\d){NOT_A_DOSE}",
            re.IGNORECASE,
        ),
        PHONE,
    ),
)


def redact(text: str) -> str:
    for pattern, placeholder in PATTERNS:
        text = pattern.sub(placeholder, text)
    return text
