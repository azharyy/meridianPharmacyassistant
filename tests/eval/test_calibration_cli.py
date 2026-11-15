"""Live calibration guards labels and freezes its prompt before any model request."""

import json
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path

import httpx
import pytest

from assistant.llm import FakeSender, ModelClient, sdk_sender
from assistant.settings import MissingKey, load_settings
from eval.cli import (
    EvaluationInputError,
    input_pairs,
    require_calibration,
    run_calibration,
    run_live,
)
from eval.judge.calibrate import PROMPT_SHA256, Pair
from eval.judge.judge import Verdict
from tests.eval.test_cli import SETTINGS, cases, evaluate_fake, saved_calibration

LIVE = load_settings({"MERIDIAN_LLM": "live", "OPENCODE_API_KEY": "synthetic-opencode-key"})


def pairs(label=True):
    return [
        Pair(
            id=f"cal-{i:02d}",
            question="Synthetic question?",
            reply="Catalog evidence",
            drafted_as="right evidence",
            label=label,
        )
        for i in range(20)
    ]


def models(settings, answers):
    @contextmanager
    def factory(settings, *, judge_only=False):
        assert judge_only
        yield (
            ModelClient(
                settings.judge, FakeSender([{"answers_question": answer} for answer in answers])
            ),
        )

    return factory


def test_calibration_uses_only_the_judge_and_writes_agreement_disagreements_and_prompt_hash(
    tmp_path,
):
    result = run_calibration(
        pairs(), LIVE, models=models(LIVE, [False] + [True] * 19), directory=tmp_path
    )
    assert result["agreed"] == 19 and result["total"] == 20
    assert result["disagreements"] == [{"id": "cal-00", "label": True, "judge": False}]
    assert result["prompt_sha256"] == PROMPT_SHA256 and result["service_tier"] == "provider_default"
    assert result["label_source"] == "AI (user authorized)"
    assert result == json.loads((tmp_path / "calibration.json").read_text())
    text = (tmp_path / "calibration.md").read_text()
    assert "19/20 (95.0%)" in text and "cal-00: labeled True, the judge said False" in text
    assert PROMPT_SHA256 in text and "Processing: provider default" in text
    assert "Judge: opencode kimi-k3.1-pro." in text
    assert require_calibration(tmp_path, result["judge"]) == result


def test_unlabeled_calibration_stops_before_keys_or_models(tmp_path):
    started = []
    with pytest.raises(EvaluationInputError, match="Label every calibration pair"):
        run_calibration(pairs(None), SETTINGS, models=started.append, directory=tmp_path)
    assert started == [] and not list(tmp_path.iterdir())


def test_calibration_uses_the_same_opencode_key_as_the_runtime(tmp_path):
    started = []
    with pytest.raises(MissingKey, match="OPENCODE_API_KEY"):
        run_calibration(
            pairs(),
            load_settings({"MERIDIAN_LLM": "live"}),
            models=started.append,
            directory=tmp_path,
        )
    assert started == []
    assert (
        run_calibration(pairs(), LIVE, models=models(LIVE, [True] * 20), directory=tmp_path)[
            "agreed"
        ]
        == 20
    )


@pytest.mark.parametrize("change", ["prompt", "judge", "incomplete"])
def test_test_set_stops_before_keys_models_or_api_when_calibration_is_untrusted(tmp_path, change):
    result = saved_calibration(tmp_path)
    if change == "prompt":
        result["prompt_sha256"] = "changed"
    elif change == "judge":
        result["judge"]["model"] = "different"
    else:
        result.pop("agreed")
    (tmp_path / "calibration.json").write_text(json.dumps(result))
    started = []
    settings = load_settings({"MERIDIAN_LLM": "live", "MERIDIAN_EXACT_MATCH": "0"})
    with pytest.raises(EvaluationInputError):
        run_live(
            "baseline",
            cases(),
            settings,
            models=started.append,
            serve=started.append,
            directory=tmp_path,
        )
    assert started == []


def test_test_set_needs_a_completed_calibration_before_keys_models_or_api(tmp_path):
    started = []
    settings = load_settings({"MERIDIAN_LLM": "live", "MERIDIAN_EXACT_MATCH": "0"})
    with pytest.raises(EvaluationInputError, match="Calibrate the labeled"):
        run_live(
            "baseline",
            cases(),
            settings,
            models=started.append,
            serve=started.append,
            directory=tmp_path,
        )
    assert started == []


