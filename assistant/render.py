"""Step 8: build the reply the customer reads, and the only module that does.

A reply is built from templates, record text copied word for word and API results. Code, not a
model, sets `handoff_offered`, from the policy table. A plan this module can't build safely gets
the fallback reply instead, never a partial answer. The fixed replies for risk labels, the 911
reply among them, are built here too, from assistant/policy.py.
"""

import re
from datetime import datetime

from assistant import policy, templates
from assistant.policy import FIXED_REPLIES, POLICY
from assistant.session import VerifiedOrder
from contracts.api import Availability, StoreInfo
from contracts.catalog import PolicyRecord, ProductRecord
from contracts.chat import (
    AvailabilityBlock,
    ChatReply,
    ComparisonBlock,
    ComparisonRow,
    LabelSectionBlock,
    OrderFormBlock,
    OrderStatusBlock,
    PolicyExcerptBlock,
    ProductListBlock,
    ProductRef,
    ProductSummary,
    Source,
    StoreAvailability,
    StoreInfoBlock,
    TextBlock,
)
from contracts.plan import AvailabilityRequest, CatalogPlan, StoreRequest
from contracts.taxonomy import LabelSection, ReplyType, RiskLabel

Record = ProductRecord | PolicyRecord


def label_section(
    product: ProductRecord, section: LabelSection
) -> tuple[LabelSectionBlock, Source]:
    """One label section, copied word for word, and the source that cites it."""
    text = getattr(product, section.value)
    title = templates.SECTION_TITLES[section]
    source_id = f"{product.sku}#{section.value}"
    block = LabelSectionBlock(
        type="label_section",
        sku=product.sku,
        name=product.name,
        section=section,
        title=title,
        text=text,
        source_id=source_id,
    )
    source_title = templates.LABEL_SOURCE_TITLE.format(name=product.name, section=title)
    return block, Source(id=source_id, title=source_title, text=text, retrieved_at=None)


def render_label_sections(plan: CatalogPlan, records: list[Record], risk: RiskLabel) -> ChatReply:
    products = {record.sku: record for record in records if isinstance(record, ProductRecord)}
    picked = [(products.get(s.record_id), s.sections) for s in plan.records]
    if not picked or any(product is None or not sections for product, sections in picked):
        return render_fallback()
    blocks, sources = [], []
    for product, sections in picked:
        for section in sections:
            block, source = label_section(product, section)
            blocks.append(block)
            sources.append(source)
    return ChatReply(
        reply_type=ReplyType.LABEL_SECTIONS,
        blocks=blocks,
        sources=list({source.id: source for source in sources}.values()),
        handoff_offered=POLICY[risk].handoff_offered,
        emergency=False,
    )


def render_fallback() -> ChatReply:
    """The reply when the model fails or a plan is rejected: no product facts, and the card."""
    return render_fixed(ReplyType.FALLBACK)


def render_fixed(reply_type: ReplyType) -> ChatReply:
    fixed = FIXED_REPLIES[reply_type]
    return ChatReply(
        reply_type=reply_type,
        blocks=[TextBlock(type="text", text=fixed.text)],
        sources=[],
        handoff_offered=fixed.handoff_offered,
        emergency=False,
    )


def catalog_reply(reply_type: ReplyType, blocks: list, sources: list[Source]) -> ChatReply:
    return ChatReply(
        reply_type=reply_type,
        blocks=blocks,
        sources=list({source.id: source for source in sources}.values()),
        handoff_offered=POLICY[RiskLabel.NONE].handoff_offered,
        emergency=False,
    )


def render_comparison(plan: CatalogPlan, records: list[Record]) -> ChatReply:
    products = {record.sku: record for record in records if isinstance(record, ProductRecord)}
    ids = [selection.record_id for selection in plan.records]
    if len(ids) != 2 or len(set(ids)) != 2 or any(key not in products for key in ids):
        return render_fallback()
    pair = [products[key] for key in ids]
    rows, sources = [], []
    for section in LabelSection:
        cells = [label_section(product, section) for product in pair]
        rows.append(
            ComparisonRow(
                section=section,
                title=templates.SECTION_TITLES[section],
                texts=[block.text for block, _ in cells],
            )
        )
        sources.extend(source for _, source in cells)
    block = ComparisonBlock(
        type="comparison",
        products=[ProductRef(sku=product.sku, name=product.name) for product in pair],
        rows=rows,
    )
    return catalog_reply(ReplyType.COMPARISON, [block], sources)


