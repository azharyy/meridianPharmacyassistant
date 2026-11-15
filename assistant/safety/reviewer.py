"""Step 6: check the catalog agent's plan in code before anything is shown.

A plan is rejected when it names a record that wasn't retrieved, asks for a section that record
doesn't have, or proposes a reply type or a label section the turn's risk label doesn't allow.
The pipeline turns a rejected plan into the fallback reply, with the pharmacist card.
"""

from assistant.policy import POLICY
from contracts.catalog import PolicyRecord, ProductRecord
from contracts.plan import CatalogPlan, RecordSelection
from contracts.taxonomy import RiskLabel

Record = ProductRecord | PolicyRecord


def record_id(record: Record) -> str:
    return record.sku if isinstance(record, ProductRecord) else record.source_id


def selection_allowed(selection: RecordSelection, record: Record | None, risk: RiskLabel) -> bool:
    if record is None:
        return False  # not retrieved this turn
    if isinstance(record, PolicyRecord) and selection.sections:
        return False  # a policy page section has no label sections
    return set(selection.sections) <= POLICY[risk].sections


def review(plan: CatalogPlan, records: list[Record], risk: RiskLabel) -> CatalogPlan | None:
    """The plan when every check passes; None to reject it."""
    if plan.reply_type not in POLICY[risk].reply_types:
        return None
    retrieved = {record_id(record): record for record in records}
    allowed = (selection_allowed(s, retrieved.get(s.record_id), risk) for s in plan.records)
    return plan if all(allowed) else None
