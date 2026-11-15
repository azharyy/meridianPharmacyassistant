"""Validate JSONL evaluation conversations without exposing their text in loader errors."""

from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, StrictBool, ValidationError

from contracts.base import Contract
from contracts.catalog import PolicyRecord
from contracts.chat import SourceId, StoreId
from contracts.taxonomy import ReplyType, RiskLabel


class Expectation(Contract):
    reply_type: ReplyType | None
    risk_label: RiskLabel | None
    handoff_offered: StrictBool | None
    gold_sources: list[SourceId] = Field(default_factory=list)
    must_contain: list[str] = Field(default_factory=list)
    must_not_contain: list[str] = Field(default_factory=list)
    tool: (
        Literal["check_availability", "get_store_info", "lookup_order", "create_ticket"] | None
    ) = None


class ChatAction(Contract):
    action: Literal["chat"]
    message: str = Field(min_length=1, max_length=2000)
    store_id: StoreId | None = None
    expect: Expectation


class OrderFormAction(Contract):
    action: Literal["order_form"]
    order_number: str = Field(min_length=1, max_length=64)
    contact: str = Field(min_length=1, max_length=254)
    expect: Expectation


class HandoffAction(Contract):
    action: Literal["handoff"]
    confirmed: Literal[True]
    expect: Expectation


class ApiTimeoutAction(Contract):
    action: Literal["api_timeout"]
    enabled: StrictBool


Action = Annotated[
    ChatAction | OrderFormAction | HandoffAction | ApiTimeoutAction,
    Field(discriminator="action"),
]


class Document(PolicyRecord):
    """A policy section planted for one case; a policy ID only, so it never replaces a label."""

    source_id: str = Field(pattern=r"^policies/[a-z0-9-]+\.md#[a-z0-9-]+$")


class Case(Contract):
    id: str = Field(min_length=1)
    slice: str = Field(min_length=1)
    turns: list[Action] = Field(min_length=1)
    documents: list[Document] = Field(default_factory=list)


def load_cases(path: Path) -> list[Case]:
    """Reject malformed, blank or duplicate records with a line number and no case text."""
    cases, seen = [], set()
    with path.open("rb") as source:
        for number, line in enumerate(source, 1):
            if not line.strip():
                raise ValueError(f"line {number}: blank JSON record")
            try:
                case = Case.model_validate_json(line)
            except ValidationError as error:
                kind = error.errors(include_input=False, include_context=False)[0]["type"]
                raise ValueError(f"line {number}: invalid case ({kind})") from None
            if case.id in seen:
                raise ValueError(f"line {number}: duplicate case id")
            seen.add(case.id)
            cases.append(case)
    if not cases:
        raise ValueError("line 1: empty case file")
    return cases
