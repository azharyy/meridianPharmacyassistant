"""Check section indexing, BM25 ranking and unchanged whole-record retrieval."""

import json

import pytest

from assistant.retrieval.index import SECTIONS, SearchIndex
from contracts.catalog import PolicyRecord, ProductRecord, Retriever
from tests.assistant.fixtures import product


@pytest.fixture
def catalog(tmp_path):
    first = product("MRD-ALG-001", "Meridian First").model_copy(
        update={section: f"fixture{section.replace('_', '')}" for section in SECTIONS}
    )
    second = product("MRD-ALG-002", "Meridian Second")
    path = tmp_path / "products.json"
    path.write_text(
        json.dumps([first.model_dump(mode="json"), second.model_dump(mode="json")]),
        encoding="utf-8",
    )
    policies = tmp_path / "policies"
    policies.mkdir()
    (policies / "delivery.md").write_text(
        "# Delivery\n\n## Delivery area\n\nFixture delivery text.\n\n"
        "## Fees & refunds\n\nFixture fees text.\n",
        encoding="utf-8",
    )
    return path, policies, [first, second]


@pytest.fixture
def index(catalog):
    path, policies, _ = catalog
    search = SearchIndex(path, policies)
    yield search
    search.close()


@pytest.mark.parametrize("section", SECTIONS)
def test_every_product_section_returns_the_whole_record(index, catalog, section):
    found = index.search(f"fixture{section.replace('_', '')}", 5)
    assert found == [catalog[2][0]]
    assert isinstance(found[0], ProductRecord)
    assert set(type(found[0]).model_fields) == set(ProductRecord.model_fields)


def test_multiple_section_hits_do_not_duplicate_a_product(index, catalog):
    assert index.search("Meridian First", 5).count(catalog[2][0]) == 1


def test_retrieval_protocol_accepts_the_index_and_respects_k(index):
    retriever: Retriever = index
    all_matches = retriever.search("Meridian", 20)
    assert len(all_matches) == 2
    assert retriever.search("Meridian", 1) == all_matches[:1]


def test_policy_section_preserves_its_body_and_citable_anchor(index):
    assert index.search("refunds", 1) == [
        PolicyRecord(
            source_id="policies/delivery.md#fees-refunds",
            title="Fees & refunds",
            text="Fixture fees text.",
        )
    ]


def test_bm25_puts_the_distinctive_section_first(index):
    found = index.search("delivery area", 5)
    assert isinstance(found[0], PolicyRecord)
    assert found[0].source_id == "policies/delivery.md#delivery-area"


def test_a_named_product_is_found_only_by_its_sku_name_ingredient_or_alias():
    index = SearchIndex(exact_match=False)  # the strict lookup ignores the retrieval flag
    try:
        assert index.search("warfarin", 1)[0].sku == "MRD-PAN-002"  # its warnings mention it
        assert index.named("warfarin") is None
        assert index.named("Meridian All Day Allergy").sku == "MRD-ALG-012"
        assert index.named("Can I take MRD-ALG-012 twice?").sku == "MRD-ALG-012"
        assert index.named("Advil") is None
        assert "Acetaminophen" in index.named("acetaminophen").active_ingredients
    finally:
        index.close()


def test_default_paths_load_the_catalog_and_each_policy_section():
    index = SearchIndex()
    try:
        assert sum(isinstance(record, ProductRecord) for record in index.records.values()) == 52
        assert sum(isinstance(record, PolicyRecord) for record in index.records.values()) == 16
        found = index.search("delivery fees", 1)
        assert found[0].source_id == "policies/delivery.md#delivery-fees"
    finally:
        index.close()


@pytest.mark.parametrize("query", ['" OR * ( ) - :', "NEAR(foo bar)", "x' UNION SELECT 1 --"])
def test_customer_input_is_literal_fts_text(index, query):
    assert isinstance(index.search(query, 5), list)


@pytest.mark.parametrize("exact_match", [False, True])
@pytest.mark.parametrize("query", ["", " \t\n", "...?!", "quuxnoncatalogtoken987"])
def test_empty_or_unmatched_queries_return_no_records(catalog, exact_match, query):
    path, policies, _ = catalog
    index = SearchIndex(path, policies, exact_match=exact_match)
    try:
        assert index.search(query, 5) == []
    finally:
        index.close()


@pytest.mark.parametrize("flag", [False, True])
@pytest.mark.parametrize(
    ("query", "sku"),
    [
        ("MRD-ALG-012", "MRD-ALG-012"),
        ("Meridian All Day Allergy", "MRD-ALG-012"),
        ("MRD-ALG-012 MRD-ALG-012", "MRD-ALG-012"),
        ("oxymetazoline", "MRD-CLD-006"),
        ("Afrin", "MRD-CLD-006"),
        ("MRD-ALG-012 MRD-ALG-014", None),
        ("Meridian All Day Allergy and Meridian 24-Hour Allergy", None),
        ("diphenhydramine 2% spray", None),
        ("famotidine 10 mg", None),
        ("Advil", None),
    ],
)
def test_named_lookup_requires_one_identity_independent_of_search_flag(flag, query, sku):
    index = SearchIndex(exact_match=flag)
    try:
        found = index.named(query)
        assert (found.sku if found else None) == sku
    finally:
        index.close()
