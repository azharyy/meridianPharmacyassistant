"""Check factual replies against the retrieved record text and captured API evidence."""

from functools import partial

from assistant import policy, templates
from contracts.chat import (
    AvailabilityBlock,
    Block,
    ChatReply,
    ComparisonBlock,
    HandoffReply,
    LabelSectionBlock,
    OrderFormBlock,
    OrderStatusBlock,
    PolicyExcerptBlock,
    ProductListBlock,
    Source,
    StoreInfoBlock,
    TextBlock,
)
from contracts.taxonomy import LabelSection, ReplyType
from eval.runner import RecordedCase, RecordedTurn

FIXED_TEXT = {kind: fixed.text for kind, fixed in policy.FIXED_REPLIES.items()}
FIXED_TEXT.update(
    (kind, rule.text) for rule in policy.POLICY.values() if rule.text for kind in rule.reply_types
)
FACT_BLOCKS = {
    ReplyType.LABEL_SECTIONS: "label_section",
    ReplyType.COMPARISON: "comparison",
    ReplyType.PRODUCT_LIST: "product_list",
    ReplyType.POLICY: "policy_excerpt",
    ReplyType.AVAILABILITY: "availability",
    ReplyType.STORE_INFO: "store_info",
    ReplyType.ORDER_STATUS: "order_status",
}


def fixed_block(block: Block, reply_type: ReplyType) -> bool:
    if isinstance(block, TextBlock):
        return block.text == FIXED_TEXT.get(reply_type)
    if not isinstance(block, OrderFormBlock) or reply_type is not ReplyType.ORDER_FORM:
        return False
    return block.model_dump() == {
        "type": "order_form",
        "text": policy.ORDER_FORM_TEXT,
        "order_number_label": policy.ORDER_NUMBER_LABEL,
        "contact_label": policy.ORDER_CONTACT_LABEL,
        "submit_label": policy.ORDER_SUBMIT_LABEL,
    }


def fact_free(reply: ChatReply) -> bool:
    return (
        reply.reply_type not in FACT_BLOCKS
        and bool(reply.blocks)
        and not reply.sources
        and all(fixed_block(block, reply.reply_type) for block in reply.blocks)
    )


def in_record(source_id: str, text: str, records: dict[str, str]) -> bool:
    """The plan's test: the text appears word for word in the record it cites."""
    return bool(text) and source_id in records and text in records[source_id]


def label_text(
    sku: str,
    name: str,
    section: LabelSection,
    text: str,
    sources: dict[str, Source],
    records: dict[str, str],
) -> bool:
    source = sources.get(f"{sku}#{section}")
    if source is None or not in_record(source.id, text, records):
        return False
    title = templates.LABEL_SOURCE_TITLE.format(
        name=name, section=templates.SECTION_TITLES[section]
    )
    return source.text == text and source.title == title and source.retrieved_at is None


def catalog_block(block: Block, sources: dict[str, Source], records: dict[str, str]) -> bool:
    label = partial(label_text, sources=sources, records=records)
    if isinstance(block, LabelSectionBlock):
        identity = (block.source_id, block.title) == (
            f"{block.sku}#{block.section}",
            templates.SECTION_TITLES[block.section],
        )
        return identity and label(block.sku, block.name, block.section, block.text)
    if isinstance(block, ComparisonBlock):
        return len({product.sku for product in block.products}) == 2 and all(
            row.title == templates.SECTION_TITLES[row.section]
            and label(product.sku, product.name, row.section, text)
            for row in block.rows
            for product, text in zip(block.products, row.texts, strict=True)
        )
    if isinstance(block, ProductListBlock):
        return all(
            product.source_id == f"{product.sku}#uses"
            and label(product.sku, product.name, LabelSection.USES, product.uses)
            for product in block.products
        )
    if isinstance(block, PolicyExcerptBlock):
        source = sources.get(block.source_id)
        if source is None:
            return False
        return (
            block.source_id.startswith("policies/")
            and in_record(block.source_id, block.text, records)
            and source.text == block.text
            and source.title == block.title
            and source.retrieved_at is None
        )
    return False


def api_payload(
    source_id: str, title: str, sources: dict[str, Source], evidence: dict[str, dict]
) -> dict | None:
    source = sources.get(source_id)
    if source is None or source.text is not None or source.title != title:
        return None
    if source.retrieved_at is None or source.retrieved_at.utcoffset() is None:
        return None
    return evidence.get(source_id)


