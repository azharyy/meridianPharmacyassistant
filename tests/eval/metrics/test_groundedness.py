"""Groundedness uses exact cited text and captured API data, with explicit fact-free counts."""

from datetime import UTC, datetime

import pytest

from assistant import policy, templates
from contracts.chat import ChatReply, HandoffReply
from contracts.taxonomy import LabelSection
from eval.metrics.groundedness import score
from eval.runner import RecordedTurn
from tests.assistant.fixtures import PRODUCTS
from tests.eval.fixtures import RECORDS, recorded_case, recorded_turn

NOW = datetime(2026, 1, 1, tzinfo=UTC)
POLICY_ID, POLICY_TEXT = "policies/returns.md#returns", "Exact policy.\nSecond line."


def reply(kind, blocks, sources):
    return ChatReply(
        reply_type=kind, blocks=blocks, sources=sources, handoff_offered=False, emergency=False
    )


def label_source(product, section):
    return {
        "id": f"{product.sku}#{section}",
        "text": getattr(product, section),
        "retrieved_at": None,
        "title": f"{product.name}: {templates.SECTION_TITLES[section]}",
    }


def catalog_turn(kind):
    if kind == "comparison":
        block = {
            "type": kind,
            "products": [{"sku": p.sku, "name": p.name} for p in PRODUCTS],
            "rows": [
                {
                    "section": section,
                    "title": templates.SECTION_TITLES[section],
                    "texts": [getattr(p, section) for p in PRODUCTS],
                }
                for section in LabelSection
            ],
        }
        sources = [label_source(p, section) for p in PRODUCTS for section in LabelSection]
    elif kind == "product_list":
        block = {
            "type": kind,
            "products": [
                {"sku": p.sku, "name": p.name, "uses": p.uses, "source_id": f"{p.sku}#uses"}
                for p in PRODUCTS
            ],
        }
        sources = [label_source(p, LabelSection.USES) for p in PRODUCTS]
    else:
        block = {
            "type": "policy_excerpt",
            "source_id": POLICY_ID,
            "title": "Returns",
            "text": POLICY_TEXT,
        }
        sources = [
            {
                "id": block["source_id"],
                "title": "Returns",
                "text": block["text"],
                "retrieved_at": None,
            }
        ]
    records = {**RECORDS, POLICY_ID: POLICY_TEXT}
    return recorded_turn(reply=reply(kind, [block], sources), record_evidence=records)


def api_turn(kind):
    if kind == "availability":
        source_id, title = f"api:availability/{PRODUCTS[0].sku}", "Stock check"
        payload = {
            "sku": PRODUCTS[0].sku,
            "stores": [{"store_id": "store-001", "store_name": "Downtown", "quantity": 12}],
        }
        block = {
            "type": kind,
            "sku": PRODUCTS[0].sku,
            "name": PRODUCTS[0].name,
            "stores": [{**payload["stores"][0], "text": "In stock (12)"}],
            "source_id": source_id,
        }
    elif kind == "store_info":
        source_id, title = "api:stores/store-001", "Store details"
        payload = {
            "store_id": "store-001",
            "name": "Downtown",
            "address": "Sample Street",
            "phone": "(217) 555-0100",
            "hours": {"Sunday": "Closed"},
            "services": ["Pickup"],
        }
        block = {"type": kind, "store": payload, "source_id": source_id}
    else:
        source_id, title = "api:orders", "Order status"
        payload = {"status": "shipped", "delivery_estimate": "2026-11-17", "item_count": 2}
        block = {
            "type": kind,
            "order": payload,
            "source_id": source_id,
            "text": "Your order is shipped. Estimated delivery: 2026-11-17. Items: 2.",
        }
    source = {"id": source_id, "title": title, "text": None, "retrieved_at": NOW}
    return recorded_turn(reply=reply(kind, [block], [source]), api_evidence={source_id: payload})


def changed(turn, path, value):
    data = turn.model_dump(mode="json")
    target = data
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    return RecordedTurn.model_validate(data)


def test_every_factual_block_type_is_grounded_by_its_actual_evidence():
    turns = [
        recorded_turn(),
        *(catalog_turn(kind) for kind in ("comparison", "product_list", "policy")),
        *(api_turn(kind) for kind in ("availability", "store_info", "order_status")),
    ]
    case = recorded_case(*turns)
    before = case.model_dump()
    assert score([case]) == {
        "grounded": 7,
        "factual": 7,
        "fact_free": 0,
        "rate": 1.0,
        "failed_cases": {},
        "skipped_handoffs": 0,
    }
    assert case.model_dump() == before


@pytest.mark.parametrize("text", [PRODUCTS[1].directions, "Take 40 tablets every hour."])
def test_a_reply_that_agrees_with_itself_still_needs_the_retrieved_record(text):
    # Another product's directions, or invented text, in both the block and its source.
    original = recorded_turn().reply
    block = original.blocks[0].model_copy(update={"text": text})
    source = original.sources[0].model_copy(update={"text": text})
    changed_reply = original.model_copy(update={"blocks": [block], "sources": [source]})
    result = score([recorded_case(recorded_turn(reply=changed_reply))])
    assert result["grounded"] == 0 and result["factual"] == 1


def test_a_cited_record_that_was_never_retrieved_is_not_grounded():
    assert score([recorded_case(recorded_turn(record_evidence={}))])["grounded"] == 0
    policy_turn = catalog_turn("policy")
    policy_turn.record_evidence = RECORDS
    assert score([recorded_case(policy_turn)])["grounded"] == 0


