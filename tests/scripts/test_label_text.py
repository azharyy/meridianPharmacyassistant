"""Label text is only ever cut, never rewritten; unusable labels are named with their problem."""

import pytest

from scripts.label_text import problems, sections, strip_heading, warnings_text


def label(**fields) -> dict:
    """A small label shaped like openFDA's, with placeholder text."""
    base = {
        "set_id": "set-0001",
        "effective_time": "20260101",
        "active_ingredient": ["Active ingredient (in each tablet) Placeholderine 10 mg"],
        "indications_and_usage": ["Uses  placeholder uses text"],
        "warnings": ["Warnings"],
        "do_not_use": ["Do not use placeholder text."],
        "stop_use": ["Stop use and ask a doctor placeholder text."],
        "keep_out_of_reach_of_children": ["Keep out of reach of children."],
        "dosage_and_administration": ["Directions placeholder directions text"],
        "openfda": {
            "generic_name": ["PLACEHOLDERINE HYDROCHLORIDE"],
            "brand_name": ["Sample Allergy Care"],
            "manufacturer_name": ["Sample Labs Inc"],
        },
    }
    return base | fields


def test_each_section_loses_only_its_own_heading():
    assert sections(label()) == {
        "active_ingredients": "(in each tablet) Placeholderine 10 mg",
        "uses": "placeholder uses text",
        "warnings": "Do not use placeholder text. Stop use and ask a doctor placeholder text. "
        "Keep out of reach of children.",
        "directions": "placeholder directions text",
    }


@pytest.mark.parametrize(
    ("text", "section", "rest"),
    [
        ("USE(S) temporarily relieves", "uses", "temporarily relieves"),
        ("Use temporarily relieves", "uses", "temporarily relieves"),
        ("Uses: temporarily relieves", "uses", "temporarily relieves"),
        ("ACTIVE INGREDIENT(S) in each tablet X", "active_ingredients", "in each tablet X"),
        ("DIRECTIONS adults", "directions", "adults"),
        ("Warnings", "warnings", ""),
        ("Useful text", "uses", "Useful text"),
        ("temporarily relieves", "uses", "temporarily relieves"),
    ],
)
def test_strip_heading(text, section, rest):
    assert strip_heading(text, section) == rest


def test_the_active_ingredient_stops_where_the_purpose_begins():
    raw = ["Active ingredient (in each tablet) Placeholderine 180 mg Purpose Antihistamine"]
    found = sections(label(active_ingredient=raw))["active_ingredients"]
    assert found == "(in each tablet) Placeholderine 180 mg"


def test_warnings_already_complete_are_not_repeated():
    complete = (
        "Warnings Do not use placeholder text. Stop use and ask a doctor placeholder text. "
        "Keep out of reach of children."
    )
    assert warnings_text(label(warnings=[complete])) == complete.removeprefix("Warnings ")


def test_warnings_follow_drug_facts_order_and_drop_nothing():
    parts = {
        "keep_out_of_reach_of_children": ["Keep out of reach of children."],
        "when_using": ["When using this product placeholder text."],
        "ask_doctor": ["Ask a doctor before use placeholder text."],
    }
    text = warnings_text(label(warnings=["Warnings Reye's syndrome placeholder."], **parts))
    expected_order = [
        "Reye's syndrome placeholder.",
        "Do not use placeholder text.",
        "Ask a doctor before use placeholder text.",
        "When using this product placeholder text.",
        "Stop use and ask a doctor placeholder text.",
        "Keep out of reach of children.",
    ]
    assert text == " ".join(expected_order)


def test_a_usable_label_has_no_problems():
    assert problems(label()) == []


@pytest.mark.parametrize(
    ("changes", "problem"),
    [
        ({"dosage_and_administration": None}, "a section is missing"),
        ({"indications_and_usage": ["Uses"]}, "a section is empty"),
        ({"stop_use": ["Call 1-800-222-1222 now."]}, "a phone number"),
        ({"stop_use": ["Call (217) 555-0142."]}, "a phone number"),
        ({"indications_and_usage": ["Uses  runny nose"]}, "a symbol-font or broken character"),
        ({"indications_and_usage": ["Uses compare to Brandname®"]}, "a trademark sign"),
        (
            {"dosage_and_administration": ["Directions use daily Image Image"]},
            "a figure placeholder",
        ),
        (
            {"indications_and_usage": ["Uses like Sample Allergy Care"]},
            "a brand or manufacturer name",
        ),
        ({"stop_use": ["Made by Sample Labs Inc."]}, "a brand or manufacturer name"),
    ],
)
def test_unusable_labels_name_their_problem(changes, problem):
    assert problem in problems(label(**changes))


@pytest.mark.parametrize(
    "changes",
    [
        {"indications_and_usage": ["Uses Stop use and ask a doctor if irritation occurs"]},
        {"indications_and_usage": ["Uses for acne Warnings For external use only"]},
        {"active_ingredient": ["Purpose Placeholderine 5% Uses For acne"]},
        {"active_ingredient": ["Active Ingredients (in each tablet)"]},
        {"dosage_and_administration": ["Directions use daily Other information store cool"]},
        {"dosage_and_administration": ["Directions take one Directions take one"]},
        {"warnings": ["Warnings Do not use. Directions take one"]},
    ],
    ids=[
        "uses_hold_warnings",
        "uses_run_into_warnings",
        "ingredient_holds_purpose",
        "ingredient_without_strength",
        "directions_run_on",
        "directions_twice",
        "warnings_run_into_directions",
    ],
)
def test_a_section_holding_another_sections_text_is_not_used(changes):
    assert "a section holds the wrong text" in problems(label(**changes))


def test_a_cross_reference_to_another_section_is_fine():
    raw = {"when_using": ["When using this product do not take with fruit juices (see Directions)"]}
    assert problems(label(**raw)) == []


def test_zero_width_characters_count_as_whitespace():
    raw = {"dosage_and_administration": ["​Directions placeholder directions text"]}
    assert sections(label(**raw))["directions"] == "placeholder directions text"


@pytest.mark.parametrize(
    ("openfda", "problem"),
    [
        ({"generic_name": ["PLACEHOLDERINE AND OTHERINE"]}, "more than one active ingredient"),
        ({"generic_name": ["PLACEHOLDERINE, OTHERINE HCL"]}, "more than one active ingredient"),
        ({"generic_name": ["PLACEHOLDERINE / OTHERINE"]}, "more than one active ingredient"),
        ({"generic_name": ["A", "B"]}, "more than one active ingredient"),
        (
            {"generic_name": ["PLACEHOLDERINE"], "brand_name": ["Children's Placeholder"]},
            "a children's product",
        ),
    ],
)
def test_combinations_and_childrens_products_are_not_used(openfda, problem):
    assert problem in problems(label(openfda=openfda))


def test_a_brand_that_is_only_the_generic_name_is_not_a_brand():
    fda = {"generic_name": ["PLACEHOLDERINE HYDROCHLORIDE"], "brand_name": ["Placeholderine HCl"]}
    raw = ["Active ingredient Placeholderine HCl 10 mg"]
    assert problems(label(openfda=fda, active_ingredient=raw)) == []
