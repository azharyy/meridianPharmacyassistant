"""Retrieval requires both comparison records in the correct turn and excludes API-only cases."""

from eval.metrics.retrieval import score
from tests.eval.fixtures import recorded_case, recorded_turn


def with_gold(*sources, retrieved=()):
    turn = recorded_turn(retrieved=list(retrieved))
    turn.expect.gold_sources = list(sources)
    return turn


def test_label_sections_map_to_products_but_policy_sections_keep_their_anchor():
    turn = with_gold(
        "MRD-ALG-012#directions",
        "policies/returns.md#returns",
        retrieved=["MRD-ALG-012", "policies/returns.md#returns"],
    )
    assert score([recorded_case(turn)])["passed"] == 1
    turn.retrieved = ["MRD-ALG-012", "policies/returns.md#another-section"]
    assert score([recorded_case(turn)])["passed"] == 0


def test_both_comparison_records_are_needed_in_the_same_turn():
    turn = with_gold("MRD-ALG-012#uses", "MRD-ALG-014#uses", retrieved=["MRD-ALG-012"])
    case = recorded_case(turn, recorded_turn(retrieved=["MRD-ALG-014"]))
    assert score([case])["passed"] == 0
    turn.retrieved.append("MRD-ALG-014")
    assert score([recorded_case(turn)])["passed"] == 1


def test_known_counts_and_api_or_no_gold_cases_are_not_applicable():
    good = recorded_case(with_gold("MRD-ALG-012#uses", retrieved=["MRD-ALG-012"]), id="good")
    bad = recorded_case(with_gold("MRD-ALG-014#uses"), id="bad")
    api = recorded_case(with_gold("api:orders"), id="api")
    result = score([good, bad, api, recorded_case(id="none")])
    assert (result["passed"], result["total"], result["rate"], result["not_applicable"]) == (
        1,
        2,
        0.5,
        2,
    )
    assert set(result["failed_cases"]) == {"bad"}
    assert score([api])["rate"] is None and score([])["rate"] is None
