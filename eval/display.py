"""Extract the text shown in widget reply blocks for deterministic checks and evidence judging."""

from contracts.chat import Block, ChatReply, HandoffReply


def block_lines(block: Block) -> list[str]:
    match block.type:
        case "text" | "order_status":
            return [block.text]
        case "label_section":
            return [block.name, block.title, block.text]
        case "comparison":
            return [product.name for product in block.products] + [
                text for row in block.rows for text in [row.title, *row.texts]
            ]
        case "product_list":
            return [text for product in block.products for text in [product.name, product.uses]]
        case "availability":
            return [block.name] + [
                text for store in block.stores for text in [store.store_name, store.text]
            ]
        case "store_info":
            store = block.store
            return [
                store.name,
                store.address,
                store.phone,
                *[text for day, hours in store.hours.items() for text in [day, hours]],
                *store.services,
            ]
        case "policy_excerpt":
            return [block.title, block.text]
        case "order_form":
            return [block.text, block.order_number_label, block.contact_label, block.submit_label]
    raise ValueError("unsupported reply block")


def displayed(reply: ChatReply | HandoffReply) -> str:
    if isinstance(reply, HandoffReply):
        return reply.text
    return "\n".join(text for block in reply.blocks for text in block_lines(block))


def needs_judge(reply: ChatReply | HandoffReply) -> bool:
    return isinstance(reply, ChatReply) and any(
        block.type in {"label_section", "comparison", "product_list", "policy_excerpt"}
        for block in reply.blocks
    )
