"""Pharmacist tickets: one per idempotency key, readable back only by staff.

The same key returns the same ticket, even with a different summary, and never creates a
second one. Tickets live in memory for as long as the API runs.
"""

import threading

from contracts.api import TicketCreated, TicketCreateRequest, TicketRecord


class TicketDesk:
    def __init__(self) -> None:
        self._by_key: dict[str, str] = {}
        self._by_id: dict[str, TicketRecord] = {}
        self._guard = threading.Lock()

    def create(self, request: TicketCreateRequest) -> TicketCreated:
        with self._guard:
            ticket_id = self._by_key.get(request.idempotency_key)
            if ticket_id is None:
                ticket_id = f"TCK-{1001 + len(self._by_id)}"
                self._by_key[request.idempotency_key] = ticket_id
                self._by_id[ticket_id] = TicketRecord(ticket_id=ticket_id, summary=request.summary)
            return TicketCreated(ticket_id=ticket_id)

    def get(self, ticket_id: str) -> TicketRecord | None:
        return self._by_id.get(ticket_id)

    def count(self) -> int:
        return len(self._by_id)
