"""The renderer builds replies from templates and record text only, and the fallback from policy."""

from datetime import UTC, datetime

import pytest

from assistant import policy, templates
from assistant.render import render, render_fallback, render_risk
from assistant.session import VerifiedOrder
from contracts.api import Availability, OrderStatus, StoreInfo
from contracts.catalog import PolicyRecord
from contracts.chat import ChatReply, TextBlock
from contracts.plan import AvailabilityRequest, CatalogPlan, StoreRequest
from contracts.taxonomy import LabelSection, ReplyType, RiskLabel
from tests.assistant.fixtures import PLAN, PRODUCTS


def strings(value) -> list[str]:
    """Every string in a JSON value."""
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [s for item in value.values() for s in strings(item)]
    if isinstance(value, list):
        return [s for item in value for s in strings(item)]
    return []


def allowed_strings() -> set[str]:
    """Record text, template wording, and the IDs and enum values a reply carries."""
    record_text = {value for p in PRODUCTS for value in p.model_dump(mode="json").values()}
    titles = set(templates.SECTION_TITLES.values())
    source_titles = {
        templates.LABEL_SOURCE_TITLE.format(name=p.name, section=t)
        for p in PRODUCTS
        for t in titles
    }
    ids = {f"{p.sku}#{s.value}" for p in PRODUCTS for s in LabelSection}
    enums = {e.value for e in (*ReplyType, *LabelSection)} | {"label_section", "text"}
    return {str(v) for v in record_text} | titles | source_titles | ids | enums


def test_the_cited_answer_is_the_label_section_word_for_word():
    reply = render(PLAN, PRODUCTS, RiskLabel.NONE, None)
    assert reply.reply_type is ReplyType.LABEL_SECTIONS
    [block] = reply.blocks
    assert (block.sku, block.section, block.title) == ("MRD-ALG-012", "directions", "Directions")
    assert block.text == PRODUCTS[0].directions
    [source] = reply.sources
    assert (source.id, source.text) == ("MRD-ALG-012#directions", PRODUCTS[0].directions)
    assert source.title == "Meridian All Day Allergy: Directions"
    assert (reply.handoff_offered, reply.emergency) == (False, False)


def test_the_reply_holds_only_template_and_record_text():
    reply = render(PLAN, PRODUCTS, RiskLabel.NONE, None)
    shown = strings(reply.model_dump(mode="json"))
    assert set(shown) <= allowed_strings()


def test_the_fallback_is_the_policys_fixed_reply_with_the_card():
    reply = render_fallback()
    assert reply == ChatReply(
        reply_type=ReplyType.FALLBACK,
        blocks=[{"type": "text", "text": policy.FALLBACK_TEXT}],
        sources=[],
        handoff_offered=True,
        emergency=False,
    )
    assert "call 911" in reply.blocks[0].text


def test_a_plan_naming_a_record_that_was_not_retrieved_gets_the_fallback():
    stray = CatalogPlan(
        reply_type="label_sections",
        records=[{"record_id": "MRD-ALG-999", "sections": ["directions"]}],
        tool=None,
    )
    assert render(stray, PRODUCTS, RiskLabel.NONE, None) == render_fallback()


def test_a_reply_type_this_issue_does_not_build_yet_gets_the_fallback():
    plan = PLAN.model_copy(update={"reply_type": ReplyType.COMPARISON})
    assert render(plan, PRODUCTS, RiskLabel.NONE, None) == render_fallback()


RISKS = [
    RiskLabel.EMERGENCY,
    RiskLabel.MEDICAL_ADVICE,
    RiskLabel.DOSING_BEYOND_LABEL,
    RiskLabel.PRESCRIPTION,
    RiskLabel.PROMPT_INJECTION,
]


@pytest.mark.parametrize("risk", RISKS)
def test_each_risk_reply_is_its_fixed_text_first_and_offers_the_card(risk):
    reply = render_risk(risk, None)
    assert reply.blocks == [TextBlock(type="text", text=policy.POLICY[risk].text)]
    assert reply.reply_type in policy.POLICY[risk].reply_types
    assert (reply.handoff_offered, reply.sources) == (True, [])
    assert reply.emergency is (risk is RiskLabel.EMERGENCY)


def test_the_911_reply_comes_first_and_the_card_after_it():
    reply = render_risk(RiskLabel.EMERGENCY, PRODUCTS[0])
    assert reply.blocks[0].text == policy.EMERGENCY_TEXT and len(reply.blocks) == 1
    assert reply.handoff_offered and reply.emergency


