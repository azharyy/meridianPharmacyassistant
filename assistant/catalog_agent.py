"""Step 5: choose the records and sections that answer the question, and at most one tool.

One structured-output call. The retrieved records go in as data, marked as such, and the agent
returns a plan: it never writes text for the customer and has no way to reach orders.
"""

import json
from pathlib import Path

from assistant.llm import ModelClient
from contracts.catalog import PolicyRecord, ProductRecord
from contracts.plan import CatalogPlan

PROMPT = (Path(__file__).parent / "prompts" / "catalog_agent.txt").read_text(encoding="utf-8")


def records_as_data(records: list[ProductRecord | PolicyRecord]) -> str:
    """The records as JSON inside <records>. Every "<" is escaped, so no text can close the tag."""
    rows = json.dumps([record.model_dump(mode="json") for record in records], ensure_ascii=False)
    escaped = rows.replace("<", "\\u003c")  # still valid JSON, with the same meaning
    return f"<records>\n{escaped}\n</records>"


def plan(
    llm: ModelClient, question: str, records: list[ProductRecord | PolicyRecord]
) -> CatalogPlan:
    """`question` is the customer's latest message, redacted."""
    content = f"Question: {question}\n\n{records_as_data(records)}"
    return llm.complete(
        [{"role": "system", "content": PROMPT}, {"role": "user", "content": content}],
        CatalogPlan,
    )
