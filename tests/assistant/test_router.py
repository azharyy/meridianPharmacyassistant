"""The router makes one structured call over the customer's redacted messages, with its prompt."""

import pytest

from assistant.llm import FakeSender, ModelClient, ModelUnavailable
from assistant.router import PROMPT, route
from assistant.settings import load_settings
from contracts.router import RouterOutput
from tests.assistant.fixtures import ROUTED

RUNTIME = load_settings({}).runtime


def test_one_call_returns_the_router_output():
    fake = FakeSender([ROUTED])
    messages = ["I'm pregnant.", "How do I take Meridian All Day Allergy?"]
    assert route(ModelClient(RUNTIME, fake), messages) == ROUTED
    [(sent, schema)] = fake.requests
    assert schema == RouterOutput.__name__
    assert sent[0] == {"role": "system", "content": PROMPT}
    assert sent[1]["content"] == (
        "Customer: I'm pregnant.\nCustomer: How do I take Meridian All Day Allergy?"
    )


def test_the_prompt_is_a_text_file_that_asks_for_no_reply_text():
    assert "never write a reply" in PROMPT


def test_no_valid_output_is_reported_to_the_caller():
    with pytest.raises(ModelUnavailable):
        route(ModelClient(RUNTIME, FakeSender()), ["Hello"])
