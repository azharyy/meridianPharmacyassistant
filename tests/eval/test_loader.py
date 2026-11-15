"""Evaluation case loading validates every action and reports safe line-numbered errors."""

import json

import pytest

from eval.loader import (
    ApiTimeoutAction,
    Case,
    ChatAction,
    HandoffAction,
    OrderFormAction,
    load_cases,
)

EXPECT = {"reply_type": "off_topic", "risk_label": "none", "handoff_offered": False}
CHAT = {"action": "chat", "message": "A synthetic shopper question?", "expect": EXPECT}


def case(**changes):
    return {"id": "case-001", "slice": "synthetic", "turns": [CHAT], **changes}


def write_cases(tmp_path, *records):
    path = tmp_path / "cases.jsonl"
    path.write_text("".join(json.dumps(record) + "\n" for record in records), encoding="utf-8")
    return path


def test_all_actions_load_and_roundtrip_with_defaults_and_document_data(tmp_path):
    record = case(
        turns=[
            {"action": "api_timeout", "enabled": True},
            CHAT,
            {
                "action": "order_form",
                "order_number": "MRD-ORD-48213",
                "contact": "synthetic@example.com",
                "expect": {
                    **EXPECT,
                    "reply_type": "order_status",
                    "tool": "lookup_order",
                    "gold_sources": ["api:orders"],
                    "must_contain": ["Items"],
                    "must_not_contain": ["Address"],
                },
            },
            {
                "action": "handoff",
                "confirmed": True,
                "expect": {
                    "reply_type": None,
                    "risk_label": None,
                    "handoff_offered": None,
                    "tool": "create_ticket",
                },
            },
        ],
        documents=[
            {
                "source_id": "policies/returns.md#returns",
                "title": "Returns",
                "text": "Data only.",
            }
        ],
    )
    [loaded] = load_cases(write_cases(tmp_path, record))
    assert [type(action) for action in loaded.turns] == [
        ApiTimeoutAction,
        ChatAction,
        OrderFormAction,
        HandoffAction,
    ]
    assert loaded.turns[1].store_id is None
    assert loaded.documents[0].text == "Data only."
    assert Case.model_validate_json(loaded.model_dump_json()) == loaded


def test_valid_cases_keep_order_and_store_ids(tmp_path):
    records = [
        case(turns=[{**CHAT, "store_id": "store-001"}]),
        case(id="case-002", slice="another"),
    ]
    loaded = load_cases(write_cases(tmp_path, *records))
    assert [record.id for record in loaded] == ["case-001", "case-002"]
    assert loaded[0].turns[0].store_id == "store-001"
    assert loaded[1].documents == []


@pytest.mark.parametrize(
    "invalid",
    [
        {},
        case(id=""),
        case(slice=""),
        case(turns=[]),
        case(unexpected="private@example.com"),
        case(documents=[{"source_id": "evil-doc", "title": "T", "text": "x"}]),
        case(documents=[{"source_id": "MRD-PAN-001#directions", "title": "T", "text": "x"}]),
        case(turns=[{**CHAT, "message": ""}]),
        case(turns=[{**CHAT, "message": "x" * 2001}]),
        case(turns=[{**CHAT, "store_id": "../orders"}]),
        case(turns=[{"action": "chat", "message": "No expectation"}]),
        case(turns=[{**CHAT, "expect": {}}]),
        case(turns=[{**CHAT, "expect": {**EXPECT, "reply_type": "invented"}}]),
        case(turns=[{**CHAT, "expect": {**EXPECT, "tool": "list_orders"}}]),
        case(turns=[{**CHAT, "expect": {**EXPECT, "gold_sources": ["private@example.com"]}}]),
        case(turns=[{**CHAT, "expect": {**EXPECT, "extra": "private@example.com"}}]),
        case(turns=[{**CHAT, "expect": {**EXPECT, "handoff_offered": "false"}}]),
        case(labeled=True),
        case(turns=[{"action": "invented", "message": "private@example.com"}]),
        case(turns=[{"action": "api_timeout", "enabled": True, "expect": EXPECT}]),
        case(turns=[{"action": "api_timeout"}]),
        case(turns=[{"action": "api_timeout", "enabled": "false"}]),
        case(turns=[{"action": "handoff", "confirmed": False, "expect": EXPECT}]),
        case(
            turns=[{"action": "order_form", "order_number": "", "contact": "a", "expect": EXPECT}]
        ),
        case(
            turns=[
                {"action": "order_form", "order_number": "x" * 65, "contact": "a", "expect": EXPECT}
            ]
        ),
        case(
            turns=[{"action": "order_form", "order_number": "a", "contact": "", "expect": EXPECT}]
        ),
        case(
            turns=[
                {
                    "action": "order_form",
                    "order_number": "a",
                    "contact": "x" * 255,
                    "expect": EXPECT,
                }
            ]
        ),
        case(documents=[{"source_id": "a", "title": "b", "text": "c", "extra": True}]),
    ],
)
def test_invalid_schema_reports_the_line_without_echoing_the_case(tmp_path, invalid):
    with pytest.raises(ValueError, match=r"^line 2: invalid case \(") as raised:
        load_cases(write_cases(tmp_path, case(), invalid))
    assert "private@example.com" not in str(raised.value)
    assert "synthetic" not in str(raised.value)


@pytest.mark.parametrize("bad_line", [b"{private@example.com", b"null", b"[]", b"\xff"])
def test_malformed_json_and_nonrecords_report_their_line_safely(tmp_path, bad_line):
    path = write_cases(tmp_path, case())
    with path.open("ab") as source:
        source.write(bad_line + b"\n")
    with pytest.raises(ValueError, match=r"^line 2: invalid case \(") as raised:
        load_cases(path)
    assert "private@example.com" not in str(raised.value)


def test_duplicate_ids_fail_on_the_duplicate_line_without_echoing_the_id(tmp_path):
    record = case(id="PRIVATE_CASE_ID")
    with pytest.raises(ValueError, match=r"^line 2: duplicate case id$") as raised:
        load_cases(write_cases(tmp_path, record, record))
    assert "PRIVATE_CASE_ID" not in str(raised.value)


@pytest.mark.parametrize("blank", ["\n", "  \t\n"])
def test_blank_json_lines_are_not_silently_skipped(tmp_path, blank):
    path = write_cases(tmp_path, case())
    with path.open("a", encoding="utf-8") as source:
        source.write(blank)
    with pytest.raises(ValueError, match=r"^line 2: blank JSON record$"):
        load_cases(path)


def test_empty_files_have_a_clear_first_line_error(tmp_path):
    with pytest.raises(ValueError, match=r"^line 1: empty case file$"):
        load_cases(write_cases(tmp_path))
