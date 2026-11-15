"""Step 8: build the reply the customer reads, and the only module that does.

A reply is built from templates, record text copied word for word and API results. Code, not a
model, sets `handoff_offered`, from the policy table. A plan this module can't build safely gets
the fallback reply instead, never a partial answer. The fixed replies for risk labels, the 911
reply among them, are built here too, from assistant/policy.py.
"""

from assistant import templates
from assistant.policy import FIXED_REPLIES, POLICY
from contracts.catalog import PolicyRecord, ProductRecord
from contracts.chat import ChatReply, LabelSectionBlock, Source, TextBlock
from contracts.plan import CatalogPlan
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
        sources=sources,
        handoff_offered=POLICY[risk].handoff_offered,
        emergency=False,
    )


def render_fallback() -> ChatReply:
    """The reply when the model fails or a plan is rejected: no product facts, and the card."""
    fixed = FIXED_REPLIES[ReplyType.FALLBACK]
    return ChatReply(
        reply_type=ReplyType.FALLBACK,
        blocks=[TextBlock(type="text", text=fixed.text)],
        sources=[],
        handoff_offered=fixed.handoff_offered,
        emergency=False,
    )


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
    """The reply for a reviewed plan. Issue 6 adds the other reply types and the tool results."""
    if plan.reply_type is ReplyType.LABEL_SECTIONS:
        return render_label_sections(plan, records, risk)
    return render_fallback()
