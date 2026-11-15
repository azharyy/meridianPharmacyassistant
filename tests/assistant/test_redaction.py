"""Contact details and order numbers are replaced; ages, doses and medicine names stay intact."""

import pytest

from assistant.redaction import redact


@pytest.mark.parametrize(
    ("typed", "redacted"),
    [
        ("write to jane.doe+rx@example.co.uk please", "write to [email] please"),
        ("my email is SAM_88@mail.example.com.", "my email is [email]."),
        ("call me on (217) 555-0142", "call me on [phone]"),
        ("call me on 217-555-0142 or 217.555.0143", "call me on [phone] or [phone]"),
        ("my number is +1 217 555 0142", "my number is [phone]"),
        ("text 2175550142", "text [phone]"),
        ("where is MRD-ORD-48213?", "where is [order number]?"),
        ("order mrd ord 48213 and MRDORD48231", "order [order number] and [order number]"),
    ],
)
def test_contact_details_and_order_numbers_become_placeholders(typed, redacted):
    assert redact(typed) == redacted


def test_a_message_with_all_three():
    message = "Order MRD-ORD-48213 for sam@example.com, phone 217-555-0142: where is it?"
    assert redact(message) == "Order [order number] for [email], phone [phone]: where is it?"


@pytest.mark.parametrize(
    "message",
    [
        "I'm 34 and pregnant. Can I take 10 mg of cetirizine?",
        "My son is 6 years old and weighs 45 lb.",
        "Can I take 500mg ibuprofen every 4-6 hours, 400-1200 mg a day?",
        "Is Zyrtec the same as MRD-ALG-012?",
        "Take 2 tablets on 11/15/2026 at 08:00.",
    ],
)
def test_ages_doses_medicine_names_and_skus_stay_intact(message):
    assert redact(message) == message


def test_redacting_twice_changes_nothing_more():
    message = "MRD-ORD-48213, sam@example.com, (217) 555-0142"
    assert redact(redact(message)) == redact(message)
