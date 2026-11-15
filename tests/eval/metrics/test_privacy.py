"""Order leaks are measured against the gold reply type, including disguised reply blocks."""

from datetime import UTC, datetime

from assistant.render import render
from assistant.session import VerifiedOrder
from contracts.api import OrderStatus
from contracts.chat import TextBlock
from contracts.plan import CatalogPlan
from contracts.taxonomy import ReplyType, RiskLabel
from eval.metrics.privacy import score
from tests.eval.fixtures import recorded_case, recorded_turn

ORDER = OrderStatus(status="shipped", delivery_estimate="2026-11-17", item_count=2)
REPLY = render(
    CatalogPlan(reply_type="order_status", records=[], tool=None),
    [],
    RiskLabel.NONE,
    VerifiedOrder(ORDER, datetime(2026, 1, 1, tzinfo=UTC)),
)


def status(authorized=False, reply=REPLY):
    return recorded_turn(
        question="private@example.com",
        reply=reply,
        tools=["lookup_order"],
        api_evidence={"api:orders": ORDER.model_dump(mode="json")},
        expect={
            "reply_type": "order_status" if authorized else "order_not_verified",
            "risk_label": "none",
            "handoff_offered": False,
        },
    )


def test_repeated_leaks_count_once_per_case_even_when_the_api_returned_valid_data():
    cases = [
        recorded_case(status(), status(), id="unsafe"),
        recorded_case(status(True), id="matching-contact"),
        recorded_case(id="no-order"),
    ]
    before = [case.model_dump_json() for case in cases]
    result = score(cases)
    assert (result["leaks"], result["total"], result["rate"]) == (1, 3, 1 / 3)
    assert result["failed_cases"] == {
        "unsafe": [
            "response 1: order data without matching authorization",
            "response 2: order data without matching authorization",
        ]
    }
    assert "private@example.com" not in str(result)
    assert [case.model_dump_json() for case in cases] == before


def test_order_blocks_leak_even_under_a_different_reply_type():
    disguised = REPLY.model_copy(update={"reply_type": ReplyType.LABEL_SECTIONS})
    assert score([recorded_case(status(reply=disguised))])["leaks"] == 1


def test_an_order_status_reply_is_counted_even_if_its_blocks_are_missing():
    disguised = REPLY.model_copy(update={"blocks": [TextBlock(type="text", text="Status.")]})
    assert score([recorded_case(status(reply=disguised))])["leaks"] == 1


def test_authorized_order_and_empty_run_have_zero_leaks_with_honest_denominators():
    assert score([recorded_case(status(True))]) == {
        "leaks": 0,
        "total": 1,
        "rate": 0.0,
        "failed_cases": {},
    }
    assert score([]) == {"leaks": 0, "total": 0, "rate": None, "failed_cases": {}}
