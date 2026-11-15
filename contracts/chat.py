"""Define the assistant's HTTP requests and nine renderable reply blocks."""

from datetime import datetime
from typing import Annotated, Literal

from pydantic import Field

from contracts.api import Availability, OrderStatus, StoreInfo
from contracts.base import Contract
from contracts.taxonomy import LabelSection, ReplyType


class ChatRequest(Contract):
    session_id: str = Field(min_length=1)
    message: str = Field(min_length=1)


class OrderFormRequest(Contract):
    session_id: str = Field(min_length=1)
    order_number: str = Field(min_length=1)
    contact: str = Field(min_length=1)


class HandoffRequest(Contract):
    session_id: str = Field(min_length=1)
    confirmed: Literal[True]


class HandoffReply(Contract):
    ticket_id: str


class Source(Contract):
    id: str
    title: str
    text: str | None
    retrieved_at: datetime | None


class TextBlock(Contract):
    type: Literal["text"]
    text: str


class LabelSectionBlock(Contract):
    type: Literal["label_section"]
    sku: str
    name: str
    section: LabelSection
    text: str
    source_id: str


class ComparisonProduct(Contract):
    sku: str
    name: str
    active_ingredients: str
    uses: str
    warnings: str
    directions: str


class ComparisonBlock(Contract):
    type: Literal["comparison"]
    products: list[ComparisonProduct] = Field(min_length=2, max_length=2)


class ProductSummary(Contract):
    sku: str
    name: str
    uses: str
    source_id: str


class ProductListBlock(Contract):
    type: Literal["product_list"]
    products: list[ProductSummary]


class AvailabilityBlock(Contract):
    type: Literal["availability"]
    availability: Availability


class StoreInfoBlock(Contract):
    type: Literal["store_info"]
    stores: list[StoreInfo]


class PolicyExcerptBlock(Contract):
    type: Literal["policy_excerpt"]
    source_id: str
    title: str
    text: str


class OrderStatusBlock(Contract):
    type: Literal["order_status"]
    order: OrderStatus


class OrderFormBlock(Contract):
    type: Literal["order_form"]
    text: str
    order_number_label: str
    contact_label: str
    submit_label: str


Block = Annotated[
    TextBlock
    | LabelSectionBlock
    | ComparisonBlock
    | ProductListBlock
    | AvailabilityBlock
    | StoreInfoBlock
    | PolicyExcerptBlock
    | OrderStatusBlock
    | OrderFormBlock,
    Field(discriminator="type"),
]


class ChatReply(Contract):
    reply_type: ReplyType
    blocks: list[Block]
    sources: list[Source]
    handoff_offered: bool
    emergency: bool
