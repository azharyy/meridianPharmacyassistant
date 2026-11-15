"""Run one chat turn: the plan's eight steps as plain functions, called top to bottom.

The only module that wires steps together. Each step comes in through `Steps`, with what it
depends on passed as arguments, so a test can swap any step without patching. Retrieval and the
tool executor still have do-nothing defaults here, behind the signatures issues 5 and 6 keep.

An emergency gets the 911 reply before any model call. After the router, the turn's risk label
is the most restrictive of the router's label and the injection rules'; any label but none gets
the reply the policy table fixes, and the catalog agent doesn't run.
"""

import logging
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field

import httpx

from assistant.catalog_agent import plan as make_plan
from assistant.llm import ModelClient, ModelUnavailable
from assistant.policy import POLICY, most_restrictive
from assistant.redaction import redact
from assistant.render import render as render_reply
from assistant.render import render_fallback, render_risk
from assistant.router import route
from assistant.safety.emergency import is_emergency
from assistant.safety.injection import looks_like_injection
from assistant.safety.reviewer import review
from assistant.session import Session, Turn
from contracts.api import Availability, StoreInfo
from contracts.catalog import PolicyRecord, ProductRecord
from contracts.chat import ChatReply, ChatRequest
from contracts.plan import AvailabilityRequest, CatalogPlan, StoreRequest
from contracts.router import RouterOutput
from contracts.taxonomy import ReplyType, RiskLabel

log = logging.getLogger("meridian.turn")
RETRIEVE_K = 5

Record = ProductRecord | PolicyRecord
ToolRequest = AvailabilityRequest | StoreRequest
ToolResult = Availability | StoreInfo | None


def retrieve_nothing(query: str, k: int) -> list[Record]:
    """Step 4 until issue 5: nothing is found. A retriever returns at most k whole records."""
    return []


def no_tool(http: httpx.Client, tool: ToolRequest | None) -> ToolResult:
    """Step 7 until issue 6: no tool runs. The executor returns the API's result or None."""
    return None


@dataclass(frozen=True)
class Steps:
    emergency: Callable[[str], bool] = is_emergency
    redact: Callable[[str], str] = redact
    route: Callable[[ModelClient, list[str]], RouterOutput] = route
    injection: Callable[[str], bool] = looks_like_injection
    retrieve: Callable[[str, int], list[Record]] = retrieve_nothing
    plan: Callable[[ModelClient, str, list[Record]], CatalogPlan] = make_plan
    review: Callable[[CatalogPlan, list[Record], RiskLabel], CatalogPlan | None] = review
    execute: Callable[[httpx.Client, ToolRequest | None], ToolResult] = no_tool
    render: Callable[[CatalogPlan, list[Record], RiskLabel, ToolResult], ChatReply] = render_reply
    render_risk: Callable[[RiskLabel, ProductRecord | None], ChatReply] = render_risk
    fallback: Callable[[], ChatReply] = render_fallback


@dataclass
class TurnResult:
    """The reply, and what the eval records about how the turn reached it."""

    reply: ChatReply
    routed: RouterOutput | None = None
    retrieved: list[str] = field(default_factory=list)  # record IDs, in retrieval order
    plan: CatalogPlan | None = None
    tool: str | None = None
    risk: RiskLabel = RiskLabel.NONE
    timings: dict[str, float] = field(default_factory=dict)  # milliseconds per stage


@contextmanager
def stage(timings: dict[str, float], name: str) -> Iterator[None]:
    start = time.perf_counter()
    try:
        yield
    finally:
        timings[name] = round((time.perf_counter() - start) * 1000, 2)


def record_id(record: Record) -> str:
    return record.sku if isinstance(record, ProductRecord) else record.source_id


def named_product(routed: RouterOutput, steps: Steps, timings) -> ProductRecord | None:
    """The first product the customer named, as retrieval finds it."""
    if not routed.product_mentions:
        return None
    with stage(timings, "retrieval"):
        found = steps.retrieve(routed.product_mentions[0], 1)
    return next((record for record in found if isinstance(record, ProductRecord)), None)


def risk_reply(routed: RouterOutput | None, risk: RiskLabel, steps: Steps, timings) -> TurnResult:
    """The policy table's reply for a risk label other than none."""
    shows_a_label = routed is not None and bool(POLICY[risk].sections)
    product = named_product(routed, steps, timings) if shows_a_label else None
    with stage(timings, "render"):
        reply = steps.render_risk(risk, product)
    return TurnResult(reply, routed, [product.sku] if product else [], risk=risk)


def answer(
    session_id: str, message: str, session: Session, steps: Steps, llm: ModelClient, http, timings
) -> TurnResult:
    """Steps 3 to 8, for a message the emergency rules let through."""
    with stage(timings, "router"):
        routed = steps.route(llm, [*session.messages(), message])
    risk = routed.risk_label
    if steps.injection(message):
        log.warning("prompt injection session=%s", session_id)
        risk = most_restrictive(risk, RiskLabel.PROMPT_INJECTION)
    if risk is not RiskLabel.NONE:
        return risk_reply(routed, risk, steps, timings)
    with stage(timings, "retrieval"):
        records = steps.retrieve(message, RETRIEVE_K)
    with stage(timings, "catalog_agent"):
        plan = steps.plan(llm, message, records)
    with stage(timings, "review"):
        reviewed = steps.review(plan, records, risk)
    found = [record_id(record) for record in records]
    if reviewed is None:
        return TurnResult(steps.fallback(), routed, found, plan, risk=risk)
    with stage(timings, "tool"):
        tool_result = steps.execute(http, reviewed.tool)
    with stage(timings, "render"):
        reply = steps.render(reviewed, records, risk, tool_result)
    tool = reviewed.tool.name.value if reviewed.tool else None
    return TurnResult(reply, routed, found, reviewed, tool, risk)


def record_offer(session: Session, result: TurnResult) -> None:
    """The card on this reply becomes the session's current offer; a reply without one clears it."""
    if not result.reply.handoff_offered:
        session.handoff_offer = None
        return
    reason = "fallback" if result.reply.reply_type is ReplyType.FALLBACK else "risk"
    session.offer_handoff(result.risk, reason)


def run_turn(
    request: ChatRequest, session: Session, steps: Steps, llm: ModelClient, http: httpx.Client
) -> TurnResult:
    """One customer message, steps 1 to 8. The 911 reply comes before any model call."""
    timings: dict[str, float] = {}
    with stage(timings, "emergency"):
        emergency = steps.emergency(request.message)
    with stage(timings, "redaction"):
        message = steps.redact(request.message)
    if emergency:
        result = risk_reply(None, RiskLabel.EMERGENCY, steps, timings)
    else:
        try:
            result = answer(request.session_id, message, session, steps, llm, http, timings)
        except ModelUnavailable as error:
            log.warning("model unavailable session=%s: %s", request.session_id, error)
            result = TurnResult(steps.fallback())
    result.timings = timings
    record_offer(session, result)
    session.add(Turn(message=message, reply=result.reply, routed=result.routed))
    log.info("turn session=%s reply=%s ms=%s", request.session_id, result.reply.reply_type, timings)
    return result
