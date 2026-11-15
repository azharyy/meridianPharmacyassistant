"""A turn runs the eight steps in order; model failures give the fallback; logs hold no text."""

import logging

import httpx
import pytest

from assistant import pipeline
from assistant.llm import FakeSender, ModelClient, TransportError
from assistant.render import render_fallback
from assistant.session import Session
from assistant.settings import load_settings
from contracts.chat import ChatReply, ChatRequest
from contracts.taxonomy import RiskLabel
from tests.assistant.fixtures import PLAN, PRODUCTS, QUESTION, ROUTED, search

RUNTIME = load_settings({}).runtime
HTTP = httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(500)))
SESSION_ID = "session-0001"
STAGES = {
    "emergency",
    "redaction",
    "router",
    "retrieval",
    "catalog_agent",
    "review",
    "tool",
    "render",
}
EMERGENCY = ChatReply(
    reply_type="emergency",
    blocks=[{"type": "text", "text": "Call 911 now."}],
    sources=[],
    handoff_offered=True,
    emergency=True,
)


def turn(message: str, fake: FakeSender, steps=None, session=None) -> pipeline.TurnResult:
    request = ChatRequest(session_id=SESSION_ID, message=message)
    steps = steps or pipeline.Steps(retrieve=search)
    llm = ModelClient(RUNTIME, fake)
    return pipeline.run_turn(request, session or Session(), steps, llm, HTTP)


def test_a_turn_runs_the_eight_steps_top_to_bottom():
    calls = []

    def step(name, value):
        def run(*args):
            calls.append((name, args))
            return value

        return run

    reply = render_fallback()
    steps = pipeline.Steps(
        emergency=step("emergency", None),
        redact=step("redact", "redacted message"),
        route=step("route", ROUTED),
        retrieve=step("retrieve", PRODUCTS),
        plan=step("plan", PLAN),
        review=step("review", PLAN),
        execute=step("execute", None),
        render=step("render", reply),
    )
    llm = ModelClient(RUNTIME, FakeSender())
    request = ChatRequest(session_id=SESSION_ID, message="raw message")
    result = pipeline.run_turn(request, Session(), steps, llm, HTTP)
    names = ["emergency", "redact", "route", "retrieve", "plan", "review", "execute", "render"]
    assert [name for name, _ in calls] == names
    args = dict(calls)
    assert args["emergency"] == ("raw message",)
    assert args["route"] == (llm, ["redacted message"])
    assert args["retrieve"] == ("redacted message", pipeline.RETRIEVE_K)
    assert args["plan"] == (llm, "redacted message", PRODUCTS)
    assert args["review"] == (PLAN, PRODUCTS, RiskLabel.NONE)
    assert args["execute"] == (HTTP, None)
    assert args["render"] == (PLAN, PRODUCTS, RiskLabel.NONE, None)
    assert result.reply is reply
    assert set(result.timings) == STAGES


def test_an_emergency_reply_comes_before_any_model_call():
    fake = FakeSender([ROUTED, PLAN])
    steps = pipeline.Steps(emergency=lambda message: EMERGENCY, retrieve=search)
    result = turn("My son swallowed a bottle of pills", fake, steps)
    assert result.reply is EMERGENCY
    assert fake.requests == []
    assert set(result.timings) == {"emergency", "redaction"}


def test_a_directions_question_gets_the_label_text_and_its_source():
    result = turn(QUESTION, FakeSender([ROUTED, PLAN]))
    [block] = result.reply.blocks
    assert block.text == PRODUCTS[0].directions
    assert [source.id for source in result.reply.sources] == ["MRD-ALG-012#directions"]
    assert result.retrieved == ["MRD-ALG-012", "MRD-ALG-014"]
    assert (result.routed, result.plan, result.tool) == (ROUTED, PLAN, None)


@pytest.mark.parametrize(
    "script",
    [
        [TransportError("APITimeoutError")] * 2,
        [TransportError("RateLimitError")] * 2,
        ['{"intent": "invented"}', "not json"],
        [ROUTED, TransportError("APITimeoutError"), "{}"],
    ],
    ids=["timeout", "rate_limit", "invalid_after_retry", "catalog_agent_fails"],
)
def test_a_model_failure_gives_the_fallback_with_the_card(script):
    result = turn(QUESTION, FakeSender(script))
    assert result.reply == render_fallback()
    assert result.reply.handoff_offered is True


def test_a_rejected_plan_gives_the_fallback():
    steps = pipeline.Steps(retrieve=search, review=lambda plan, records, risk: None)
    assert turn(QUESTION, FakeSender([ROUTED, PLAN]), steps).reply == render_fallback()


def test_the_model_sees_only_the_redacted_message():
    fake = FakeSender([ROUTED, PLAN])
    turn("I'm sam@example.com, order MRD-ORD-48213. How do I take it?", fake)
    sent = str(fake.requests)
    assert "sam@example.com" not in sent and "MRD-ORD-48213" not in sent
    assert "[email]" in sent and "[order number]" in sent


def test_the_session_keeps_redacted_turns_and_the_router_sees_earlier_ones():
    session, fake = Session(), FakeSender([ROUTED, PLAN, ROUTED, PLAN])
    turn("I'm pregnant, my email is sam@example.com.", fake, session=session)
    turn(QUESTION, fake, session=session)
    assert session.messages() == ["I'm pregnant, my email is [email].", QUESTION]
    second_router_request = fake.requests[2][0][1]["content"]
    assert second_router_request == (
        f"Customer: I'm pregnant, my email is [email].\nCustomer: {QUESTION}"
    )


def test_logs_carry_the_session_and_timings_but_no_message_text(caplog):
    caplog.set_level(logging.INFO, logger="meridian")
    message = "I'm sam@example.com, phone 217-555-0142. How do I take it?"
    turn(message, FakeSender([ROUTED, PLAN]))
    turn(message, FakeSender())
    logged = "\n".join(record.getMessage() for record in caplog.records)
    assert logged.count(SESSION_ID) == 3  # two turns, one model-unavailable warning
    assert all(name in logged for name in STAGES)
    for private in ("sam@example.com", "217-555-0142", "How do I take it", "[email]"):
        assert private not in logged


def test_the_later_issues_steps_do_nothing_by_default():
    assert pipeline.no_emergency("help") is None
    assert pipeline.retrieve_nothing("anything", 5) == []
    assert pipeline.accept(PLAN, [], RiskLabel.NONE) is PLAN
    assert pipeline.no_tool(HTTP, None) is None
