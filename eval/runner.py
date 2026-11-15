"""Drive isolated evaluation conversations and retain their replies, evidence and stage traces."""

from contextlib import ExitStack
from dataclasses import replace
from hashlib import sha256
from typing import Literal

import httpx
from pydantic import Field

from assistant import escalation, pipeline
from assistant.api_client import connect
from assistant.app import default_steps
from assistant.llm import ModelClient, make_client
from assistant.session import Session
from assistant.settings import Settings, load_settings
from contracts.base import Contract
from contracts.catalog import PolicyRecord, ProductRecord
from contracts.chat import ChatReply, ChatRequest, HandoffReply, OrderFormRequest
from contracts.plan import CatalogPlan
from contracts.router import RouterOutput
from contracts.taxonomy import LabelSection, RiskLabel
from eval.loader import ApiTimeoutAction, Case, ChatAction, Expectation, OrderFormAction
from eval.tracing import capture_api


class RecordedTurn(Contract):
    action: Literal["chat", "order_form", "handoff"]
    question: str
    expect: Expectation
    reply: ChatReply | HandoffReply
    routed: RouterOutput | None = None
    retrieved: list[str] = Field(default_factory=list)
    plan: CatalogPlan | None = None
    requested_tool: str | None = None
    tools: list[str] = Field(default_factory=list)
    risk: RiskLabel = RiskLabel.NONE
    timings: dict[str, float] = Field(default_factory=dict)
    api_evidence: dict[str, dict] = Field(default_factory=dict)
    record_evidence: dict[str, str] = Field(default_factory=dict)  # cited ID: retrieved text
    product_names: dict[str, str] = Field(default_factory=dict)  # SKU: retrieved catalog name
    judge_correct: bool | None = None
    judge_error: str | None = None


class RecordedCase(Contract):
    id: str
    slice: str
    turns: list[RecordedTurn]


def with_documents(steps: pipeline.Steps, documents: list[PolicyRecord]) -> pipeline.Steps:
    """Add planted records after this case's results, without touching the shared index.

    Added after, so a one-record lookup of a named product still finds that product.
    """
    if not documents:
        return steps
    planted = {document.source_id: document for document in documents}

    def retrieve(query, k):
        found = steps.retrieve(query, k)
        remaining = [record for record in found if pipeline.record_id(record) not in planted]
        return [*remaining, *planted.values()]

    return replace(steps, retrieve=retrieve)


def with_record_capture(
    steps: pipeline.Steps, seen: dict[str, str], product_names: dict[str, str]
) -> pipeline.Steps:
    """Keep retrieved text and product names independently of the reply's displayed facts."""

    def retrieve(query, k):
        found = steps.retrieve(query, k)
        for record in found:
            if isinstance(record, ProductRecord):
                product_names[record.sku] = record.name
                seen.update(
                    {f"{record.sku}#{s.value}": getattr(record, s.value) for s in LabelSection}
                )
            else:
                seen[record.source_id] = record.text
        return found

    return replace(steps, retrieve=retrieve)


def run_action(action, session_id, session, steps, llm, http) -> RecordedTurn:
    if isinstance(action, ChatAction):
        result = pipeline.run_turn(
            ChatRequest(session_id=session_id, message=action.message, store_id=action.store_id),
            session,
            steps,
            llm,
            http,
        )
        requested = result.plan.tool if result.plan is not None else None
        return RecordedTurn(
            action=action.action,
            question=session.messages()[-1],
            expect=action.expect,
            reply=result.reply,
            routed=result.routed,
            retrieved=result.retrieved,
            plan=result.plan,
            requested_tool=requested.name.value if requested else None,
            risk=result.risk,
            timings=result.timings,
        )
    timings = {}
    if isinstance(action, OrderFormAction):
        request = OrderFormRequest(
            session_id=session_id, order_number=action.order_number, contact=action.contact
        )
        with pipeline.stage(timings, "order_form"):
            reply = pipeline.verify_order(request, session, steps, http)
        requested_tool = "lookup_order"
    else:
        with pipeline.stage(timings, "handoff"):
            reply = escalation.handoff(session_id, session, http)
        requested_tool = "create_ticket"
    return RecordedTurn(
        action=action.action,
        question="",
        expect=action.expect,
        reply=reply,
        requested_tool=requested_tool,
        timings=timings,
    )


def _run_case(
    case: Case, steps: pipeline.Steps, llm: ModelClient, http: httpx.Client
) -> RecordedCase:
    session = Session()
    session_id = f"eval-{sha256(case.id.encode()).hexdigest()[:32]}"
    seen: dict[str, str] = {}
    product_names: dict[str, str] = {}
    steps = with_record_capture(with_documents(steps, case.documents), seen, product_names)
    original_timeout = http.headers.get("X-Meridian-Test")
    turns = []
    try:
        with capture_api(http) as capture:
            for action in case.turns:
                if isinstance(action, ApiTimeoutAction):
                    if action.enabled:
                        http.headers["X-Meridian-Test"] = "timeout"
                    else:
                        http.headers.pop("X-Meridian-Test", None)
                    continue
                start = len(capture.calls)
                seen.clear()
                product_names.clear()
                turn = run_action(action, session_id, session, steps, llm, http)
                turn.tools = capture.calls[start:]
                sources = turn.reply.sources if isinstance(turn.reply, ChatReply) else []
                turn.api_evidence = {
                    source.id: capture.evidence[source.id]
                    for source in sources
                    if source.id in capture.evidence
                }
                turn.record_evidence = {s.id: seen[s.id] for s in sources if s.id in seen}
                turn.product_names = dict(product_names)
                turns.append(turn)
    finally:
        if original_timeout is None:
            http.headers.pop("X-Meridian-Test", None)
        else:
            http.headers["X-Meridian-Test"] = original_timeout
    print(f"{case.id} done", flush=True)  # a rate-limited live run is otherwise silent for minutes
    return RecordedCase(id=case.id, slice=case.slice, turns=turns)


def validate_cases(cases: list[Case]) -> None:
    """Reject missing labels before creating clients or making any request."""
    if not cases or any(
        all(isinstance(action, ApiTimeoutAction) for action in case.turns) for case in cases
    ):
        raise ValueError("evaluation cases must contain a scored response")
    expectations = (
        action.expect
        for case in cases
        for action in case.turns
        if isinstance(action, (ChatAction, OrderFormAction))
    )
    if any(
        expected.reply_type is None
        or expected.risk_label is None
        or expected.handoff_offered is None
        for expected in expectations
    ):
        raise ValueError("labeled chat and order forms need complete reply expectations")


def run_cases(
    cases: list[Case],
    settings: Settings | None = None,
    llm: ModelClient | None = None,
    http: httpx.Client | None = None,
    steps: pipeline.Steps | None = None,
) -> list[RecordedCase]:
    """Run labeled cases; close resources created here, never injected ones."""
    validate_cases(cases)
    settings = settings or load_settings()
    llm = llm or make_client(settings, settings.runtime)
    with ExitStack() as resources:
        if steps is None:
            steps, index = default_steps(settings)
            resources.callback(index.close)
        if http is None:
            http = connect(settings)
            resources.callback(http.close)
        return [_run_case(case, steps, llm, http) for case in cases]
