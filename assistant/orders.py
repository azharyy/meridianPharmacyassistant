"""Verify the order form through the API and retain only its public status in the session."""

from datetime import UTC, datetime

import httpx

from assistant import api_client
from assistant.session import Session, VerifiedOrder
from contracts.api import OrderLookupRequest
from contracts.chat import OrderFormRequest


def verify(request: OrderFormRequest, session: Session, http: httpx.Client) -> VerifiedOrder | None:
    """Every attempt replaces old verification; all lookup failures leave no verified order."""
    session.verified_order = None
    lookup = OrderLookupRequest(order_number=request.order_number, contact=request.contact)
    checked_at = datetime.now(UTC)
    try:
        status = api_client.lookup_order(http, lookup)
    except api_client.APIUnavailable:
        status = None
    verified = VerifiedOrder(status, checked_at) if status is not None else None
    session.verified_order = verified
    return verified