def test_a_saved_calibration_from_an_unknown_endpoint_cannot_be_trusted(tmp_path):
    result = saved_calibration(tmp_path)
    result["judge"]["base_url"] = "https://model.invalid"
    (tmp_path / "calibration.json").write_text(json.dumps(result))
    with pytest.raises(EvaluationInputError, match="does not match this judge"):
        require_calibration(tmp_path, result["judge"])


def test_a_saved_prompt_cannot_be_replaced_by_recalibrating_after_a_change(tmp_path):
    result = saved_calibration(tmp_path)
    result["prompt_sha256"] = "changed"
    path = tmp_path / "calibration.json"
    text = json.dumps(result)
    path.write_text(text)
    started = []
    with pytest.raises(EvaluationInputError, match="restore the calibrated prompt"):
        run_calibration(pairs(), LIVE, models=started.append, directory=tmp_path)
    assert started == [] and path.read_text() == text


def test_calibration_refreshes_an_existing_compatible_test_report(tmp_path):
    directory = tmp_path / "results"
    evaluate_fake(directory, "baseline", replace(SETTINGS, exact_match=False))
    evaluate_fake(directory, "improved")
    run_calibration(pairs(), LIVE, models=models(LIVE, [True] * 20), directory=directory)
    text = (tmp_path / "REPORT.md").read_text()
    assert "Agreement with the supplied labels: 20/20 (100.0%)." in text


def test_a_calibration_for_another_judge_leaves_the_measured_report_alone(tmp_path):
    directory = tmp_path / "results"
    evaluate_fake(directory, "baseline", replace(SETTINGS, exact_match=False))
    evaluate_fake(directory, "improved")
    other = replace(LIVE, judge=replace(LIVE.judge, model="another-judge"))
    result = run_calibration(pairs(), other, models=models(other, [True] * 20), directory=directory)
    assert result["judge"]["model"] == "another-judge"
    assert not (tmp_path / "REPORT.md").exists()  # the runs used SETTINGS.judge, not this one


def test_bad_calibration_input_never_echoes_pair_text(tmp_path):
    path = tmp_path / "calibration.jsonl"
    path.write_text('{"question": "synthetic-private@example.com"}')
    with pytest.raises(EvaluationInputError, match="missing or invalid") as error:
        input_pairs(path)
    assert "synthetic-private" not in str(error.value)


@pytest.mark.parametrize("alter", ["short", "duplicate", "unlabeled"])
def test_calibration_inputs_require_twenty_unique_hand_labels(tmp_path, alter):
    source = pairs()
    if alter == "short":
        source.pop()
    elif alter == "duplicate":
        source[-1].id = source[0].id
    else:
        source[-1].label = None
    path = tmp_path / "calibration.jsonl"
    path.write_text("\n".join(pair.model_dump_json() for pair in source))
    with pytest.raises(EvaluationInputError):
        input_pairs(path)


def test_shared_sdk_wire_uses_the_opencode_go_judge_with_strict_outputs_and_no_tools():
    requests, urls = [], []

    def send(request):
        requests.append(json.loads(request.content))
        urls.append(str(request.url))
        return httpx.Response(
            200,
            json={
                "id": "synthetic",
                "object": "chat.completion",
                "created": 0,
                "model": LIVE.judge.model,
                "choices": [
                    {
                        "index": 0,
                        "finish_reason": "stop",
                        "message": {"role": "assistant", "content": '{"answers_question":true}'},
                    }
                ],
            },
        )

    with httpx.Client(transport=httpx.MockTransport(send)) as http:
        client = ModelClient(LIVE.judge, sdk_sender(LIVE.judge, "synthetic-key", http))
        assert client.complete(
            [{"role": "user", "content": "Synthetic evidence"}], Verdict
        ).answers_question
    assert urls == ["https://opencode.ai/inference/go/openai/v1/chat/completions"]
    assert requests[0]["model"] == "kimi-k3.1-pro"
    assert requests[0]["reasoning_effort"] == "low"
    assert "service_tier" not in requests[0]
    assert requests[0]["response_format"]["json_schema"]["strict"] is True
    assert "tools" not in requests[0]


def test_the_calibration_make_target_selects_live_mode_and_the_cli_command():
    makefile = Path("Makefile").read_text()
    assert "judge-calibrate: export MERIDIAN_LLM := live" in makefile
    assert "judge-calibrate: export MERIDIAN_RUNTIME_PROVIDER := opencode" in makefile
    assert "\t$(PY) -m eval.cli calibrate\n" in makefile
