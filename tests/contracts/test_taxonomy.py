"""Keep the shared vocabulary fixed and JSON-compatible."""

import json

import pytest

from contracts.taxonomy import Intent, LabelSection, ReplyType, RiskLabel, ToolName


@pytest.mark.parametrize(
    ("enum", "values"),
    [
        (Intent, "product_info compare availability store_info policy order_status off_topic"),
        (
            RiskLabel,
            "none emergency medical_advice dosing_beyond_label prescription prompt_injection",
        ),
        (LabelSection, "active_ingredients uses warnings directions"),
        (ToolName, "check_availability get_store_info"),
        (
            ReplyType,
            "label_sections comparison product_list availability store_info policy order_status "
            "order_form order_not_verified emergency medical_advice dosing_beyond_label "
            "prescription prompt_injection fallback off_topic not_found lookup_failed",
        ),
    ],
)
def test_taxonomy(enum, values):
    assert json.loads(json.dumps(list(enum))) == values.split()
    for value in values.split():
        assert enum(value).value == value
    with pytest.raises(ValueError):
        enum("unknown")
