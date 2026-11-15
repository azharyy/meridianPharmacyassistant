"""Calibration: the drafted pairs, and agreement measured on faked verdicts."""

import json

import pytest

from assistant.llm import FakeSender, ModelClient
from assistant.settings import load_settings
from eval.judge.calibrate import PROMPT_SHA256, Pair, calibrate, load_pairs, summary

PRODUCTS = json.loads(open("catalog/products.json", encoding="utf-8").read())
SECTIONS = ("active_ingredients", "uses", "warnings", "directions")


def pair(id, label, drafted_as="right evidence"):
    return Pair(id=id, question="Q?", reply="Shown text", drafted_as=drafted_as, label=label)


def judge(*answers):
    fake = FakeSender([{"answers_question": answer} for answer in answers])
    return ModelClient(load_settings({}).judge, fake), fake


def test_the_drafted_pairs_are_twenty_from_the_catalog_about_half_with_wrong_evidence():
    pairs = load_pairs()
    assert len(pairs) == 20 and len({p.id for p in pairs}) == 20
    assert 8 <= sum(p.drafted_as != "right evidence" for p in pairs) <= 12
    texts = [product[section] for product in PRODUCTS for section in SECTIONS]
    for p in pairs:
        name, title, body = p.reply.split("\n", 2)
        assert body in texts, p.id  # every shown section is copied from a catalog record


def test_agreement_and_each_disagreement_come_from_the_judges_verdicts():
    client, fake = judge(True, True, False)
    result = calibrate(client, [pair("cal-01", True), pair("cal-02", False), pair("cal-03", False)])
    assert (result["agreed"], result["total"]) == (2, 3)
    assert result["disagreements"] == [{"id": "cal-02", "label": False, "judge": True}]
    assert result["prompt_sha256"] == PROMPT_SHA256 and len(fake.requests) == 3
    assert summary(result).splitlines() == [
        "Judge agreement: 2/3 (66.7%)",
        "- cal-02: labeled False, the judge said True",
    ]


def test_unlabeled_pairs_stop_before_any_judge_request():
    client, fake = judge(True)
    with pytest.raises(ValueError, match="label every calibration pair"):
        calibrate(client, [pair("cal-01", True), pair("cal-02", None)])
    assert fake.requests == []
