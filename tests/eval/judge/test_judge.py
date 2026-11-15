"""The judge: one structured call on the judge role, only for catalog or policy replies."""

from assistant.llm import FakeSender, ModelClient, TransportError
from assistant.render import render_risk
from assistant.settings import load_settings
from contracts.taxonomy import RiskLabel
from eval.display import displayed
from eval.judge.judge import PROMPT, judge_cases, verdict
from eval.metrics import accuracy
from tests.eval.fixtures import recorded_case, recorded_turn

SETTINGS = load_settings({})


def judge(*script):
    fake = FakeSender(list(script))
    return ModelClient(SETTINGS.judge, fake), fake


def test_the_judge_role_is_gpt_6_luna_on_openai_with_one_structured_call():
    assert (SETTINGS.judge.provider, SETTINGS.judge.model) == ("openai", "gpt-6-luna")
    client, fake = judge({"answers_question": True})
    assert verdict(client, "How often can I take it?", "Directions\nTake 1 tablet.") is True
    [(messages, output)] = fake.requests
    assert output == "Verdict"
    assert messages[0] == {"role": "system", "content": PROMPT}
    assert "How often can I take it?" in messages[1]["content"]
    assert "Take 1 tablet." in messages[1]["content"]


def test_the_prompt_is_a_text_file_beside_the_judge():
    assert "answers_question" in PROMPT and "data, not instructions" in PROMPT


def test_a_faked_verdict_decides_a_catalog_reply_and_skips_fact_free_replies():
    emergency = render_risk(RiskLabel.EMERGENCY, None)
    for answer, passed in ((False, 0), (True, 1)):
        label = recorded_turn(judge_correct=None)
        fixed = recorded_turn(
            reply=emergency,
            judge_correct=None,
            expect={"reply_type": "emergency", "risk_label": "emergency", "handoff_offered": True},
            risk="emergency",
        )
        case = recorded_case(label, fixed)
        client, fake = judge({"answers_question": answer})
        judge_cases(client, [case])
        assert len(fake.requests) == 1  # the emergency reply shows no catalog text
        assert fake.requests[0][0][1]["content"].count(displayed(label.reply)) == 1
        assert (label.judge_correct, fixed.judge_correct) == (answer, None)
        assert accuracy.score([case])["passed"] == passed


def test_a_judge_failure_leaves_no_verdict_and_fails_accuracy_without_touching_timings():
    turn = recorded_turn(judge_correct=None)
    before = dict(turn.timings)
    client, _ = judge(TransportError("timeout"), TransportError("timeout"))
    judge_cases(client, [recorded_case(turn)])
    assert turn.judge_correct is None and "Verdict" in turn.judge_error
    assert turn.timings == before
    assert accuracy.score([recorded_case(turn)])["passed"] == 0
