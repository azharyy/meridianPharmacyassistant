"""Keep each conversation's state in memory: its turns, its verified order and its handoff offer.

A turn keeps the customer's message after redaction, never the raw text. The verified order is
the status the API returned; the order number and contact are never kept.
"""

import threading
from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

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
    """The last pharmacist card shown, and why. Its number and the session ID key the ticket."""

    number: int
    risk_label: RiskLabel
    reason: Literal["risk", "fallback", "customer_requested"]
    ticket_id: str | None = None  # set once the ticket exists


@dataclass
class Session:
    turns: list[Turn] = field(default_factory=list)
    verified_order: VerifiedOrder | None = None
    handoff_offer: HandoffOffer | None = None
    offers_made: int = 0
    max_turns: int = MAX_TURNS
    _offer_lock: threading.Lock = field(default_factory=threading.Lock, repr=False, compare=False)

    def add(self, turn: Turn) -> None:
        self.turns = [*self.turns, turn][-self.max_turns :]

    def messages(self) -> list[str]:
        """The customer's messages so far, redacted, oldest first."""
        return [turn.message for turn in self.turns]

    def offer_handoff(
        self,
        risk_label: RiskLabel,
        reason: Literal["risk", "fallback", "customer_requested"],
        *,
        reuse: bool = False,
    ) -> HandoffOffer:
        # Only allocation is locked: emergency replies never wait for a ticket API call.
        with self._offer_lock:
            if not reuse or self.handoff_offer is None:
                self.offers_made += 1
                self.handoff_offer = HandoffOffer(self.offers_made, risk_label, reason)
            return self.handoff_offer


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
