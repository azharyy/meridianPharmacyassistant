"""Validate drafted case structure through the loader without printing test questions."""

import json
import re
from collections import Counter
from pathlib import Path

import pytest

from eval.loader import load_cases
from eval.runner import validate_cases

ROOT = Path(__file__).resolve().parents[2]
CASE_DIR = ROOT / "eval" / "cases"
SLICES = {
    "store_policy": 8,
    "product": 14,
    "availability": 5,
    "orders": 7,
    "emergency": 6,
    "medical_advice": 6,
    "dosing_beyond_label": 4,
    "prescription": 3,
    "prompt_injection": 4,
    "lookalike_off_topic": 3,
}
CALIBRATION_SKUS = {
    "MRD-ALG-016",
    "MRD-ALG-018",
    "MRD-CLD-002",
    "MRD-DIG-005",
    "MRD-DIG-012",
    "MRD-SKN-002",
    "MRD-SKN-004",
    "MRD-SLP-002",
    "MRD-EYE-002",
    "MRD-EYE-004",
}
SKU = re.compile(r"\bMRD-[A-Z]{3}-\d{3}\b")


@pytest.fixture(scope="module")
def case_sets():
    return {name: load_cases(CASE_DIR / f"{name}.jsonl") for name in ("dev", "test")}


def test_draft_counts_and_slice_coverage(case_sets):
    assert len(case_sets["dev"]) == 12
    assert len(case_sets["test"]) == 60
    assert Counter(case.slice for case in case_sets["test"]) == SLICES
    assert {case.slice for case in case_sets["dev"]} == set(SLICES)


def test_test_set_has_at_least_ten_multiturn_cases(case_sets):
    count = sum(len(case.turns) > 1 for case in case_sets["test"])
    assert count >= 10


def test_unlabeled_copies_cannot_run(case_sets):
    for cases in case_sets.values():
        unlabelled = [case.model_copy(deep=True) for case in cases]
        for case in unlabelled:
            for turn in case.turns:
                if turn.action in {"chat", "order_form"}:
                    turn.expect.reply_type = None
                    turn.expect.risk_label = None
                    turn.expect.handoff_offered = None
        with pytest.raises(ValueError, match="complete reply expectations"):
            validate_cases(unlabelled)


def test_product_references_are_real_disjoint_and_reserved(case_sets):
    products = json.loads((ROOT / "catalog" / "products.json").read_text("utf-8"))
    catalog_skus = {product["sku"] for product in products}
    referenced = {
        name: set(SKU.findall("\n".join(case.model_dump_json() for case in cases)))
        for name, cases in case_sets.items()
    }
    for skus in referenced.values():
        assert skus <= catalog_skus
        assert not skus & CALIBRATION_SKUS
    assert not referenced["dev"] & referenced["test"]


def test_six_fixed_questions_are_wrapped_verbatim_once(case_sets):
    source = (CASE_DIR / "handwritten_questions.md").read_text("utf-8")
    questions = re.findall(r"^\d+\. (.+)$", source, re.MULTILINE)
    messages = [
        turn.message for case in case_sets["test"] for turn in case.turns if turn.action == "chat"
    ]
    assert len(questions) == 6
    wrapped_once = all(messages.count(question) == 1 for question in questions)
    assert wrapped_once


def test_development_questions_are_separate(case_sets):
    questions = {
        name: {turn.message for case in cases for turn in case.turns if turn.action == "chat"}
        for name, cases in case_sets.items()
    }
    separate = not questions["dev"] & questions["test"]
    assert separate


def test_test_set_includes_scripted_forms_handoffs_and_timeouts(case_sets):
    actions = {turn.action for case in case_sets["test"] for turn in case.turns}
    assert {"chat", "order_form", "handoff", "api_timeout"} <= actions
