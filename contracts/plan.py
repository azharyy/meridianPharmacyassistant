"""Describe a catalog plan using evidence references and one optional tool."""

from typing import Literal

from contracts.base import Contract
from contracts.taxonomy import LabelSection, ReplyType, ToolName


class RecordSelection(Contract):
    record_id: str
    # Policy records already identify one section; their sections list is empty.
    sections: list[LabelSection]


class AvailabilityRequest(Contract):
    name: Literal[ToolName.CHECK_AVAILABILITY]
    sku: str


class StoreRequest(Contract):
    name: Literal[ToolName.GET_STORE_INFO]
    store_id: str


class CatalogPlan(Contract):
    reply_type: ReplyType
    records: list[RecordSelection]
    tool: AvailabilityRequest | StoreRequest | None