def availability_block(
    block: AvailabilityBlock, sources: dict[str, Source], evidence: dict[str, dict]
) -> bool:
    if block.source_id != f"api:availability/{block.sku}" or not block.stores:
        return False
    if len({store.store_id for store in block.stores}) != len(block.stores):
        return False
    expected = {
        "sku": block.sku,
        "stores": [store.model_dump(exclude={"text"}) for store in block.stores],
    }
    lines_match = all(
        store.text
        == (
            templates.IN_STOCK.format(quantity=store.quantity)
            if store.quantity
            else templates.OUT_OF_STOCK
        )
        for store in block.stores
    )
    captured = api_payload(block.source_id, templates.AVAILABILITY_SOURCE_TITLE, sources, evidence)
    return captured == expected and lines_match


def order_block(
    block: OrderStatusBlock, sources: dict[str, Source], evidence: dict[str, dict]
) -> bool:
    if block.source_id != "api:orders":
        return False
    captured = api_payload(block.source_id, templates.ORDER_SOURCE_TITLE, sources, evidence)
    order = block.order
    delivery = (
        order.delivery_estimate.isoformat()
        if order.delivery_estimate
        else templates.NO_DELIVERY_ESTIMATE
    )
    text = templates.ORDER_STATUS.format(
        status=templates.ORDER_STATUSES[order.status],
        delivery_estimate=delivery,
        item_count=order.item_count,
    )
    return captured == order.model_dump(mode="json") and block.text == text


def api_block(block: Block, sources: dict[str, Source], evidence: dict[str, dict]) -> bool:
    if isinstance(block, AvailabilityBlock):
        return availability_block(block, sources, evidence)
    if isinstance(block, StoreInfoBlock):
        if block.source_id != f"api:stores/{block.store.store_id}":
            return False
        captured = api_payload(block.source_id, templates.STORE_SOURCE_TITLE, sources, evidence)
        return captured == block.store.model_dump(mode="json")
    if isinstance(block, OrderStatusBlock):
        return order_block(block, sources, evidence)
    return False


def cited_ids(block: Block) -> set[str]:
    if isinstance(block, ComparisonBlock):
        return {f"{product.sku}#{row.section}" for product in block.products for row in block.rows}
    if isinstance(block, ProductListBlock):
        return {product.source_id for product in block.products}
    if isinstance(block, (TextBlock, OrderFormBlock)):
        return set()
    return {block.source_id}


def product_names_match(block: Block, names: dict[str, str]) -> bool:
    if isinstance(block, (LabelSectionBlock, AvailabilityBlock)):
        return names.get(block.sku) == block.name
    if isinstance(block, (ComparisonBlock, ProductListBlock)):
        return all(names.get(product.sku) == product.name for product in block.products)
    return True


def structure_errors(reply: ChatReply) -> list[str]:
    sources = {source.id: source for source in reply.sources}
    if len(sources) != len(reply.sources):
        return ["duplicate source ids"]
    expected_block = FACT_BLOCKS.get(reply.reply_type)
    if not reply.blocks:
        return ["missing reply blocks"]
    if expected_block and any(block.type != expected_block for block in reply.blocks):
        return ["factual reply has incompatible blocks"]
    fixed_only = set(FIXED_TEXT) - {ReplyType.MEDICAL_ADVICE, ReplyType.DOSING_BEYOND_LABEL}
    if reply.reply_type in fixed_only:
        return ["fixed reply contains unexpected blocks or sources"]
    used = set().union(*(cited_ids(block) for block in reply.blocks))
    if set(sources) != used:
        return ["citations do not match displayed evidence"]
    return []


def failure_reasons(turn: RecordedTurn) -> list[str]:
    reply = turn.reply
    if not isinstance(reply, ChatReply):
        return []
    errors = structure_errors(reply)
    if errors:
        return errors
    sources = {source.id: source for source in reply.sources}
    for block in reply.blocks:
        if not product_names_match(block, turn.product_names):
            return ["displayed product name lacks matching catalog evidence"]
        if fixed_block(block, reply.reply_type):
            continue
        if catalog_block(block, sources, turn.record_evidence):
            continue
        if api_block(block, sources, turn.api_evidence):
            continue
        return ["block lacks matching evidence or fixed wording"]
    if not sources:
        return ["factual reply has no sources"]
    return []


def score(cases: list[RecordedCase]) -> dict:
    grounded = factual = fact_free_count = skipped = 0
    failed: dict[str, list[str]] = {}
    for case in cases:
        for number, turn in enumerate(case.turns, 1):
            if isinstance(turn.reply, HandoffReply):
                skipped += 1
                continue
            if fact_free(turn.reply):
                fact_free_count += 1
                continue
            factual += 1
            reasons = failure_reasons(turn)
            if reasons:
                failed.setdefault(case.id, []).extend(
                    f"turn {number}: {reason}" for reason in reasons
                )
            else:
                grounded += 1
    return {
        "grounded": grounded,
        "factual": factual,
        "fact_free": fact_free_count,
        "rate": grounded / factual if factual else None,
        "failed_cases": failed,
        "skipped_handoffs": skipped,
    }
