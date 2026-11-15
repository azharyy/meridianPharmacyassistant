"""Wait for bounded provider-directed evaluation retries inside each model call."""

import math
import time
from collections.abc import Callable

from assistant.llm import Send, TransportError
from assistant.settings import Role

RETRIES = 2
MAX_WAIT = 60.0


def retry_after(error: TransportError) -> float | None:
    response = getattr(error.__cause__, "response", None)
    if response is None or response.status_code != 429:
        return None
    try:
        seconds = float(response.headers.get("Retry-After", ""))
    except ValueError:
        return None
    return seconds if math.isfinite(seconds) and 0 <= seconds <= MAX_WAIT else None


def rate_limited_sender(
    send: Send, role: Role, pause: Callable[[float], None] = time.sleep
) -> Send:
    """Retry only a 429 with a valid Retry-After, twice per shared-client send attempt."""

    def retry(messages, output):
        for attempt in range(RETRIES + 1):
            try:
                return send(messages, output)
            except TransportError as error:
                seconds = retry_after(error)
                if seconds is None or attempt == RETRIES:
                    raise
                print(
                    f"{role.provider}/{role.model} rate limit: waiting {seconds:g}s"
                    f" before retry {attempt + 1}/{RETRIES}.",
                    flush=True,
                )
                pause(seconds)

    return retry
