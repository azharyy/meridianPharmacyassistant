"""Check alias-table validation, catalog coverage and the flag's retrieval effect."""

import pytest

from assistant.retrieval.aliases import load_aliases
from assistant.retrieval.exact import exact_products, normalize, phrase
from assistant.retrieval.index import ROOT, SearchIndex, record_id
from contracts.catalog import ProductRecord

ALIASES = load_aliases(ROOT / "catalog" / "aliases.yaml")


@pytest.mark.parametrize(
    "content", ["null", "[]", "brand: []", "brand: null", "1: term", "brand: ''", "'!': term"]
)
def test_invalid_alias_mappings_fail_at_startup(tmp_path, content):
    path = tmp_path / "aliases.yaml"
    path.write_text(content, encoding="utf-8")
    with pytest.raises(ValueError, match="nonempty"):
        load_aliases(path)


def test_ambiguous_normalized_aliases_are_rejected(tmp_path):
    path = tmp_path / "aliases.yaml"
    path.write_text("Brand-X: first\nbrand x: second\n", encoding="utf-8")
    with pytest.raises(ValueError, match="unique"):
        load_aliases(path)


def test_every_catalog_ingredient_has_a_brand_from_the_independent_list():
    index = SearchIndex()
    try:
        brand_targets = [target for alias, target in ALIASES.items() if alias[0].isupper()]
        assert len(brand_targets) == 27
        for product in index.products:
            assert any(
                phrase(normalize(product.active_ingredients), term) for term in brand_targets
            )
    finally:
        index.close()


@pytest.mark.parametrize(("alias", "target"), ALIASES.items())
def test_every_alias_targets_existing_catalog_text_and_retrieves_it(alias, target):
    index = SearchIndex()
    try:
        found = index.search(alias, 5)
        assert found, alias
        assert isinstance(found[0], ProductRecord)
        if alias[0].isupper():
            assert phrase(normalize(found[0].active_ingredients), target), alias
        else:
            assert phrase(normalize(found[0].uses), target), alias
    finally:
        index.close()


def test_real_brand_alias_fails_with_the_flag_off_and_passes_with_it_on():
    baseline, improved = SearchIndex(exact_match=False), SearchIndex()
    try:
        assert baseline.search("Zyrtec", 5) == []
        assert improved.search("zYrTeC", 1)[0].sku == "MRD-ALG-012"
    finally:
        baseline.close()
        improved.close()


def test_a_brand_alias_does_not_crowd_the_policy_question_out_of_k():
    index = SearchIndex()
    try:
        found = [record_id(record) for record in index.search("Can I return Advil I bought?", 5)]
        assert found[0] == "MRD-PAN-001"  # the brand still finds ibuprofen first
        assert "policies/returns.md#returning-a-product" in found
        # Aspirin, reached only through the word "ibuprofen" in its warnings, stays out.
        assert not {"MRD-PAN-007", "MRD-PAN-008"} & set(found)
    finally:
        index.close()


def test_each_brand_target_also_works_as_an_exact_ingredient_without_aliases():
    index = SearchIndex()
    try:
        for alias, target in ALIASES.items():
            if alias[0].isupper():
                expected = [
                    record.sku
                    for record in index.products
                    if phrase(normalize(record.active_ingredients), target)
                ]
                assert exact_products(target, index.products, {}) == expected, target
    finally:
        index.close()