@pytest.mark.parametrize(
    ("risk", "section"),
    [
        (RiskLabel.MEDICAL_ADVICE, LabelSection.WARNINGS),
        (RiskLabel.DOSING_BEYOND_LABEL, LabelSection.DIRECTIONS),
    ],
)
def test_a_named_product_adds_only_the_section_the_label_allows(risk, section):
    reply = render_risk(risk, PRODUCTS[0])
    [_, block] = reply.blocks
    assert (block.section, block.text) == (section, getattr(PRODUCTS[0], section.value))
    assert [source.id for source in reply.sources] == [f"MRD-ALG-012#{section.value}"]


def test_a_prescription_refusal_shows_no_label_even_for_a_named_product():
    assert render_risk(RiskLabel.PRESCRIPTION, PRODUCTS[0]) == render_risk(
        RiskLabel.PRESCRIPTION, None
    )


def test_a_turn_without_risk_has_no_fixed_reply():
    with pytest.raises(ValueError):
        render_risk(RiskLabel.NONE, None)


def test_a_comparison_copies_all_four_sections_from_both_records():
    plan = CatalogPlan(
        reply_type="comparison",
        records=[{"record_id": p.sku, "sections": list(LabelSection)} for p in PRODUCTS],
        tool=None,
    )
    reply = render(plan, PRODUCTS, RiskLabel.NONE, None)
    [block] = reply.blocks
    assert block.type == "comparison"
    assert [p.sku for p in block.products] == [p.sku for p in PRODUCTS]
    assert [row.section for row in block.rows] == list(LabelSection)
    for row in block.rows:
        assert row.texts == [getattr(p, row.section.value) for p in PRODUCTS]
    assert len(reply.sources) == 8 and not reply.handoff_offered


def test_product_lists_keep_retrieval_order_and_copy_each_products_uses():
    plan = CatalogPlan(
        reply_type="product_list",
        records=[{"record_id": p.sku, "sections": ["uses"]} for p in reversed(PRODUCTS)],
        tool=None,
    )
    reply = render(plan, PRODUCTS, RiskLabel.NONE, None)
    [block] = reply.blocks
    assert block.type == "product_list"
    assert [(p.sku, p.uses) for p in block.products] == [(p.sku, p.uses) for p in PRODUCTS]


def test_a_policy_excerpt_copies_its_exact_section_and_source():
    policy = PolicyRecord(
        source_id="policies/returns.md#returning-a-product",
        title="Returns",
        text="The exact policy section.\nA second line.",
    )
    plan = CatalogPlan(
        reply_type="policy",
        records=[{"record_id": policy.source_id, "sections": []}],
        tool=None,
    )
    reply = render(plan, [*PRODUCTS, policy], RiskLabel.NONE, None)
    [block], [source] = reply.blocks, reply.sources
    assert (block.type, block.text, block.source_id) == (
        "policy_excerpt",
        policy.text,
        policy.source_id,
    )
    assert (source.id, source.title, source.text) == (policy.source_id, policy.title, policy.text)


@pytest.mark.parametrize("reply_type", list(policy.FIXED_REPLIES))
def test_each_fixed_plan_reply_uses_only_its_policy_text(reply_type):
    plan = CatalogPlan(reply_type=reply_type, records=[], tool=None)
    reply = render(plan, PRODUCTS, RiskLabel.NONE, None)
    fixed = policy.FIXED_REPLIES[reply_type]
    assert reply.reply_type == reply_type
    assert reply.blocks == [TextBlock(type="text", text=fixed.text)]
    assert reply.sources == [] and reply.handoff_offered == fixed.handoff_offered


@pytest.mark.parametrize("reply_type", ["comparison", "product_list", "policy"])
def test_missing_evidence_never_produces_a_partial_answer(reply_type):
    plan = CatalogPlan(reply_type=reply_type, records=[], tool=None)
    assert render(plan, PRODUCTS, RiskLabel.NONE, None) == render_fallback()


def test_sources_cite_only_displayed_evidence_and_do_not_repeat():
    selection = {"record_id": PRODUCTS[0].sku, "sections": ["directions", "directions"]}
    plan = CatalogPlan(reply_type="label_sections", records=[selection, selection], tool=None)
    reply = render(plan, PRODUCTS, RiskLabel.NONE, None)
    [source] = reply.sources
    assert source.id == f"{PRODUCTS[0].sku}#directions"
    assert source.text == PRODUCTS[0].directions and source.retrieved_at is None
    assert {block.source_id for block in reply.blocks} == {source.id}
    assert PRODUCTS[1].sku not in str(reply.model_dump())


