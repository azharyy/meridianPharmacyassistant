"""Order verification retains status only and clears old verification on every failure."""

import json
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from threading import Event

import httpx
import pytest

from assistant.orders import verify
from assistant.session import Session, VerifiedOrder
from contracts.api import OrderStatus
from contracts.chat import OrderFormRequest

FORM = OrderFormRequest(
    session_id="session-0001", order_number="MRD-ORD-48213", contact="maria.garcia@example.com"
)
STATUS = OrderStatus(status="shipped", delivery_estimate="2026-11-17", item_count=2)
OLD_ORDER = VerifiedOrder(STATUS, datetime(2026, 1, 1, tzinfo=UTC))


def api(answer):
    seen = []

    def handle(request):
        seen.append(request)
        if isinstance(answer, Exception):
            raise answer
        return answer

    return httpx.Client(base_url="http://api.test", transport=httpx.MockTransport(handle)), seen


def test_matching_form_is_forwarded_once_and_keeps_only_status_and_call_time(caplog):
    http, seen = api(httpx.Response(200, json=STATUS.model_dump(mode="json")))
    session = Session(verified_order=OLD_ORDER)
    before = datetime.now(UTC)
    result = verify(FORM, session, http)
    assert result is session.verified_order and result is not OLD_ORDER
    assert result.status == STATUS and before <= result.checked_at <= datetime.now(UTC)
    assert result.checked_at.utcoffset().total_seconds() == 0
    [sent] = seen
    assert (sent.method, sent.url.path) == ("POST", "/v1/orders/lookup")
    assert json.loads(sent.content) == {
        "order_number": FORM.order_number,
        "contact": FORM.contact,
    }
    assert FORM.order_number not in repr(session) + caplog.text
    assert FORM.contact not in repr(session) + caplog.text
    assert session.turns == []


@pytest.mark.parametrize(
    "form",
    [
        FORM.model_copy(update={"contact": "another.customer@example.org"}),
        FORM.model_copy(update={"order_number": "MRD-ORD-48231"}),
        FORM.model_copy(update={"order_number": "MRD-ORD-99999"}),
    ],
    ids=["wrong_contact", "someone_elses_order", "unknown_order"],
)
def test_every_mismatch_clears_the_previous_order(form):
    http, seen = api(httpx.Response(404, json={"detail": "not_found"}))
    session = Session(verified_order=OLD_ORDER)
    assert verify(form, session, http) is None
    assert session.verified_order is None and len(seen) == 1


@pytest.mark.parametrize(
    "answer",
    [
        httpx.ReadTimeout("timed out"),
        httpx.Response(504, json={"detail": "timeout"}),
        httpx.Response(429, json={"detail": "locked"}),
        httpx.Response(200, json={**STATUS.model_dump(mode="json"), "address": "Private Lane"}),
        httpx.Response(200, json={**STATUS.model_dump(mode="json"), "items": ["Private item"]}),
        httpx.Response(200, json={"status": "invented"}),
    ],
    ids=["transport_timeout", "api_timeout", "lockout", "address", "item_names", "invalid_status"],
)
def test_timeout_lockout_and_malformed_status_clear_the_order_without_retry(answer, caplog):
    http, seen = api(answer)
    session = Session(verified_order=OLD_ORDER)
    assert verify(FORM, session, http) is None
    assert session.verified_order is None and len(seen) == 1
    assert FORM.order_number not in repr(session) + caplog.text
    assert FORM.contact not in repr(session) + caplog.text


@pytest.mark.parametrize("failure_status", [404, 504], ids=["wrong_contact", "timeout"])
def test_a_failed_lookup_never_returns_an_overlapping_success(failure_status):
    failed_started, finish_failure = Event(), Event()

    def handle(request):
        if json.loads(request.content)["contact"] != FORM.contact:
            failed_started.set()
            assert finish_failure.wait(5)
            return httpx.Response(failure_status, json={"detail": "not_found"})
        return httpx.Response(200, json=STATUS.model_dump(mode="json"))

    http = httpx.Client(base_url="http://api.test", transport=httpx.MockTransport(handle))
    session = Session(verified_order=OLD_ORDER)
    wrong = FORM.model_copy(update={"contact": "another.customer@example.org"})
    with ThreadPoolExecutor(max_workers=2) as pool:
        failed = pool.submit(verify, wrong, session, http)
        try:
            assert failed_started.wait(5)
            matched = verify(FORM, session, http)
            assert matched is not None and matched.status == STATUS
            assert session.verified_order is matched
        finally:
            finish_failure.set()
        assert failed.result(timeout=5) is None
    assert session.verified_order is None
