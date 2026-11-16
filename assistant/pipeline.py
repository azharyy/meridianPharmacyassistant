"""Run one chat turn: the plan's eight steps as plain functions, called top to bottom.

The only module that wires steps together. Each step comes in through `Steps`, with what it
depends on passed as arguments, so a test can swap any step without patching. The app binds
the startup retriever and the tool executor's trusted identities.

An emergency gets the 911 reply before any model call. After the router, the turn's risk label
is the most restrictive of the router's label and the injection rules'; any label but none gets
the reply the policy table fixes, and the catalog agent doesn't run.
"""

import hmac
import logging
import secrets
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from hashlib import sha256

import httpx

from assistant import orders
from assistant.catalog_agent import plan as make_plan
from assistant.llm import CONVERSATION, ModelClient, ModelUnavailable
from assistant.policy import POLICY, most_restrictive
from assistant.redaction import NUMBER, ORDER_NUMBER, redact
from assistant.render import render as render_reply
from assistant.render import render_fallback, render_fixed, render_risk
from assistant.router import route
from assistant.safety.emergency import is_emergency
from assistant.safety.injection import looks_like_injection
from assistant.safety.reviewer import review
from assistant.session import Session, Turn, VerifiedOrder
from assistant.tools import ToolRequest, ToolResult, allowed, execute
from contracts.catalog import PolicyRecord, ProductRecord
from contracts.chat import ChatReply, ChatRequest, OrderFormRequest
from contracts.plan import CatalogPlan, StoreRequest
from contracts.router import RouterOutput
from contracts.taxonomy import Intent, ReplyType, RiskLabel, ToolName

log = logging.getLogger("meridian.turn")
LOG_KEY = secrets.token_bytes(32)  # per process: a session ID can't be found from its reference
RETRIEVE_K = 5

Record = ProductRecord | PolicyRecord


def retrieve_nothing(query: str, k: int) -> list[Record]:
    """Step 4 until issue 5: nothing is found. A retriever returns at most k whole records."""
    return []


def find_nothing(name: str) -> ProductRecord | None:
    """No catalog bound: nothing is named."""
    return None


@dataclass(frozen=True)
class Steps:
    emergency: Callable[[str], bool] = is_emergency
    redact: Callable[[str], str] = redact
    route: Callable[[ModelClient, list[str]], RouterOutput] = route
    injection: Callable[[str], bool] = looks_like_injection
    retrieve: Callable[[str, int], list[Record]] = retrieve_nothing
    find_product: Callable[[str], ProductRecord | None] = find_nothing
    plan: Callable[[ModelClient, str, list[Record]], CatalogPlan] = make_plan
    review: Callable[[CatalogPlan, list[Record], RiskLabel], CatalogPlan | None] = review
    execute: Callable[[httpx.Client, ToolRequest | None], ToolResult] = execute
    render: Callable[
        [CatalogPlan, list[Record], RiskLabel, ToolResult | VerifiedOrder], ChatReply
    ] = render_reply
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
    """One product the customer named, matched exactly: a keyword hit could be another
    product whose label merely mentions a medicine outside the catalog."""
    if not routed.product_mentions:
        return None
    with stage(timings, "retrieval"):
        return steps.find_product(" ".join(routed.product_mentions))


def risk_reply(routed: RouterOutput | None, risk: RiskLabel, steps: Steps, timings) -> TurnResult:
    """The policy table's reply for a risk label other than none."""
    shows_a_label = routed is not None and bool(POLICY[risk].sections)
    product = named_product(routed, steps, timings) if shows_a_label else None
    with stage(timings, "render"):
        reply = steps.render_risk(risk, product)
    return TurnResult(reply, routed, [product.sku] if product else [], risk=risk)


