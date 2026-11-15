"""Read the mock API's settings, once: the staff key and where the data files are.

The API's own settings module, because api/ may not import assistant/. The assistant never
holds the staff key.
"""

import os
from collections.abc import Mapping
from pathlib import Path

DATA = Path(__file__).resolve().parents[1] / "data"
DEFAULT_STAFF_KEY = "dev-staff-key"


def staff_key(env: Mapping[str, str] = os.environ) -> str:
    """The value `GET /v1/tickets/{ticket_id}` needs in its X-Staff-Key header."""
    return env.get("MERIDIAN_STAFF_KEY", "").strip() or DEFAULT_STAFF_KEY
