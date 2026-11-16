"""Keep each conversation's state in memory: its turns, its verified order and its handoff offer.

A turn keeps the customer's message after redaction, never the raw text. The verified order is
the status the API returned; the order number and contact are never kept.
"""

import threading
from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal
from uuid import uuid4

from contracts.api import OrderStatus
from contracts.chat import ChatReply
from contracts.router import RouterOutput
from contracts.taxonomy import RiskLabel

MAX_TURNS = 20
MAX_SESSIONS = 10_000


@dataclass(frozen=True)
class Turn:
    message: str  # after redaction
    reply: ChatReply
    routed: RouterOutput | None  # None when the turn made no model call


@dataclass(frozen=True)
class VerifiedOrder:
    status: OrderStatus
    checked_at: datetime


@dataclass
class HandoffOffer:
    """A pharmacist card, and why it was shown. Its ID and the session ID key the ticket."""

    risk_label: RiskLabel
    reason: Literal["risk", "fallback", "customer_requested"]
    id: str = field(default_factory=lambda: str(uuid4()))  # never repeats, even after a restart
    ticket_id: str | None = None  # set once the ticket exists


@dataclass
class Session:
    turns: list[Turn] = field(default_factory=list)
    verified_order: VerifiedOrder | None = None
    handoff_offer: HandoffOffer | None = None  # the current card: the only one that can be filed
    max_turns: int = MAX_TURNS
    _offer_lock: threading.Lock = field(default_factory=threading.Lock, repr=False, compare=False)

    def add(self, turn: Turn) -> None:
        self.turns = [*self.turns, turn][-self.max_turns :]

    def messages(self) -> list[str]:
        """The customer's messages so far, redacted, oldest first."""
        return [turn.message for turn in self.turns]

    # The lock covers only these two short steps: no model or ticket API call ever waits on it.
    def offer_handoff(
        self, risk_label: RiskLabel, reason: Literal["risk", "fallback", "customer_requested"]
    ) -> HandoffOffer:
        """A new card. It becomes the current offer, so older cards can no longer be filed."""
        with self._offer_lock:
            self.handoff_offer = HandoffOffer(risk_label, reason)
            return self.handoff_offer

    def confirm_offer(self, offer_id: str | None) -> HandoffOffer | None:
        """The offer a confirmation files: the current one if `offer_id` names it, else None and
        nothing changes. No ID is the header button: the current offer, or one it requests."""
        with self._offer_lock:
            if offer_id is None:
                if self.handoff_offer is None:
                    self.handoff_offer = HandoffOffer(RiskLabel.NONE, "customer_requested")
                return self.handoff_offer
            current = self.handoff_offer
            return current if current is not None and current.id == offer_id else None


class SessionStore:
    """Sessions by ID. Past the limit, the oldest session is dropped."""

    def __init__(self, max_sessions: int = MAX_SESSIONS) -> None:
        self._sessions: dict[str, Session] = {}
        self._max_sessions = max_sessions
        self._lock = threading.Lock()

    def get(self, session_id: str) -> Session:
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                if len(self._sessions) >= self._max_sessions:
                    self._sessions.pop(next(iter(self._sessions)))
                session = self._sessions[session_id] = Session()
            return session
