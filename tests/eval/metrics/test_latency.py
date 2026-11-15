"""Latency summarizes each response's stage sum with inclusive percentile interpolation."""

from contracts.chat import HandoffReply
from eval.metrics.latency import score
from tests.eval.fixtures import recorded_case, recorded_turn


def test_percentiles_are_per_response_and_exclude_every_judge_stage():
    turns = [
        recorded_turn(
            timings={
                "router": 25.0,
                "catalog_agent": value - 25,
                "judge": 99999,
                "judge_review": 99999,
            }
        )
        for value in (100.0, 200.0, 300.0, 400.0, 500.0)
    ]
    cases = [recorded_case(*turns[:3], id="first"), recorded_case(*turns[3:], id="second")]
    before = [case.model_dump_json() for case in cases]
    assert score(cases) == {"count": 5, "missing_timings": 0, "p50_ms": 300.0, "p95_ms": 480.0}
    assert [case.model_dump_json() for case in cases] == before


def test_missing_timings_are_counted_apart_from_real_zero_latency():
    case = recorded_case(
        recorded_turn(timings={}),
        recorded_turn(timings={"judge": 1000}),
        recorded_turn(timings={"router": 0.0}),
    )
    assert score([case]) == {"count": 1, "missing_timings": 2, "p50_ms": 0.0, "p95_ms": 0.0}


def test_single_slow_response_is_measured_and_can_fail_the_four_second_target():
    result = score([recorded_case(recorded_turn(timings={"router": 5000.0}))])
    assert result["p50_ms"] == result["p95_ms"] == 5000.0
    assert result["p95_ms"] > 4000


def test_order_form_and_handoff_response_timers_are_included():
    case = recorded_case(
        recorded_turn(action="order_form", timings={"order_form": 100.0}),
        recorded_turn(
            action="handoff",
            reply=HandoffReply(ticket_id="TCK-1001", text="Created."),
            timings={"handoff": 200.0},
        ),
    )
    assert score([case]) == {"count": 2, "missing_timings": 0, "p50_ms": 150.0, "p95_ms": 195.0}


def test_empty_run_has_no_latency_samples():
    assert score([]) == {"count": 0, "missing_timings": 0, "p50_ms": None, "p95_ms": None}
