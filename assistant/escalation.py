"""Hand a conversation to a pharmacist: one ticket per offer, with a summary built by code.

A ticket is created only when the customer confirms, through POST /handoff, and only for the
session's current offer: a card names its offer by ID, and an older or unknown card files
nothing. The idempotency key is the session ID and the offer's ID, so confirming twice, or
retrying after a failure, never creates a second ticket. The header button sends no ID: it files
the current offer or, with no card on screen, an offer of its own, marked as requested by the
customer. The summary holds redacted messages only.
"""

import httpx

from assistant import api_client
from assistant.policy import HANDOFF_CREATED_TEXT, HANDOFF_FAILED_TEXT, HANDOFF_STALE_TEXT
from assistant.session import HandoffOffer, Session
from contracts.api import TicketCreateRequest, TicketSummary
from contracts.chat import ChatReply, HandoffReply
from contracts.taxonomy import RiskLabel

STALE = HandoffReply(ticket_id=None, text=HANDOFF_STALE_TEXT)  # the app sends it with HTTP 409
RECENT_TURNS = 5
URGENCY = {
    RiskLabel.EMERGENCY: "emergency",
    RiskLabel.MEDICAL_ADVICE: "urgent",
    RiskLabel.DOSING_BEYOND_LABEL: "urgent",
}  # every other risk label is routine


def described(reply: ChatReply) -> str:
    """What the assistant replied, without its text: the reply type and the sources it cited."""
    cited = ", ".join(source.id for source in reply.sources)
    return f"{reply.reply_type.value} ({cited})" if cited else reply.reply_type.value


def summarize(session: Session, offer: HandoffOffer) -> TicketSummary:
    turns = session.turns[-RECENT_TURNS:]
    mentions = [name for turn in turns if turn.routed for name in turn.routed.product_mentions]
    return TicketSummary(
        risk_label=offer.risk_label,
        urgency=URGENCY.get(offer.risk_label, "routine"),
        customer_messages=[turn.message for turn in turns],
        product_mentions=list(dict.fromkeys(mentions)),
        assistant_replies=[described(turn.reply) for turn in turns],
        reason=offer.reason,
    )


def handoff(
    session_id: str, session: Session, http: httpx.Client, offer_id: str | None = None
) -> HandoffReply:
    """The ticket for the confirmed offer, created once; a failure keeps the offer for a retry.
    The offer is captured before the ticket call, so a newer card can't change what is filed."""
    offer = session.confirm_offer(offer_id)
    if offer is None:
        return STALE
    if offer.ticket_id is None:
        key = f"{session_id}:{offer.id}"
        request = TicketCreateRequest(idempotency_key=key, summary=summarize(session, offer))
        try:
            offer.ticket_id = api_client.create_ticket(http, request).ticket_id
        except api_client.APIUnavailable:
            return HandoffReply(ticket_id=None, text=HANDOFF_FAILED_TEXT)
    text = HANDOFF_CREATED_TEXT.format(ticket_id=offer.ticket_id)
    return HandoffReply(ticket_id=offer.ticket_id, text=text)
