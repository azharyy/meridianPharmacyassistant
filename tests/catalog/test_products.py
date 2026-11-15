"""Every product is a valid record whose label text is its raw label's, word for word."""

import json
import re
from collections import Counter
from itertools import combinations
from pathlib import Path

import pytest

from contracts.catalog import ProductRecord
from scripts.label_text import (
    PHONE,
    SECTION_FIELDS,
    WARNING_FIELDS,
    field_text,
    normalize,
    problems,
    real_names,
    sections,
    strip_heading,
)

ROOT = Path(__file__).resolve().parents[2]
PRODUCTS = json.loads((ROOT / "catalog" / "products.json").read_text(encoding="utf-8"))
CODES = {
    "ALG": "allergy",
    "PAN": "pain and fever",
    "CLD": "cough and cold",
    "DIG": "digestive",
    "SKN": "skin",
    "SLP": "sleep",
    "EYE": "eye care",
}
# National brands and store brands no record may name. Issue 5's alias table maps the national
# ones to their ingredients; the catalog itself never uses them.
BRANDS = [
    "Zyrtec", "Claritin", "Allegra", "Xyzal", "Chlor-Trimeton", "Benadryl", "Tylenol", "Advil",
    "Motrin", "Aleve", "Bayer", "Ecotrin", "Robitussin", "Mucinex", "Delsym", "Sudafed", "Afrin",
    "Vicks", "Sinex", "NyQuil", "DayQuil", "Pepcid", "Prilosec", "Imodium", "Pepto", "Tums",
    "Gas-X", "Phazyme", "Cortaid", "Cortizone", "Lotrimin", "Lamisil", "Clearasil", "PanOxyl",
    "Proactiv", "Unisom", "ZzzQuil", "Zaditor", "Alaway", "Visine", "Refresh", "TheraTears",
    "Systane", "Equate", "Kirkland", "up & up", "up and up", "Good Remedies", "CareOne",
    "Care One", "Foster and Thrive", "DG Health", "Meijer", "GoodMeds",
]  # fmt: skip
# Uses that products with different ingredients share, so comparisons have something to compare.
SHARED_USES = [
    "hay fever",
    "minor aches and pains",
    "heartburn",
    "diarrhea",
    "asleep",
    "athlete's foot",
]


def raw(product: dict) -> dict:
    path = ROOT / "catalog" / "raw" / f"{product['source_set_id']}.json"
    return json.loads(path.read_text(encoding="utf-8"))


def shown_text(product: dict) -> str:
    """The name and the four label sections: what a customer can read."""
    return " ".join([product["name"], *(product[section] for section in SECTION_FIELDS)])


def ingredient(product: dict) -> str:
    return raw(product)["openfda"]["generic_name"][0].split()[0].lower()


def test_52_products_each_a_valid_record_with_a_unique_sku():
    assert len(PRODUCTS) == len({product["sku"] for product in PRODUCTS}) == 52
    for product in PRODUCTS:
        assert ProductRecord.model_validate(product).model_dump(mode="json") == product


@pytest.mark.parametrize("product", PRODUCTS, ids=lambda product: product["sku"])
def test_each_section_is_its_raw_labels_text_word_for_word(product):
    label = raw(product)
    for section, field in SECTION_FIELDS.items():
        if section != "warnings":
            assert product[section] in normalize(" ".join(label[field]))
    assert {section: product[section] for section in SECTION_FIELDS} == sections(label)


@pytest.mark.parametrize("product", PRODUCTS, ids=lambda product: product["sku"])
def test_the_warnings_drop_nothing_the_label_says(product):
    label = raw(product)
    for field in WARNING_FIELDS:
        part = field_text(label, field)
        if field == "warnings":
            part = strip_heading(part, "warnings")
        assert part in product["warnings"]


@pytest.mark.parametrize("product", PRODUCTS, ids=lambda product: product["sku"])
def test_the_source_is_the_raw_label_and_it_passes_the_label_rules(product):
    label = raw(product)
    assert problems(label) == []
    assert label["set_id"] == product["source_set_id"]
    assert label["effective_time"] == product["source_date"].replace("-", "")


@pytest.mark.parametrize("product", PRODUCTS, ids=lambda product: product["sku"])
def test_no_brand_manufacturer_or_phone_number_in_any_record(product):
    text = shown_text(product)
    for name in [*real_names(raw(product)), *BRANDS]:
        assert not re.search(rf"(?i)\b{re.escape(name)}\b", text), name
    assert not PHONE.search(text)


def test_skus_carry_their_category_and_every_category_has_two_products():
    for product in PRODUCTS:
        assert CODES[product["sku"].split("-")[1]] == product["category"]
    counts = Counter(product["category"] for product in PRODUCTS)
    assert set(counts) == set(CODES.values())
    assert min(counts.values()) >= 2


def test_at_least_four_uses_are_shared_by_products_with_different_ingredients():
    shared = set()
    for use in SHARED_USES:
        having = [p for p in PRODUCTS if use in p["uses"].lower().replace("’", "'")]
        if any(ingredient(a) != ingredient(b) for a, b in combinations(having, 2)):
            shared.add(use)
    assert len(shared) >= 4, shared
