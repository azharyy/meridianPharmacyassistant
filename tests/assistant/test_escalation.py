"""The pharmacist handoff: one ticket per offer, a summary built by code with no contact details."""

import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier, Event
from uuid import uuid4

import httpx
import pytest
from fastapi.testclient import TestClient

from api.app import create_app as create_api
from assistant import pipeline
from assistant.escalation import STALE, handoff, summarize
from assistant.llm import FakeSender, ModelClient
from assistant.policy import HANDOFF_CREATED_TEXT, HANDOFF_FAILED_TEXT, HANDOFF_STALE_TEXT
from assistant.render import render_risk
from assistant.session import Session, Turn
from assistant.settings import load_settings
from contracts.chat import ChatRequest
from contracts.taxonomy import RiskLabel
from tests.assistant.fixtures import PRODUCTS, ROUTED, search

DATA = Path(__file__).resolve().parents[2] / "data"
STAFF = "test-staff-key"
SESSION_ID = "session-0001"
RUNTIME = load_settings({}).runtime
MEDICAL = ROUTED.model_copy(update={"risk_label": RiskLabel.MEDICAL_ADVICE})
QUESTION = "I'm pregnant, my email is [email]. Can I take Meridian All Day Allergy?"


def mock_api() -> TestClient:
    """The real mock API, in process."""
    return TestClient(create_api(DATA, staff_key=STAFF))


def medical_session() -> Session:
    session = Session()
    session.add(Turn(QUESTION, render_risk(RiskLabel.MEDICAL_ADVICE, PRODUCTS[0]), MEDICAL))
    session.offer_handoff(RiskLabel.MEDICAL_ADVICE, "risk")
    return session


def recorded_keys(api: httpx.Client) -> list[str]:
    """The idempotency key of every ticket request the client sends from now on."""
    keys: list[str] = []
    api.event_hooks["request"].append(
        lambda request: keys.append(json.loads(request.content)["idempotency_key"])
    )
    return keys


def test_confirming_creates_exactly_one_ticket_and_a_repeat_returns_it():
    api, session = mock_api(), medical_session()
    keys, card = recorded_keys(api), session.handoff_offer.id
    first, again = handoff(SESSION_ID, session, api, card), handoff(SESSION_ID, session, api, card)
    assert first == again
    assert first.ticket_id == "TCK-1001"
    assert first.text == HANDOFF_CREATED_TEXT.format(ticket_id="TCK-1001")
    assert api.app.state.desks.tickets.count() == 1
    assert keys == [f"{SESSION_ID}:{card}"]  # the repeat is answered without a second request


def test_simultaneous_header_confirmations_create_one_offer_and_ticket():
    ready = Barrier(2)

    class SimultaneousSession(Session):
        def confirm_offer(self, offer_id):
            # Both confirmations reach allocation before either can create an offer.
            ready.wait(timeout=5)
            return super().confirm_offer(offer_id)

    session, api = SimultaneousSession(), mock_api()
    with ThreadPoolExecutor(max_workers=2) as pool:
        pending = [pool.submit(handoff, SESSION_ID, session, api) for _ in range(2)]
        replies = [future.result(timeout=10) for future in pending]
    assert replies[0] == replies[1]
    assert api.app.state.desks.tickets.count() == 1  # a second offer would have its own key