@pytest.mark.parametrize("kind", ["comparison", "product_list", "policy"])
def test_changed_catalog_text_fails_even_when_a_source_id_remains(kind):
    turn = catalog_turn(kind)
    paths = {
        "comparison": ["reply", "blocks", 0, "rows", 0, "texts", 1],
        "product_list": ["reply", "blocks", 0, "products", 0, "uses"],
        "policy": ["reply", "blocks", 0, "text"],
    }
    turn = changed(turn, paths[kind], "private@example.com")
    result = score([recorded_case(turn)])
    assert result["grounded"] == 0 and result["factual"] == 1
    assert result["rate"] == 0 and "case-001" in result["failed_cases"]
    assert "private@example.com" not in str(result)


@pytest.mark.parametrize(
    "failure", ["missing", "duplicate", "unused", "wrong_text", "wrong_section"]
)
def test_label_sources_must_be_unique_matching_and_actually_used(failure):
    turn = recorded_turn()
    sources = turn.reply.sources
    if failure == "missing":
        turn = changed(turn, ["reply", "sources"], [])
    elif failure == "duplicate":
        turn = changed(turn, ["reply", "sources"], [sources[0].model_dump()] * 2)
    elif failure == "unused":
        turn = changed(
            turn,
            ["reply", "sources"],
            [sources[0].model_dump(), label_source(PRODUCTS[1], LabelSection.USES)],
        )
    elif failure == "wrong_text":
        turn = changed(turn, ["reply", "sources", 0, "text"], "Different label text.")
    else:
        turn = changed(turn, ["reply", "blocks", 0, "source_id"], f"{PRODUCTS[0].sku}#uses")
    assert score([recorded_case(turn)])["grounded"] == 0


@pytest.mark.parametrize("kind", ["availability", "store_info", "order_status"])
@pytest.mark.parametrize(
    "failure", ["uncaptured", "missing_time", "naive_time", "different_payload"]
)
def test_api_citations_alone_cannot_prove_the_facts(kind, failure):
    turn = api_turn(kind)
    if failure == "uncaptured":
        turn = changed(turn, ["api_evidence"], {})
    elif failure == "different_payload":
        turn = changed(turn, ["api_evidence"], {turn.reply.sources[0].id: {"wrong": "value"}})
    else:
        stamp = None if failure == "missing_time" else "2026-01-01T00:00:00"
        turn = changed(turn, ["reply", "sources", 0, "retrieved_at"], stamp)
    assert score([recorded_case(turn)])["grounded"] == 0


@pytest.mark.parametrize("kind", ["availability", "order_status"])
def test_api_display_text_must_agree_with_the_structured_payload(kind):
    turn = api_turn(kind)
    path = ["reply", "blocks", 0, "text"]
    if kind == "availability":
        path = ["reply", "blocks", 0, "stores", 0, "text"]
    turn = changed(turn, path, "Incorrect displayed claim")
    assert score([recorded_case(turn)])["grounded"] == 0


def test_fact_free_replies_are_counted_apart_and_handoffs_are_explicitly_skipped():
    fixed = reply("fallback", [{"type": "text", "text": policy.FALLBACK_TEXT}], [])
    handoff = HandoffReply(
        ticket_id="TCK-1001", text=policy.HANDOFF_CREATED_TEXT.format(ticket_id="TCK-1001")
    )
    result = score([recorded_case(recorded_turn(reply=fixed), recorded_turn(reply=handoff))])
    assert result == {
        "grounded": 0,
        "factual": 0,
        "fact_free": 1,
        "rate": None,
        "failed_cases": {},
        "skipped_handoffs": 1,
    }
    assert score([])["rate"] is None


def test_fixed_risk_wording_and_the_complete_order_form_are_fact_free():
    forms = {
        "type": "order_form",
        "text": policy.ORDER_FORM_TEXT,
        "order_number_label": policy.ORDER_NUMBER_LABEL,
        "contact_label": policy.ORDER_CONTACT_LABEL,
        "submit_label": policy.ORDER_SUBMIT_LABEL,
    }
    emergency = reply("emergency", [{"type": "text", "text": policy.EMERGENCY_TEXT}], [])
    form = reply("order_form", [forms], [])
    result = score([recorded_case(recorded_turn(reply=emergency), recorded_turn(reply=form))])
    assert result["fact_free"] == 2 and result["factual"] == 0


def test_a_risk_reply_can_ground_its_label_alongside_fixed_policy_wording():
    original = recorded_turn().reply.model_dump()
    risk = {
        **original,
        "reply_type": "dosing_beyond_label",
        "blocks": [{"type": "text", "text": policy.DOSING_BEYOND_LABEL_TEXT}, *original["blocks"]],
    }
    turn = recorded_turn(reply=risk)
    assert score([recorded_case(turn)])["grounded"] == 1


@pytest.mark.parametrize("kind", ["label_sections", "fallback", "not_found", "order_form"])
def test_arbitrary_text_is_never_disguised_as_fact_free(kind):
    bad = reply(kind, [{"type": "text", "text": "An invented product fact."}], [])
    result = score([recorded_case(recorded_turn(reply=bad))])
    assert result["fact_free"] == 0 and result["factual"] == 1 and result["grounded"] == 0


def test_empty_factual_replies_and_facts_smuggled_into_a_fallback_fail():
    empty = reply("label_sections", [], [])
    smuggled = {**recorded_turn().reply.model_dump(), "reply_type": "fallback"}
    result = score([recorded_case(recorded_turn(reply=empty), recorded_turn(reply=smuggled))])
    assert result["factual"] == 2 and result["grounded"] == 0