def render_product_list(plan: CatalogPlan, records: list[Record]) -> ChatReply:
    selected = {selection.record_id for selection in plan.records}
    products = [
        record for record in records if isinstance(record, ProductRecord) and record.sku in selected
    ]
    if not selected or selected != {product.sku for product in products}:
        return render_fallback()
    summaries, sources = [], []
    for product in products:
        _, source = label_section(product, LabelSection.USES)
        summaries.append(
            ProductSummary(
                sku=product.sku, name=product.name, uses=product.uses, source_id=source.id
            )
        )
        sources.append(source)
    block = ProductListBlock(type="product_list", products=summaries)
    return catalog_reply(ReplyType.PRODUCT_LIST, [block], sources)


def render_policy(plan: CatalogPlan, records: list[Record]) -> ChatReply:
    policies = {record.source_id: record for record in records if isinstance(record, PolicyRecord)}
    if not plan.records or any(
        selection.record_id not in policies or selection.sections for selection in plan.records
    ):
        return render_fallback()
    blocks, sources = [], []
    for selection in plan.records:
        record = policies[selection.record_id]
        blocks.append(
            PolicyExcerptBlock(
                type="policy_excerpt",
                source_id=record.source_id,
                title=record.title,
                text=record.text,
            )
        )
        sources.append(
            Source(id=record.source_id, title=record.title, text=record.text, retrieved_at=None)
        )
    return catalog_reply(ReplyType.POLICY, blocks, sources)


def render_availability(
    plan: CatalogPlan, records: list[Record], result: Availability, checked_at: datetime
) -> ChatReply:
    products = {record.sku: record for record in records if isinstance(record, ProductRecord)}
    selected = [selection.record_id for selection in plan.records]
    if not isinstance(plan.tool, AvailabilityRequest) or result.sku != plan.tool.sku:
        return render_fixed(ReplyType.LOOKUP_FAILED)
    if selected != [result.sku] or result.sku not in products or not result.stores:
        return render_fixed(ReplyType.LOOKUP_FAILED)
    if len({store.store_id for store in result.stores}) != len(result.stores):
        return render_fixed(ReplyType.LOOKUP_FAILED)
    source_id = f"api:availability/{result.sku}"
    stores = [
        StoreAvailability(
            **store.model_dump(),
            text=(
                templates.IN_STOCK.format(quantity=store.quantity)
                if store.quantity
                else templates.OUT_OF_STOCK
            ),
        )
        for store in result.stores
    ]
    block = AvailabilityBlock(
        type="availability",
        sku=result.sku,
        name=products[result.sku].name,
        stores=stores,
        source_id=source_id,
    )
    source = Source(
        id=source_id,
        title=templates.AVAILABILITY_SOURCE_TITLE,
        text=None,
        retrieved_at=checked_at,
    )
    return catalog_reply(ReplyType.AVAILABILITY, [block], [source])


def render_stores(plan: CatalogPlan, stores: list, checked_at: datetime) -> ChatReply:
    if not isinstance(plan.tool, StoreRequest) or plan.records or not stores:
        return render_fixed(ReplyType.LOOKUP_FAILED)
    if not all(isinstance(store, StoreInfo) for store in stores):
        return render_fixed(ReplyType.LOOKUP_FAILED)
    ids = [store.store_id for store in stores]
    if len(set(ids)) != len(ids) or any(
        re.fullmatch(r"[a-z0-9-]{1,32}", key) is None for key in ids
    ):
        return render_fixed(ReplyType.LOOKUP_FAILED)
    if plan.tool.store_id and ids != [plan.tool.store_id]:
        return render_fixed(ReplyType.LOOKUP_FAILED)
    blocks, sources = [], []
    for store in stores:
        source_id = f"api:stores/{store.store_id}"
        blocks.append(StoreInfoBlock(type="store_info", store=store, source_id=source_id))
        sources.append(
            Source(
                id=source_id, title=templates.STORE_SOURCE_TITLE, text=None, retrieved_at=checked_at
            )
        )
    return catalog_reply(ReplyType.STORE_INFO, blocks, sources)


