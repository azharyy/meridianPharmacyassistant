"""Measure each conversation's gold catalog or policy evidence in its own retrieval turns."""

from eval.runner import RecordedCase


def gold_record(source_id: str) -> str:
    return source_id.split("#")[0] if source_id.startswith("MRD-") else source_id


def score(cases: list[RecordedCase]) -> dict:
    total, failed = 0, {}
    for case in cases:
        gold_turns = [
            (
                {
                    gold_record(source)
                    for source in turn.expect.gold_sources
                    if not source.startswith("api:")
                },
                set(turn.retrieved),
            )
            for turn in case.turns
        ]
        if not any(gold for gold, _ in gold_turns):
            continue
        total += 1
        if any(not gold <= retrieved for gold, retrieved in gold_turns):
            failed[case.id] = ["gold evidence missing from its retrieval turn"]
    passed = total - len(failed)
    return {
        "passed": passed,
        "total": total,
        "rate": passed / total if total else None,
        "not_applicable": len(cases) - total,
        "failed_cases": failed,
    }
