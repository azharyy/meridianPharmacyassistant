"""The reviewer rejects, one test each: a record not retrieved, a section that doesn't exist, and
a reply type or label section the turn's risk label doesn't allow."""

from assistant.safety.reviewer import review
from contracts.catalog import PolicyRecord
from contracts.plan import CatalogPlan
from contracts.taxonomy import RiskLabel
from tests.assistant.fixtures import PRODUCTS

POLICY_PAGE = PolicyRecord(
    source_id="policies/delivery.md#delivery-area", title="Delivery area", text="Within 10 miles."
)
RECORDS = [*PRODUCTS, POLICY_PAGE]


def plan(reply_type="label_sections", record="MRD-ALG-012", sections=("directions",)):
    selection = {"record_id": record, "sections": list(sections)}
    return CatalogPlan(reply_type=reply_type, records=[selection], tool=None)


def test_a_plan_that_passes_every_check_is_returned_unchanged():
    label_plan, policy_plan = plan(), plan("policy", POLICY_PAGE.source_id, ())
    assert review(label_plan, RECORDS, RiskLabel.NONE) is label_plan
    assert review(policy_plan, RECORDS, RiskLabel.NONE) is policy_plan


def test_a_record_that_was_not_retrieved_is_rejected():
    assert review(plan(record="MRD-ALG-999"), RECORDS, RiskLabel.NONE) is None


def test_a_section_that_does_not_exist_is_rejected():
    assert review(plan("policy", POLICY_PAGE.source_id, ("uses",)), RECORDS, RiskLabel.NONE) is None


def test_a_reply_type_the_risk_label_does_not_allow_is_rejected():
    assert review(plan(reply_type="emergency"), RECORDS, RiskLabel.NONE) is None
    assert review(plan(), RECORDS, RiskLabel.MEDICAL_ADVICE) is None


def test_a_label_section_the_risk_label_does_not_allow_is_rejected():
    medical = plan(reply_type="medical_advice", sections=("directions",))
    assert review(medical, RECORDS, RiskLabel.MEDICAL_ADVICE) is None
    warnings = plan(reply_type="medical_advice", sections=("warnings",))
    assert review(warnings, RECORDS, RiskLabel.MEDICAL_ADVICE) is warnings