def render_lookup(plan: CatalogPlan, records: list[Record], tool_result: object) -> ChatReply:
    if not isinstance(tool_result, tuple) or len(tool_result) != 2:
        return render_fixed(ReplyType.LOOKUP_FAILED)
    result, checked_at = tool_result
    if not isinstance(checked_at, datetime):
        return render_fixed(ReplyType.LOOKUP_FAILED)
    if checked_at.utcoffset() is None:
        return render_fixed(ReplyType.LOOKUP_FAILED)
    if plan.reply_type is ReplyType.AVAILABILITY and isinstance(result, Availability):
        return render_availability(plan, records, result, checked_at)
    if plan.reply_type is ReplyType.STORE_INFO and isinstance(result, list):
        return render_stores(plan, result, checked_at)
    return render_fixed(ReplyType.LOOKUP_FAILED)


def render_order(plan: CatalogPlan, verified: object) -> ChatReply:
    if plan.records or plan.tool is not None:
        return render_fallback()
    if plan.reply_type is ReplyType.ORDER_FORM:
        block = OrderFormBlock(
            type="order_form",
            text=policy.ORDER_FORM_TEXT,
            order_number_label=policy.ORDER_NUMBER_LABEL,
            contact_label=policy.ORDER_CONTACT_LABEL,
            submit_label=policy.ORDER_SUBMIT_LABEL,
        )
        return catalog_reply(ReplyType.ORDER_FORM, [block], [])
    if not isinstance(verified, VerifiedOrder):
        return render_fallback()
    order = verified.status
    delivery = (
        order.delivery_estimate.isoformat()
        if order.delivery_estimate is not None
        else templates.NO_DELIVERY_ESTIMATE
    )
    block = OrderStatusBlock(
        type="order_status",
        order=order,
        source_id="api:orders",
        text=templates.ORDER_STATUS.format(
            status=templates.ORDER_STATUSES[order.status],
            delivery_estimate=delivery,
            item_count=order.item_count,
        ),
    )
    source = Source(
        id="api:orders",
        title=templates.ORDER_SOURCE_TITLE,
        text=None,
        retrieved_at=verified.checked_at,
    )
    return catalog_reply(ReplyType.ORDER_STATUS, [block], [source])


def render_risk(risk: RiskLabel, product: ProductRecord | None) -> ChatReply:
    """The reply the policy table fixes for a risk label other than none: its text first, then,
    for a named product, the label sections that label may show, word for word. For an
    emergency this is the 911 reply; the widget draws the pharmacist card after it."""
    rule = POLICY[risk]
    if rule.text is None:
        raise ValueError(f"{risk} has no fixed reply")
    blocks: list = [TextBlock(type="text", text=rule.text)]
    sources = []
    for section in sorted(rule.sections) if product is not None else []:
        block, source = label_section(product, section)
        blocks.append(block)
        sources.append(source)
    [reply_type] = rule.reply_types
    return ChatReply(
        reply_type=reply_type,
        blocks=blocks,
        sources=sources,
        handoff_offered=rule.handoff_offered,
        emergency=risk is RiskLabel.EMERGENCY,
    )


def render(
    plan: CatalogPlan, records: list[Record], risk: RiskLabel, tool_result: object
) -> ChatReply:
    """Build a reviewed plan from evidence; unsupported or incomplete plans fail closed."""
    if risk is not RiskLabel.NONE:
        return render_fallback()
    builders = {
        ReplyType.COMPARISON: render_comparison,
        ReplyType.PRODUCT_LIST: render_product_list,
        ReplyType.POLICY: render_policy,
    }
    if plan.reply_type in builders:
        return builders[plan.reply_type](plan, records)
    if plan.reply_type is ReplyType.LABEL_SECTIONS:
        return render_label_sections(plan, records, risk)
    if plan.reply_type in FIXED_REPLIES:
        return render_fixed(plan.reply_type)
    if plan.reply_type in {ReplyType.AVAILABILITY, ReplyType.STORE_INFO}:
        return render_lookup(plan, records, tool_result)
    if plan.reply_type in {ReplyType.ORDER_FORM, ReplyType.ORDER_STATUS}:
        return render_order(plan, tool_result)
    return render_fallback()