@pytest.mark.parametrize("reply_type", ["comparison", "product_list"])
def test_each_displayed_product_section_has_its_exact_source(reply_type):
    plan = CatalogPlan(
        reply_type=reply_type,
        records=[{"record_id": p.sku, "sections": []} for p in PRODUCTS],
        tool=None,
    )
    reply = render(plan, PRODUCTS, RiskLabel.NONE, None)
    sections = list(LabelSection) if reply_type == "comparison" else [LabelSection.USES]
    expected = {f"{p.sku}#{section}": getattr(p, section) for p in PRODUCTS for section in sections}
    assert {source.id: source.text for source in reply.sources} == expected
    assert all(source.retrieved_at is None for source in reply.sources)


CHECKED_AT = datetime(2026, 1, 1, 12, 30, tzinfo=UTC)
API_STORES = [
    StoreInfo(
        store_id=f"store-00{number}",
        name=f"Meridian Store {number}",
        address=f"{number} Sample Street",
        phone=f"(217) 555-010{number}",
        hours={"Sunday": "Closed"},
        services=["Pharmacist consultations"],
    )
    for number in (2, 1)
]
API_AVAILABILITY = Availability(
    sku=PRODUCTS[0].sku,
    stores=[
        {"store_id": store.store_id, "store_name": store.name, "quantity": quantity}
        for store, quantity in zip(API_STORES, (0, 12), strict=True)
    ],
)
STOCK_PLAN = CatalogPlan(
    reply_type="availability",
    records=[{"record_id": PRODUCTS[0].sku, "sections": []}],
    tool=AvailabilityRequest(name="check_availability", sku=PRODUCTS[0].sku),
)
STORE_PLAN = CatalogPlan(
    reply_type="store_info",
    records=[],
    tool=StoreRequest(name="get_store_info", store_id=""),
)


def test_availability_uses_api_quantities_order_and_call_time():
    reply = render(STOCK_PLAN, PRODUCTS, RiskLabel.NONE, (API_AVAILABILITY, CHECKED_AT))
    [block], [source] = reply.blocks, reply.sources
    assert (block.type, block.sku, block.name) == (
        "availability",
        PRODUCTS[0].sku,
        PRODUCTS[0].name,
    )
    assert [(store.store_id, store.store_name, store.quantity) for store in block.stores] == [
        (store.store_id, store.store_name, store.quantity) for store in API_AVAILABILITY.stores
    ]
    assert [store.text for store in block.stores] == ["Out of stock", "In stock (12)"]
    assert source.id == block.source_id == f"api:availability/{PRODUCTS[0].sku}"
    assert (source.title, source.text, source.retrieved_at) == (
        templates.AVAILABILITY_SOURCE_TITLE,
        None,
        CHECKED_AT,
    )
    assert not reply.handoff_offered and not reply.emergency


@pytest.mark.parametrize("one_store", [False, True])
def test_store_replies_copy_api_fields_with_a_source_per_store(one_store):
    stores = API_STORES[:1] if one_store else API_STORES
    tool = StoreRequest(name="get_store_info", store_id=stores[0].store_id if one_store else "")
    plan = STORE_PLAN.model_copy(update={"tool": tool})
    reply = render(plan, PRODUCTS, RiskLabel.NONE, (stores, CHECKED_AT))
    assert [block.store for block in reply.blocks] == stores
    assert [block.source_id for block in reply.blocks] == [
        f"api:stores/{store.store_id}" for store in stores
    ]
    assert [
        (source.id, source.title, source.text, source.retrieved_at) for source in reply.sources
    ] == [
        (f"api:stores/{store.store_id}", templates.STORE_SOURCE_TITLE, None, CHECKED_AT)
        for store in stores
    ]
    assert not reply.handoff_offered and not reply.emergency
    assert PRODUCTS[0].directions not in str(reply.model_dump())


@pytest.mark.parametrize(
    "result",
    [
        None,
        API_AVAILABILITY,
        (API_AVAILABILITY,),
        (API_AVAILABILITY, "2026-01-01"),
        (API_AVAILABILITY, CHECKED_AT.replace(tzinfo=None)),
        (API_STORES, CHECKED_AT),
        (API_AVAILABILITY.model_copy(update={"sku": PRODUCTS[1].sku}), CHECKED_AT),
        (API_AVAILABILITY.model_copy(update={"stores": []}), CHECKED_AT),
        (
            API_AVAILABILITY.model_copy(update={"stores": API_AVAILABILITY.stores[:1] * 2}),
            CHECKED_AT,
        ),
    ],
)
def test_missing_or_mismatched_availability_result_has_one_fixed_failure(result):
    reply = render(STOCK_PLAN, PRODUCTS, RiskLabel.NONE, result)
    assert reply.reply_type is ReplyType.LOOKUP_FAILED
    assert reply.blocks == [TextBlock(type="text", text=policy.LOOKUP_FAILED_TEXT)]
    assert reply.sources == [] and not reply.handoff_offered


