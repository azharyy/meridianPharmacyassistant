"""Summarize response stage latency in milliseconds without including judge work."""

from statistics import median, quantiles

from eval.runner import RecordedCase


def score(cases: list[RecordedCase]) -> dict:
    totals, missing = [], 0
    for case in cases:
        for turn in case.turns:
            stages = [value for name, value in turn.timings.items() if not name.startswith("judge")]
            if stages:
                totals.append(sum(stages))
            else:
                missing += 1
    return {
        "count": len(totals),
        "missing_timings": missing,
        "p50_ms": median(totals) if totals else None,
        "p95_ms": (
            quantiles(totals, n=100, method="inclusive")[94]
            if len(totals) > 1
            else totals[0]
            if totals
            else None
        ),
    }