def test_an_old_or_unknown_card_files_nothing_and_allocates_no_offer():
    calls = []

    def record(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(500)

    api = httpx.Client(transport=httpx.MockTransport(record))
    session = medical_session()
    old = session.handoff_offer
    current = session.offer_handoff(RiskLabel.NONE, "fallback")
    for offer_id in (old.id, str(uuid4())):
        assert handoff(SESSION_ID, session, api, offer_id) == STALE
    empty = Session()
    assert handoff(SESSION_ID, empty, api, old.id) == STALE
    assert calls == [] and empty.handoff_offer is None and session.handoff_offer is current
    assert (old.ticket_id, current.ticket_id) == (None, None)
    assert (STALE.ticket_id, STALE.text) == (None, HANDOFF_STALE_TEXT)


def test_simultaneous_confirmations_of_a_card_return_one_ticket():
    session, api, ready = medical_session(), mock_api(), Barrier(8)
    keys, card = recorded_keys(api), session.handoff_offer.id

    def confirm():
        ready.wait(timeout=5)
        return handoff(SESSION_ID, session, api, card)

    with ThreadPoolExecutor(max_workers=8) as pool:
        replies = list(pool.map(lambda _: confirm(), range(8)))
    assert len({reply.ticket_id for reply in replies}) == 1
    assert api.app.state.desks.tickets.count() == 1
    assert keys and set(keys) == {f"{SESSION_ID}:{card}"}  # racing requests share one key


def test_an_emergency_does_not_wait_for_a_ticket_in_flight_and_the_ticket_keeps_its_card():
    entered, release, session, sent = Event(), Event(), medical_session(), []
    card = session.handoff_offer.id

    def slow_ticket(request):
        sent.append(json.loads(request.content))
        entered.set()
        assert release.wait(timeout=5)
        return httpx.Response(201, json={"ticket_id": "TCK-1001"})

    api = httpx.Client(base_url="http://api.test", transport=httpx.MockTransport(slow_ticket))
    fake = FakeSender()
    request = ChatRequest(session_id=SESSION_ID, message="I cannot breathe")
    with ThreadPoolExecutor(max_workers=2) as pool:
        ticket = pool.submit(handoff, SESSION_ID, session, api, card)
        try:
            assert entered.wait(timeout=5)
            emergency = pool.submit(
                pipeline.run_turn,
                request,
                session,
                pipeline.Steps(),
                ModelClient(RUNTIME, fake),
                api,
            ).result(timeout=2)  # no lock is held across the ticket call
            assert emergency.reply.emergency and fake.requests == []
        finally:
            release.set()
        assert ticket.result(timeout=5).ticket_id == "TCK-1001"
    [body] = sent  # the confirmation files the card it captured, not the newer emergency card
    summary = body["summary"]
    assert body["idempotency_key"] == f"{SESSION_ID}:{card}"
    assert (summary["risk_label"], summary["urgency"]) == ("medical_advice", "urgent")
    assert emergency.reply.offer_id == session.handoff_offer.id != card
    assert session.handoff_offer.risk_label is RiskLabel.EMERGENCY


def test_a_new_offer_gets_a_new_ticket():
    api, session = mock_api(), medical_session()
    first = handoff(SESSION_ID, session, api)
    session.offer_handoff(RiskLabel.PRESCRIPTION, "risk")
    second = handoff(SESSION_ID, session, api)
    assert (first.ticket_id, second.ticket_id) == ("TCK-1001", "TCK-1002")


def test_the_header_button_with_no_offer_makes_a_ticket_requested_by_the_customer():
    api = mock_api()
    reply = handoff(SESSION_ID, Session(), api)
    read = api.get(f"/v1/tickets/{reply.ticket_id}", headers={"X-Staff-Key": STAFF}).json()
    summary = read["summary"]
    assert (summary["reason"], summary["risk_label"], summary["urgency"]) == (
        "customer_requested",
        "none",
        "routine",
    )


def test_a_failed_creation_says_so_and_the_retry_reuses_the_same_key():
    sent = []
    answers = [
        httpx.Response(504, json={"detail": "timeout"}),
        httpx.Response(201, json={"ticket_id": "TCK-1001"}),
    ]

    def handle(request: httpx.Request) -> httpx.Response:
        sent.append(json.loads(request.content))
        return answers.pop(0)

    api = httpx.Client(base_url="http://api.test", transport=httpx.MockTransport(handle))
    session = medical_session()
    card = session.handoff_offer.id
    failed = handoff(SESSION_ID, session, api, card)
    assert (failed.ticket_id, failed.text) == (None, HANDOFF_FAILED_TEXT)
    assert handoff(SESSION_ID, session, api, card).ticket_id == "TCK-1001"
    assert [body["idempotency_key"] for body in sent] == [f"{SESSION_ID}:{card}"] * 2


def test_a_retry_after_a_lost_response_gets_the_ticket_already_made():
    desk, session, keys = mock_api(), medical_session(), []

    def lose_the_first_response(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        keys.append(body["idempotency_key"])
        made = desk.post("/v1/tickets", json=body)  # the ticket exists even when its reply is lost
        return httpx.Response(504) if len(keys) == 1 else httpx.Response(201, json=made.json())

    api = httpx.Client(
        base_url="http://api.test", transport=httpx.MockTransport(lose_the_first_response)
    )
    card = session.handoff_offer.id
    assert handoff(SESSION_ID, session, api, card).text == HANDOFF_FAILED_TEXT
    assert handoff(SESSION_ID, session, api, card).ticket_id == "TCK-1001"
    assert keys == [f"{SESSION_ID}:{card}"] * 2
    assert desk.app.state.desks.tickets.count() == 1


def test_a_retry_of_a_superseded_card_files_neither_card():
    keys = []

    def down(request: httpx.Request) -> httpx.Response:
        keys.append(json.loads(request.content)["idempotency_key"])
        return httpx.Response(504, json={"detail": "timeout"})

    api = httpx.Client(base_url="http://api.test", transport=httpx.MockTransport(down))
    session = medical_session()
    old = session.handoff_offer
    assert handoff(SESSION_ID, session, api, old.id).text == HANDOFF_FAILED_TEXT
    newer = session.offer_handoff(RiskLabel.PRESCRIPTION, "risk")
    assert handoff(SESSION_ID, session, api, old.id) == STALE
    assert keys == [f"{SESSION_ID}:{old.id}"]  # the stale retry sent no request
    assert newer.ticket_id is None and session.handoff_offer is newer


def test_the_summary_holds_every_field():
    session = medical_session()
    assert summarize(session, session.handoff_offer).model_dump(mode="json") == {
        "risk_label": "medical_advice",
        "urgency": "urgent",
        "customer_messages": [QUESTION],
        "product_mentions": ["Meridian All Day Allergy"],
        "assistant_replies": ["medical_advice (MRD-ALG-012#warnings)"],
        "reason": "risk",
    }


@pytest.mark.parametrize(
    ("risk", "urgency"),
    [
        (RiskLabel.EMERGENCY, "emergency"),
        (RiskLabel.DOSING_BEYOND_LABEL, "urgent"),
        (RiskLabel.PRESCRIPTION, "routine"),
        (RiskLabel.PROMPT_INJECTION, "routine"),
    ],
)
def test_urgency_follows_the_risk_label(risk, urgency):
    session = Session()
    assert summarize(session, session.offer_handoff(risk, "risk")).urgency == urgency


@pytest.mark.parametrize(
    "phone",
    [
        "(217) 555-0142",
        "217 / 555 / 0110",
        "(217) 555 - 0110",
        "+44 20 7946 0958",
        "+44 (0)20 7946 0958",
        "0044 20 7946 0958",
        "555-0142",
    ],
)
def test_no_contact_detail_reaches_a_summary(phone):
    session, steps = Session(), pipeline.Steps(retrieve=search)
    for message in (
        f"I'm sam@example.com, phone {phone}, order MRD-ORD-48213.",
        "Can I take Meridian All Day Allergy while pregnant?",
    ):
        llm = ModelClient(RUNTIME, FakeSender([MEDICAL]))
        request = ChatRequest(session_id=SESSION_ID, message=message)
        pipeline.run_turn(request, session, steps, llm, httpx.Client())
    text = summarize(session, session.handoff_offer).model_dump_json()
    for private in ("sam@example.com", phone, "MRD-ORD-48213"):
        assert private not in text
    assert all(placeholder in text for placeholder in ("[email]", "[phone]", "[order number]"))
