"""Prove exact identifier/ingredient matching and the isolated keyword baseline."""

import pytest

from assistant.retrieval.exact import exact_products, ingredients, respell, typos
from assistant.retrieval.index import SearchIndex
from assistant.settings import load_settings
from tests.assistant.fixtures import product

FIRST = product("MRD-ALG-001", "Meridian Allergy").model_copy(
    update={"active_ingredients": "(in each tablet) Cetirizine HCl 10 mg"}
)
SECOND = product("MRD-ALG-002", "Meridian Allergy Capsules").model_copy(
    update={"active_ingredients": "(in each capsule) Cetirizine HCl 10 mg"}
)
PRODUCTS = [FIRST, SECOND]
ALIASES = {"FixtureBrand": "cetirizine"}


@pytest.mark.parametrize(
    "query",
    ["MRD-ALG-001", "mrd.alg.001", "mrdalg001", "meridian ALLERGY", "Meridian-Allergy"],
)
def test_sku_and_name_ignore_case_and_punctuation(query):
    assert exact_products(query, PRODUCTS, {})[0] == FIRST.sku


@pytest.mark.parametrize("query", ["cetirizine", "What does CETIRIZINE do?", "FixtureBrand"])
def test_ingredient_and_alias_find_the_whole_product_family(query):
    assert exact_products(query, PRODUCTS, ALIASES) == [FIRST.sku, SECOND.sku]


def test_longer_product_name_takes_precedence_over_the_shorter_family_name():
    assert exact_products("Meridian Allergy Capsules", PRODUCTS, {}) == [SECOND.sku]


@pytest.mark.parametrize("query", ["notfixturebrand", "cetirizines", "xMRDALG001", "hcl", "10 mg"])
def test_exact_terms_have_boundaries_and_do_not_match_label_boilerplate(query):
    assert exact_products(query, PRODUCTS, ALIASES) == []


@pytest.mark.parametrize(
    ("label", "expected"),
    [
        ("(in each tablet) Chlorpheniramine maleate 4 mg", "chlorpheniramine"),
        ("(in each tablet) Naproxen sodium 220 mg", "naproxen"),
        ("Sodium Carboxymethylcellulose 0.25%", "carboxymethylcellulose"),
        ("Tetrahydrozoline HCl.....0.05%", "tetrahydrozoline"),
        ("Terbinafine Hydrochloride 1%", "terbinafine"),
        ("(In Each Tablets) Phenylephrine HCl 5 mg", "phenylephrine"),
        ("(in each tablet) Omeprazole delayed-release tablet 20 mg", "omeprazole"),
    ],
)
def test_ingredient_names_come_from_label_text_without_changing_it(label, expected):
    record = FIRST.model_copy(update={"active_ingredients": label})
    assert expected in ingredients(record)
    assert record.active_ingredients == label


@pytest.mark.parametrize("flag", ["0", "1"])
def test_settings_flag_selects_only_keyword_or_exact_plus_keyword(flag):
    settings = load_settings({"MERIDIAN_EXACT_MATCH": flag})
    index = SearchIndex(exact_match=settings.exact_match, aliases={"FixtureBrand": "cetirizine"})
    try:
        found = index.search("FixtureBrand", 5)
        assert bool(found) == (flag == "1")
        assert index.search("cetirizine", 1)
    finally:
        index.close()


def test_exact_matching_is_on_by_default():
    index = SearchIndex(aliases={"FixtureBrand": "cetirizine"})
    try:
        assert load_settings({}).exact_match is True
        assert index.search("fixturebrand", 1)[0].sku == "MRD-ALG-012"
    finally:
        index.close()


@pytest.mark.parametrize(
    "query",
    [
        "Meridian Allergy and Meridian Allergy Capsules",
        "Meridian Allergy Capsules and Meridian Allergy",
        "MRD-ALG-001 vs MRD-ALG-002",
    ],
)
def test_two_explicit_products_both_reach_the_exact_stage(query):
    assert set(exact_products(query, PRODUCTS, {})) == {FIRST.sku, SECOND.sku}


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        (
            "Compare Meridian Ibuprofen Tablets Value Pack with Meridian Ibuprofen Tablets",
            ["MRD-PAN-004", "MRD-PAN-003"],
        ),
        (
            "Compare Meridian Ibuprofen Tablets with Meridian Ibuprofen Tablets Value Pack",
            ["MRD-PAN-003", "MRD-PAN-004"],
        ),
        ("MRD-ALG-012 versus MRD-PAN-005", ["MRD-ALG-012", "MRD-PAN-005"]),
        ("Advil and Aleve", ["MRD-PAN-001", "MRD-PAN-005"]),
        ("ibuprofen and naproxen", ["MRD-PAN-001", "MRD-PAN-005"]),
        (
            "Meridian Ibuprofen Tablets Value Pack and Aleve",
            ["MRD-PAN-004", "MRD-PAN-005"],
        ),
    ],
)
def test_comparison_preserves_both_named_products_with_k_two(query, expected):
    index = SearchIndex()
    try:
        assert [record.sku for record in index.search(query, 2)] == expected
    finally:
        index.close()


TERMS = [
    "ibuprofen",
    "acetaminophen",
    "tylenol",
    "loratadine",
    "cetirizine",
    "guaifenesin",
    "chlorpheniramine maleate",
    "diphenhydramine",
    "omeprazole",
    "lamisil",
    "claritin",
    "aleve",
]


@pytest.mark.parametrize(
    ("a", "b", "count"),
    [("kitten", "sitting", 3), ("ab", "ba", 1), ("", "abc", 3), ("ibuprofen", "ibuprofen", 0)],
)
def test_typos_count_inserts_deletes_replacements_and_neighbor_swaps(a, b, count):
    assert typos(a, b) == count


@pytest.mark.parametrize(
    ("typed", "respelled"),
    [
        ("meridian ibuprufen", "meridian ibuprofen"),  # a letter replaced
        ("ibuprfoen", "ibuprofen"),  # two neighbors swapped
        ("acetominophen", "acetaminophen"),
        ("tylenal", "tylenol"),  # a brand
        ("cetrizine", "cetirizine"),  # a letter missing
        ("guaifenisen", "guaifenesin"),  # two typos in a name of nine or more letters
        ("chlorpheniramine maleat", "chlorpheniramine maleate"),
    ],
)
def test_a_word_one_typo_from_one_catalog_word_is_respelled(typed, respelled):
    assert respell(typed, TERMS) == respelled


@pytest.mark.parametrize(
    "typed",
    [
        "ibuprofen",  # already a catalog word
        "aleeve",  # five-letter names such as aleve are left out
        "clarity",  # two typos from the eight-letter claritin
        "desloratadine",  # look-alike drugs outside the catalog
        "levocetirizine",
        "chlorpromazine",
        "guanfacine",
        "dimenhydrinate",
        "esomeprazole",
        "lamictal",
    ],
)
def test_correct_words_short_names_and_look_alike_drugs_stay_as_typed(typed):
    assert respell(typed, TERMS) == typed


def test_a_word_near_two_catalog_words_is_not_guessed():
    assert respell("loratidine", ["loratadine", "loratidane"]) == "loratidine"