@pytest.mark.parametrize("ids", [[], [PRODUCTS[1].sku], [p.sku for p in PRODUCTS]])
def test_availability_requires_the_requested_product_selected_from_retrieval(ids):
    plan = CatalogPlan(
        reply_type="availability",
        records=[{"record_id": sku, "sections": []} for sku in ids],
        tool=STOCK_PLAN.tool,
    )
    reply = render(plan, PRODUCTS, RiskLabel.NONE, (API_AVAILABILITY, CHECKED_AT))
    assert reply.reply_type is ReplyType.LOOKUP_FAILED and reply.sources == []


def test_availability_never_uses_an_unretrieved_product_or_a_different_tool():
    result = API_AVAILABILITY, CHECKED_AT
    assert render(STOCK_PLAN, [], RiskLabel.NONE, result).reply_type is ReplyType.LOOKUP_FAILED
    plan = STOCK_PLAN.model_copy(update={"tool": STORE_PLAN.tool})
    assert render(plan, PRODUCTS, RiskLabel.NONE, result).reply_type is ReplyType.LOOKUP_FAILED


@pytest.mark.parametrize(
    "result",
    [
        None,
        ([], CHECKED_AT),
        ([{}], CHECKED_AT),
        (API_AVAILABILITY, CHECKED_AT),
        (API_STORES[:1] * 2, CHECKED_AT),
        ([API_STORES[0].model_copy(update={"store_id": "../orders"})], CHECKED_AT),
    ],
)
def test_missing_or_malformed_store_data_has_no_facts_or_sources(result):
    reply = render(STORE_PLAN, PRODUCTS, RiskLabel.NONE, result)
    assert reply.reply_type is ReplyType.LOOKUP_FAILED
    assert reply.blocks == [TextBlock(type="text", text=policy.LOOKUP_FAILED_TEXT)]
    assert reply.sources == []


def test_a_store_reply_must_match_the_requested_store_and_tool():
    plan = STORE_PLAN.model_copy(
        update={"tool": StoreRequest(name="get_store_info", store_id="store-002")}
    )
    assert (
        render(plan, [], RiskLabel.NONE, (API_STORES[1:], CHECKED_AT)).reply_type
        is ReplyType.LOOKUP_FAILED
    )
    plan = STORE_PLAN.model_copy(update={"tool": STOCK_PLAN.tool})
    assert (
        render(plan, [], RiskLabel.NONE, (API_STORES, CHECKED_AT)).reply_type
        is ReplyType.LOOKUP_FAILED
    )


@pytest.mark.parametrize("status", list(templates.ORDER_STATUSES))
@pytest.mark.parametrize("estimate", [None, "2026-11-17"])
def test_order_status_uses_only_the_verified_fields_and_lookup_timestamp(status, estimate):
    order = OrderStatus(status=status, delivery_estimate=estimate, item_count=2)
    verified = VerifiedOrder(order, CHECKED_AT)
    plan = CatalogPlan(reply_type="order_status", records=[], tool=None)
    reply = render(plan, [], RiskLabel.NONE, verified)
    [block], [source] = reply.blocks, reply.sources
    assert block.order == order and block.source_id == "api:orders"
    assert block.text == templates.ORDER_STATUS.format(
        status=templates.ORDER_STATUSES[status],
        delivery_estimate=estimate or templates.NO_DELIVERY_ESTIMATE,
        item_count=2,
    )
    assert (source.id, source.text, source.retrieved_at) == ("api:orders", None, CHECKED_AT)
    assert set(block.order.model_dump()) == {"status", "delivery_estimate", "item_count"}


def test_an_order_status_plan_without_verification_gets_no_order_data():
    plan = CatalogPlan(reply_type="order_status", records=[], tool=None)
    assert render(plan, PRODUCTS, RiskLabel.NONE, None) == render_fallback()


def test_the_order_form_comes_entirely_from_policy_wording():
    plan = CatalogPlan(reply_type="order_form", records=[], tool=None)
    reply = render(plan, [], RiskLabel.NONE, None)
    assert reply.reply_type == "order_form" and reply.sources == []
    [block] = reply.blocks
    assert (block.text, block.order_number_label, block.contact_label, block.submit_label) == (
        policy.ORDER_FORM_TEXT,
        policy.ORDER_NUMBER_LABEL,
        policy.ORDER_CONTACT_LABEL,
        policy.ORDER_SUBMIT_LABEL,
    )
