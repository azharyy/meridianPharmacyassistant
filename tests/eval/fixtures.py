"""Build small recorded evaluation replies with explicit gold labels for metric tests."""

from assistant.render import render
from contracts.taxonomy import LabelSection, RiskLabel
from eval.runner import RecordedCase, RecordedTurn
from tests.assistant.fixtures import PLAN, PRODUCTS, QUESTION

# What the runner records for the fixture products: each cited section's retrieved text.
RECORDS = {
    f"{product.sku}#{section.value}": getattr(product, section.value)
    for product in PRODUCTS
    for section in LabelSection
}


def recorded_turn(**changes) -> RecordedTurn:
    values = {
        "action": "chat",
        "question": QUESTION,
        "expect": {"reply_type": "label_sections", "risk_label": "none", "handoff_offered": False},
        "reply": render(PLAN, PRODUCTS, RiskLabel.NONE, None),
        "retrieved": [PRODUCTS[0].sku],
        "timings": {"router": 10.0, "catalog_agent": 20.0},
        "record_evidence": RECORDS,
        "judge_correct": True,
    }
    return RecordedTurn.model_validate({**values, **changes})


def recorded_case(*turns: RecordedTurn, id: str = "case-001") -> RecordedCase:
    return RecordedCase(id=id, slice="synthetic", turns=list(turns) or [recorded_turn()])
