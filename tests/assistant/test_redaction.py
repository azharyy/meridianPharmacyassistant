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
        ("call 217 / 555 / 0110", "call [phone]"),
        ("call 217  555  0110", "call [phone]"),
        ("call (217) 555 - 0110", "call [phone]"),
        ("call +1 / (217) / 555 - 0110", "call [phone]"),
        ("where is MRD-ORD-48213?", "where is [order number]?"),
        ("order mrd ord 48213 and MRDORD48231", "order [order number] and [order number]"),
        ("my order 48213", "my order [number]"),
        ("order #48213.", "order #[number]."),
        ("Order number: 48213, email sam@x.com", "Order number: [number], email [email]"),
        ("order no.48213 or order-48213", "order no.[number] or order-[number]"),
        ("MRD48213, MRD-48213, MRD-ORD-48213x", "MRD[number], MRD-[number], [order number]x"),
        ("Is there a store near 62701?", "Is there a store near [number]?"),
        ("ORD-48213 and MRD_ORD_48213", "[order number] and [order number]"),
        ("MRD–ORD–48213 or MRD‑ORD‑48213", "[order number] or [order number]"),
        ("call 217–555–0110 or 217—555—0110", "call [phone] or [phone]"),
        ("call 217‑555‑0110x2", "call [phone]x2"),
        ("48213@example.com or 2175550110@example.org", "[email] or [email]"),
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
        "I took 250 / 500 / 1000 mg, between 400 - 800 - 1200mg a day.",
        "Doses 100  200  1000 mg, or 10000 IU of vitamin D for $12.99?",
        "Can I ord 2 tablets? Is 250 500 1000 milligrams too much?",
    ],
)
def test_ages_doses_medicine_names_and_skus_stay_intact(message):
    assert redact(message) == message


def test_redacting_twice_changes_nothing_more():
    message = "MRD-ORD-48213, sam@example.com, (217) 555-0142"
    assert redact(redact(message)) == redact(message)
