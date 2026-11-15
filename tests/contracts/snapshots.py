"""Build the committed contract snapshots; run as a module to rewrite them (`make contracts`).

contracts/schemas.json holds the JSON schema of every model that crosses a boundary, and
contracts/meridian-api.json the mock API's OpenAPI spec. test_snapshots.py compares both with
what the code produces now, so a contract can't change without its snapshot changing too.
This helper lives beside the test because it imports api/, which contracts/ may not.
"""

import json
from pathlib import Path

from api.app import app
from contracts.catalog import PolicyRecord, ProductRecord
from contracts.chat import (
    ChatReply,
    ChatRequest,
    HandoffReply,
    HandoffRequest,
    OrderFormRequest,
)
from contracts.plan import CatalogPlan
from contracts.router import RouterOutput

CONTRACTS = Path(__file__).resolve().parents[2] / "contracts"
MODELS = (
    RouterOutput,
    CatalogPlan,
    ChatRequest,
    ChatReply,
    OrderFormRequest,
    HandoffRequest,
    HandoffReply,
    ProductRecord,
    PolicyRecord,
)


def render(content: dict) -> str:
    return json.dumps(content, indent=2, sort_keys=True) + "\n"


def current() -> dict[str, str]:
    """Each snapshot file's name and the text the code produces for it now."""
    return {
        "schemas.json": render({model.__name__: model.model_json_schema() for model in MODELS}),
        "meridian-api.json": render(app.openapi()),
    }


def main() -> None:
    for name, text in current().items():
        (CONTRACTS / name).write_text(text, encoding="utf-8", newline="\n")
        print(f"wrote contracts/{name}")


if __name__ == "__main__":
    main()
