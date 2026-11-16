"""Replace emails, phone numbers and order numbers typed into the chat with placeholders.

Runs on every message before the model or the logs see it. Ages, doses, medicine names and
SKUs stay as typed: the router needs them, and none of them identifies a customer.
Phone recognition covers US formats, +/00 international prefixes (8-15 digits), and
seven-digit local numbers introduced by phone/call/text context, not arbitrary digit lists.
"""

import re

EMAIL = "[email]"
PHONE = "[phone]"
ORDER_NUMBER = "[order number]"
NUMBER = "[number]"

# Emails go first, so no digits inside one are read as anything else; order numbers go before
# phone numbers for the same reason. Short local numbers need explicit contact context.
SEPARATOR = r"[\s./‐-―−﹣－-]*"  # dashes as phones and autocorrect type
INTERNATIONAL_SEPARATOR = r"(?:[ \t()‐-―−﹣－-]*|\.(?=\d))"
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
    (
        re.compile(
            rf"(?<!\w)(?:\+|00)[1-9](?:{INTERNATIONAL_SEPARATOR}\d){{7,14}}"
            rf"(?!\d|{INTERNATIONAL_SEPARATOR}\d){NOT_A_DOSE}",
            re.IGNORECASE,
        ),
        PHONE,
    ),
    (
        re.compile(
            r"(\b(?:phone|telephone|tel|mobile|call(?: me)?|text(?: me)?)"
            r"(?:\s+(?:number|is|at|on))*\s*:?\s*)"
            rf"\d{{3}}{SEPARATOR}\d{{4}}(?!\d){NOT_A_DOSE}",
            re.IGNORECASE,
        ),
        rf"\1{PHONE}",
    ),
    (
        re.compile(
            rf"(?<![\w-])(?:\+?1{SEPARATOR})?(?:\(\s*\d{{3}}\s*\)|\d{{3}})"
            rf"{SEPARATOR}\d{{3}}{SEPARATOR}\d{{4}}(?!\d){NOT_A_DOSE}",
            re.IGNORECASE,
        ),
        PHONE,
    ),
    # Run after phones so a five-digit international group is not split first.
    (re.compile(rf"(?<![\d@])\d{{5}}(?!\d|@|\.\d){NOT_A_DOSE}", re.IGNORECASE), NUMBER),
)


def redact(text: str) -> str:
    for pattern, placeholder in PATTERNS:
        text = pattern.sub(placeholder, text)
    return text
