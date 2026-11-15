"""Wait for bounded provider-directed evaluation retries inside each model call."""

import math
import time
from collections.abc import Callable

from assistant.llm import Send, TransportError
from assistant.settings import Role

RETRIES = 2
MAX_WAIT = 60.0


class QuotaExhausted(RuntimeError):
    """A 429 too long to wait out, such as a daily limit: stop rather than score fallbacks."""


def retry_after(error: TransportError) -> float | None:
    """Seconds a 429 asks to wait (inf when it gives no usable number); None for other errors."""
    response = getattr(error.__cause__, "response", None)
    if response is None or response.status_code != 429:
        return None
    try:
        seconds = float(response.headers.get("Retry-After", ""))
    except ValueError:
        return math.inf
    return seconds if math.isfinite(seconds) and seconds >= 0 else math.inf


def rate_limited_sender(
    send: Send, role: Role, pause: Callable[[float], None] = time.sleep
) -> Send:
    """Retry a 429 that asks for at most MAX_WAIT twice per send; stop the run on a longer one."""

    def retry(messages, output):
        for attempt in range(RETRIES + 1):
            try:
                return send(messages, output)
            except TransportError as error:
                seconds = retry_after(error)
                if seconds is not None and seconds > MAX_WAIT:
                    wait = f"{seconds:.0f}s" if math.isfinite(seconds) else "an unstated time"
                    raise QuotaExhausted(
                        f"{role.provider}/{role.model} is rate limited for {wait}, longer than"
                        f" the eval waits ({MAX_WAIT:g}s); probably its daily limit."
                        " Nothing was saved; run again later."
                    ) from None
                if seconds is None or attempt == RETRIES:
                    raise
                print(
                    f"{role.provider}/{role.model} rate limit: waiting {seconds:g}s"
                    f" before retry {attempt + 1}/{RETRIES}.",
                    flush=True,
                )
                pause(seconds)

    return retry
