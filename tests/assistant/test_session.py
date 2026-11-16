"""The session store keeps turns, the verified order and the current handoff offer, per session."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

from assistant.session import Session, SessionStore, Turn, VerifiedOrder
from contracts.api import OrderStatus
from contracts.chat import ChatReply
from contracts.taxonomy import ReplyType, RiskLabel

REPLY = ChatReply(
    reply_type=ReplyType.OFF_TOPIC, blocks=[], sources=[], handoff_offered=False, emergency=False
)


def turn(message: str) -> Turn:
    return Turn(message=message, reply=REPLY, routed=None)


def test_each_session_id_has_its_own_session():
    store = SessionStore()
    first = store.get("session-0001")
    assert store.get("session-0001") is first
    assert store.get("session-0002") is not first


def test_turns_keep_redacted_messages_and_only_the_most_recent():
    session = Session(max_turns=3)
    for number in range(5):
        session.add(turn(f"message {number} from [email]"))
    assert session.messages() == [f"message {n} from [email]" for n in (2, 3, 4)]


def test_the_verified_order_is_the_status_and_its_time_only():
    session = Session()
    status = OrderStatus(status="shipped", delivery_estimate=None, item_count=2)
    session.verified_order = VerifiedOrder(status, datetime(2026, 11, 15, tzinfo=UTC))
    assert set(vars(session.verified_order)) == {"status", "checked_at"}


def test_each_offer_gets_its_own_uuid4_and_the_last_one_is_kept():
    session = Session()
    first = session.offer_handoff(RiskLabel.MEDICAL_ADVICE, "risk")
    second = session.offer_handoff(RiskLabel.NONE, "fallback")
    assert first.id != second.id
    assert all(str(UUID(offer.id, version=4)) == offer.id for offer in (first, second))
    assert session.handoff_offer is second
    assert second.ticket_id is None


def test_only_the_current_offer_can_be_confirmed_and_an_unknown_id_allocates_nothing():
    session = Session()
    first = session.offer_handoff(RiskLabel.EMERGENCY, "risk")
    second = session.offer_handoff(RiskLabel.NONE, "fallback")
    assert session.confirm_offer(second.id) is second
    assert session.confirm_offer(first.id) is None
    assert session.confirm_offer(str(uuid4())) is None
    assert session.handoff_offer is second
    empty = Session()
    assert empty.confirm_offer(first.id) is None and empty.handoff_offer is None


def test_the_header_confirms_the_current_offer_or_one_requested_by_the_customer():
    session = Session()
    requested = session.confirm_offer(None)
    assert (requested.risk_label, requested.reason) == (RiskLabel.NONE, "customer_requested")
    assert session.confirm_offer(None) is requested is session.handoff_offer
    card = session.offer_handoff(RiskLabel.EMERGENCY, "risk")
    assert session.confirm_offer(None) is card


def test_a_recreated_session_rejects_the_old_sessions_card():
    store = SessionStore(max_sessions=1)
    old = store.get("session-0001")
    card = old.offer_handoff(RiskLabel.EMERGENCY, "risk")
    store.get("session-0002")  # evicts the old session
    recreated = store.get("session-0001")
    assert recreated is not old
    assert recreated.confirm_offer(card.id) is None and recreated.handoff_offer is None
    assert recreated.offer_handoff(RiskLabel.EMERGENCY, "risk").id != card.id
    assert recreated.confirm_offer(card.id) is None


def test_past_the_limit_the_oldest_session_is_dropped():
    store = SessionStore(max_sessions=2)
    oldest = store.get("session-0001")
    store.get("session-0002")
    store.get("session-0003")
    assert store.get("session-0001") is not oldest
