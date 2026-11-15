"""Step 3: read the redacted conversation and return its intent, risk label and what it asks about.

One structured-output call over the customer's messages only. The router never sees retrieved
text, so an instruction planted in a document can't change a safety decision.
"""

from pathlib import Path

from assistant.llm import ModelClient
from contracts.router import RouterOutput

PROMPT = (Path(__file__).parent / "prompts" / "router.txt").read_text(encoding="utf-8")


def route(llm: ModelClient, messages: list[str]) -> RouterOutput:
    """`messages` are the customer's messages so far, redacted, oldest first."""
    conversation = "\n".join(f"Customer: {message}" for message in messages)
    return llm.complete(
        [{"role": "system", "content": PROMPT}, {"role": "user", "content": conversation}],
        RouterOutput,
    )
