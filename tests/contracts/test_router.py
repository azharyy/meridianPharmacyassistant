"""Validate router classifications without permitting a customer reply."""

import pytest
from pydantic import ValidationError

from contracts.router import RouterOutput
from contracts.taxonomy import Intent, LabelSection

PAYLOAD = {
    "intent": "product_info",
    "risk_label": "none",
    "product_mentions": ["Meridian sample"],
    "label_sections": ["directions"],
    "store_topic": None,
}


def test_router_output():
    result = RouterOutput.model_validate(PAYLOAD)
    assert result.intent is Intent.PRODUCT_INFO
    assert result.label_sections == [LabelSection.DIRECTIONS]
    assert result.model_dump(mode="json") == PAYLOAD
    assert RouterOutput(**(PAYLOAD | {"store_topic": "hours"})).store_topic == "hours"


@pytest.mark.parametrize(
    "changes", [{"intent": "invented"}, {"risk_label": "safe"}, {"reply_text": "model prose"}]
)
def test_router_rejects_invalid_output(changes):
    with pytest.raises(ValidationError):
        RouterOutput.model_validate(PAYLOAD | changes)


def test_nullable_topic_is_still_required():
    with pytest.raises(ValidationError, match="store_topic"):
        RouterOutput.model_validate(
            {key: value for key, value in PAYLOAD.items() if key != "store_topic"}
        )
