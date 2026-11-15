"""A run's raw results and summary: every metric, raw counts, and every failed case's reasons."""

import json

from eval.results import METRICS, failed_cases, percent, score_all, summary, write_run
from tests.eval.fixtures import recorded_case, recorded_turn


def test_a_run_writes_raw_json_and_a_summary_listing_every_failed_case(tmp_path):
    good = recorded_case(id="case-001")
    bad = recorded_case(recorded_turn(judge_correct=False), id="case-002")
    metrics = score_all([good, bad])
    assert set(metrics) == set(METRICS)
    raw = write_run("dev", [good, bad], metrics, extra={"runtime": "groq"}, directory=tmp_path)
    saved = json.loads((tmp_path / "dev.json").read_text(encoding="utf-8"))
    assert saved == raw and saved["runtime"] == "groq"
    assert [case["id"] for case in saved["cases"]] == ["case-001", "case-002"]
    text = (tmp_path / "dev.md").read_text(encoding="utf-8")
    assert "# Results: dev" in text and "- Answer accuracy: 1/2 (50.0%)" in text
    assert "- case-002: accuracy: evidence judge did not pass" in text
    assert "case-001:" not in text


def test_failures_from_every_metric_are_grouped_by_case_and_a_clean_run_says_none():
    metrics = {name: {"failed_cases": {}} for name in METRICS}
    metrics["accuracy"]["failed_cases"] = {"b": ["reply type mismatch"]}
    metrics["privacy"]["failed_cases"] = {"b": ["response 1: order data"], "a": ["x"]}
    assert failed_cases(metrics) == {
        "a": ["privacy: x"],
        "b": ["accuracy: reply type mismatch", "privacy: response 1: order data"],
    }
    clean = score_all([recorded_case()])
    assert summary("dev", clean).rstrip().endswith("## Failed cases\n\nNone.")


def test_counts_are_raw_with_a_percentage_and_an_empty_total_is_not_a_rate():
    assert percent(9, 12) == "9/12 (75.0%)" and percent(0, 0) == "0/0 (n/a)"