def answer(
    log_id: str,
    message: str,
    session: Session,
    steps: Steps,
    llm: ModelClient,
    http,
    timings,
    store_id: str | None = None,
) -> TurnResult:
    """Steps 3 to 8, for a message the emergency rules let through."""
    with stage(timings, "router"):
        routed = steps.route(llm, [*session.messages(), message])
    risk = routed.risk_label
    if steps.injection(message):
        log.warning("prompt injection session=%s", log_id)
        risk = most_restrictive(risk, RiskLabel.PROMPT_INJECTION)
    if risk is not RiskLabel.NONE:
        return risk_reply(routed, risk, steps, timings)
    if routed.intent is Intent.ORDER_STATUS:
        # A typed number may name another order than the verified one, so it gets the form.
        typed = ORDER_NUMBER in message or NUMBER in message
        verified = None if typed else session.verified_order
        reply_type = ReplyType.ORDER_STATUS if verified else ReplyType.ORDER_FORM
        plan = CatalogPlan(reply_type=reply_type, records=[], tool=None)
        with stage(timings, "render"):
            reply = steps.render(plan, [], risk, verified)
        return TurnResult(reply, routed, plan=plan)
    if routed.intent is Intent.STORE_INFO:
        plan = CatalogPlan(
            reply_type=ReplyType.STORE_INFO,
            records=[],
            tool=StoreRequest(name=ToolName.GET_STORE_INFO, store_id=store_id or ""),
        )
        return fulfill(routed, plan, [], steps, http, timings)
    with stage(timings, "retrieval"):
        query = steps.redact(" ".join([*routed.product_mentions, message]))
        records = steps.retrieve(query, RETRIEVE_K)
    with stage(timings, "catalog_agent"):
        plan = steps.plan(llm, message, records)
    return fulfill(routed, plan, records, steps, http, timings)


def fulfill(routed, plan: CatalogPlan, records: list[Record], steps: Steps, http, timings):
    """Review a public answer plan, authorize its tool and render the resulting evidence."""
    risk = routed.risk_label
    with stage(timings, "review"):
        reviewed = steps.review(plan, records, risk)
    found = [record_id(record) for record in records]
    if reviewed is None:
        return TurnResult(steps.fallback(), routed, found, plan, risk=risk)
    if not allowed(routed.intent, reviewed.tool):
        reply = render_fixed(ReplyType.LOOKUP_FAILED)
        return TurnResult(reply, routed, found, reviewed, risk=risk)
    with stage(timings, "tool"):
        tool_result = steps.execute(http, reviewed.tool)
    with stage(timings, "render"):
        reply = steps.render(reviewed, records, risk, tool_result)
    tool = reviewed.tool.name.value if reviewed.tool else None
    return TurnResult(reply, routed, found, reviewed, tool, risk)


def record_offer(session: Session, reply: ChatReply, risk: RiskLabel) -> ChatReply:
    """The card on this reply becomes the session's current offer, and the reply carries that
    offer's ID, so its Confirm files exactly this offer. A reply without a card keeps the
    earlier offer confirmable; a newer card retires it."""
    if not reply.handoff_offered:
        return reply
    reason = "fallback" if reply.reply_type is ReplyType.FALLBACK else "risk"
    return reply.model_copy(update={"offer_id": session.offer_handoff(risk, reason).id})


def verify_order(
    request: OrderFormRequest, session: Session, steps: Steps, http: httpx.Client
) -> ChatReply:
    """The private form bypasses models and renders only the API-verified status or failure."""
    verified = orders.verify(request, session, http)
    reply_type = ReplyType.ORDER_STATUS if verified is not None else ReplyType.ORDER_NOT_VERIFIED
    plan = CatalogPlan(reply_type=reply_type, records=[], tool=None)
    reply = steps.render(plan, [], RiskLabel.NONE, verified)
    return record_offer(session, reply, RiskLabel.NONE)


def log_reference(session_id: str) -> str:
    """The session as logs name it: stable per process, and not reversible by hashing guesses."""
    return hmac.new(LOG_KEY, session_id.encode(), sha256).hexdigest()


def run_turn(
    request: ChatRequest, session: Session, steps: Steps, llm: ModelClient, http: httpx.Client
) -> TurnResult:
    """One customer message, steps 1 to 8. The 911 reply comes before any model call."""
    timings: dict[str, float] = {}
    log_id = log_reference(request.session_id)
    with stage(timings, "emergency"):
        emergency = steps.emergency(request.message)
    with stage(timings, "redaction"):
        message = steps.redact(request.message)
    if emergency:
        result = risk_reply(None, RiskLabel.EMERGENCY, steps, timings)
    else:
        conversation = CONVERSATION.set(log_id)  # every model call of this session shares it
        try:
            result = answer(log_id, message, session, steps, llm, http, timings, request.store_id)
        except ModelUnavailable as error:
            log.warning("model unavailable session=%s: %s", log_id, error)
            result = TurnResult(steps.fallback())
        finally:
            CONVERSATION.reset(conversation)
    result.timings = timings
    result.reply = record_offer(session, result.reply, result.risk)
    session.add(Turn(message=message, reply=result.reply, routed=result.routed))
    log.info("turn session=%s reply=%s ms=%s", log_id, result.reply.reply_type, timings)
    return result
