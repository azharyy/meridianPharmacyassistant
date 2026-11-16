"""Define the assistant's HTTP requests and replies, and the nine blocks a reply is built from.

The widget draws every string in a block as given: label and policy text copied word for
word, API results, or wording from assistant/policy.py and assistant/templates.py.
"""

from datetime import datetime
from typing import Annotated, Literal

from pydantic import Field

from contracts.api import OrderStatus, StoreInfo, StoreStock
from contracts.base import Contract
from contracts.catalog import SKU_PATTERN
from contracts.taxonomy import LabelSection, ReplyType

SECTIONS = "|".join(section.value for section in LabelSection)
# The plan's three forms of source: a label section, a policy page section, a live lookup.
SOURCE_ID_PATTERN = (
    rf"^({SKU_PATTERN}#({SECTIONS})"
    r"|policies/[a-z0-9-]+\.md#[a-z0-9-]+"
    rf"|api:(stores/[a-z0-9-]+|availability/{SKU_PATTERN}|orders))$"
)
Sku = Annotated[str, Field(pattern=rf"^{SKU_PATTERN}$")]
SourceId = Annotated[str, Field(pattern=SOURCE_ID_PATTERN)]
StoreId = Annotated[str, Field(pattern=r"^[a-z0-9-]{1,32}$")]
# Logs carry the session ID, and the client chooses it, so it can't hold an email address.
SessionId = Annotated[str, Field(pattern=r"^[A-Za-z0-9_-]{8,64}$")]
OfferId = Annotated[
    str,
    Field(pattern=r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"),
]


class ChatRequest(Contract):
    session_id: SessionId
    message: str = Field(min_length=1, max_length=2000)
    # The widget's data-store: the store the customer shops at, used for store questions.
    store_id: StoreId | None = None


class OrderFormRequest(Contract):
    session_id: SessionId
    order_number: str = Field(min_length=1, max_length=64)
    contact: str = Field(min_length=1, max_length=254)


class HandoffRequest(Contract):
    session_id: SessionId
    confirmed: Literal[True]
    # A card targets this offer; null is the header's current-conversation action.
    # The server rejects unknown/superseded IDs with 409 and no ticket creation.
    offer_id: OfferId | None = None


class HandoffReply(Contract):
    # None when the ticket couldn't be created; calling /handoff again retries with the same key.
    ticket_id: str | None
    text: str


class Source(Contract):
    id: SourceId
    title: str
    # The exact text for a label or policy source; None for a live lookup.
    text: str | None
    # The time of the call for a live lookup; None for a label or policy source.
    retrieved_at: datetime | None


class TextBlock(Contract):
    type: Literal["text"]
    text: str


class LabelSectionBlock(Contract):
    type: Literal["label_section"]
    sku: Sku
    name: str
    section: LabelSection
    title: str
    text: str
    source_id: SourceId


class ProductRef(Contract):
    sku: Sku
    name: str


class ComparisonRow(Contract):
    section: LabelSection
    title: str
    # One text per product, in the order of the block's products.
    texts: list[str] = Field(min_length=2, max_length=2)


class ComparisonBlock(Contract):
    type: Literal["comparison"]
    products: list[ProductRef] = Field(min_length=2, max_length=2)
    rows: list[ComparisonRow] = Field(min_length=1, max_length=4)


class ProductSummary(Contract):
    sku: Sku
    name: str
    uses: str
    source_id: SourceId


class ProductListBlock(Contract):
    type: Literal["product_list"]
    products: list[ProductSummary] = Field(min_length=1)


class StoreAvailability(StoreStock):
    # The renderer's line for this store, such as "In stock (12)".
    text: str


class AvailabilityBlock(Contract):
    type: Literal["availability"]
    sku: Sku
    name: str
    stores: list[StoreAvailability]
    source_id: SourceId


class StoreInfoBlock(Contract):
    type: Literal["store_info"]
    store: StoreInfo
    source_id: SourceId


class PolicyExcerptBlock(Contract):
    type: Literal["policy_excerpt"]
    source_id: SourceId
    title: str
    text: str


class OrderStatusBlock(Contract):
    type: Literal["order_status"]
    # The order-status template, filled from the API's response.
    text: str
    order: OrderStatus
    source_id: SourceId


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
    # Set by code when recording a handoff offer, never by a model.
    offer_id: OfferId | None = None
