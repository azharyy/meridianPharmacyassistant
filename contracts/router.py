"""Describe the router's structured classification of a redacted turn."""

from contracts.base import Contract
from contracts.taxonomy import Intent, LabelSection, RiskLabel


class RouterOutput(Contract):
    intent: Intent
    risk_label: RiskLabel
    product_mentions: list[str]
    label_sections: list[LabelSection]
    store_topic: str | None
