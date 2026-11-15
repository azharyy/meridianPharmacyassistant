"""The pharmacist handoff: one ticket per offer, a summary built by code with no contact details."""

import json
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from api.app import create_app as create_api
from assistant import pipeline
from assistant.escalation import handoff, summarize
from assistant.llm import FakeSender, ModelClient
from assistant.policy import HANDOFF_CREATED_TEXT, HANDOFF_FAILED_TEXT
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


def test_confirming_creates_exactly_one_ticket_and_a_repeat_returns_it():
    api, session = mock_api(), medical_session()
    first, again = handoff(SESSION_ID, session, api), handoff(SESSION_ID, session, api)
    assert first == again
    assert first.ticket_id == "TCK-1001"
    assert first.text == HANDOFF_CREATED_TEXT.format(ticket_id="TCK-1001")
    assert api.app.state.desks.tickets.count() == 1


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
    failed = handoff(SESSION_ID, session, api)
    assert (failed.ticket_id, failed.text) == (None, HANDOFF_FAILED_TEXT)
    assert handoff(SESSION_ID, session, api).ticket_id == "TCK-1001"
    assert [body["idempotency_key"] for body in sent] == [f"{SESSION_ID}:1"] * 2


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


def test_no_contact_detail_reaches_a_summary():
    session, steps = Session(), pipeline.Steps(retrieve=search)
    for message in (
        "I'm sam@example.com, phone (217) 555-0142, order MRD-ORD-48213.",
        "Can I take Meridian All Day Allergy while pregnant?",
    ):
        llm = ModelClient(RUNTIME, FakeSender([MEDICAL]))
        request = ChatRequest(session_id=SESSION_ID, message=message)
        pipeline.run_turn(request, session, steps, llm, httpx.Client())
    text = summarize(session, session.handoff_offer).model_dump_json()
    for private in ("sam@example.com", "555-0142", "MRD-ORD-48213"):
        assert private not in text
    assert all(placeholder in text for placeholder in ("[email]", "[phone]", "[order number]"))
