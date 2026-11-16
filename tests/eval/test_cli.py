"""The CLI composes fake models offline, validates before startup and compares matching runs."""

import json
from dataclasses import asdict, replace
from pathlib import Path

import httpx
import pytest

from assistant.llm import FakeSender, ModelClient
from assistant.pipeline import Steps
from assistant.settings import MissingKey, load_settings
from eval import cli
from eval.cli import EvaluationInputError, evaluate, input_cases, metadata, refresh_report, run_live
from eval.judge.calibrate import PROMPT_SHA256
from eval.loader import Case
from tests.assistant.fixtures import PLAN, QUESTION, ROUTED, search

SETTINGS = load_settings({})


def cases():
    return [
        Case.model_validate(
            {
                "id": "synthetic-001",
                "slice": "synthetic",
                "turns": [
                    {
                        "action": "chat",
                        "message": QUESTION,
                        "expect": {
                            "reply_type": "label_sections",
                            "risk_label": "none",
                            "handoff_offered": False,
                        },
                    }
                ],
            }
        )
    ]


def evaluate_fake(directory, name="dev", settings=SETTINGS, answer=True):
    runtime = ModelClient(settings.runtime, FakeSender([ROUTED, PLAN]))
    judge = ModelClient(settings.judge, FakeSender([{"answers_question": answer}]))
    with httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(500))) as http:
        result = evaluate(
            name, cases(), settings, runtime, judge, http, Steps(retrieve=search), directory
        )
    return result, runtime, judge


def saved_calibration(directory):
    directory.mkdir(parents=True, exist_ok=True)
    result = {
        "agreed": 20,
        "total": 20,
        "rate": 1.0,
        "disagreements": [],
        "prompt_sha256": PROMPT_SHA256,
        "judge": asdict(SETTINGS.judge),
        "service_tier": "provider_default",
    }
    (directory / "calibration.json").write_text(json.dumps(result))
    return result


def test_the_full_composer_runs_fake_runtime_and_judge_and_writes_actual_results(tmp_path):
    raw, runtime, judge = evaluate_fake(tmp_path, answer=False)
    assert raw["metrics"]["accuracy"]["passed"] == 0
    assert raw["cases"][0]["turns"][0]["judge_correct"] is False
    assert len(runtime.send.requests) == 2 and len(judge.send.requests) == 1
    assert raw == json.loads((tmp_path / "dev.json").read_text())
    assert "evidence judge did not pass" in (tmp_path / "dev.md").read_text()
    assert raw["configuration"]["runtime"]["model"] == SETTINGS.runtime.model
    assert "keys" not in raw["configuration"]
    assert len(raw["configuration"]["case_sha256"]) == 64
    assert all("judge" not in name for name in raw["cases"][0]["turns"][0]["timings"])


def test_unlabeled_cases_stop_before_models_or_api_start():
    source, started = cases(), []
    source[0].turns[0].expect.risk_label = None
    with pytest.raises(ValueError, match="complete reply expectations"):
        run_live("dev", source, SETTINGS, models=started.append, serve=started.append)
    assert started == []


def test_input_errors_are_clear_and_never_echo_case_text(tmp_path):
    path = tmp_path / "synthetic.jsonl"
    with pytest.raises(EvaluationInputError, match="input file is missing"):
        input_cases(path)
    path.write_text('{"message": "synthetic-secret@example.com"}')
    with pytest.raises(EvaluationInputError, match="line 1: invalid case") as error:
        input_cases(path)
    assert "synthetic-secret" not in str(error.value)
    source = cases()[0]
    source.turns[0].expect.reply_type = None
    path.write_text(source.model_dump_json())
    with pytest.raises(EvaluationInputError, match="complete reply expectations"):
        input_cases(path)


def test_missing_live_keys_stop_before_models_or_api_start():
    started = []
    with pytest.raises(MissingKey, match="OPENCODE_API_KEY"):
        run_live(
            "dev",
            cases(),
            load_settings({"MERIDIAN_LLM": "live"}),
            models=started.append,
            serve=started.append,
        )
    assert started == []


@pytest.mark.parametrize(
    "setting",
    [
        SETTINGS,
        load_settings({"MERIDIAN_LLM": "live", "MERIDIAN_EXACT_MATCH": "0"}),
        load_settings({"MERIDIAN_LLM": "live", "MERIDIAN_RUNTIME_MODEL": "glm-5.3-flash"}),
        load_settings({"MERIDIAN_LLM": "live", "MERIDIAN_RUNTIME_PROVIDER": "groq"}),
    ],
)
def test_wrong_variant_settings_stop_before_models_or_api_start(setting):
    started = []
    with pytest.raises(ValueError):
        run_live("dev", cases(), setting, models=started.append, serve=started.append)
    assert started == []


def test_live_composition_rejects_using_the_same_model_for_runtime_and_judge():
    started = []
    setting = load_settings({"MERIDIAN_LLM": "live", "OPENCODE_API_KEY": "synthetic-key"})
    setting = replace(setting, judge=setting.runtime)
    with pytest.raises(ValueError, match="different judge"):
        run_live("dev", cases(), setting, models=started.append, serve=started.append)
    assert started == []


def test_comparison_rejects_the_default_runtime_before_keys_or_reference_loading():
    started = []
    setting = load_settings({"MERIDIAN_LLM": "live"})
    with pytest.raises(ValueError, match="selected runtime"):
        run_live("dev-compare", cases(), setting, models=started.append, serve=started.append)
    assert started == []


@pytest.mark.parametrize("role", ["runtime", "judge"])
def test_unknown_model_endpoints_are_rejected_before_clients_or_requests(role):
    started = []
    setting = load_settings({"MERIDIAN_LLM": "live", "OPENCODE_API_KEY": "synthetic-key"})
    setting = replace(
        setting, **{role: replace(getattr(setting, role), base_url="https://model.invalid")}
    )
    with pytest.raises(ValueError, match="selected runtime"):
        run_live("dev", cases(), setting, models=started.append, serve=started.append)
    assert started == []


def test_report_is_written_only_after_both_compatible_variants_exist(tmp_path):
    directory = tmp_path / "results"
    assert not refresh_report(directory)
    evaluate_fake(directory, "baseline", replace(SETTINGS, exact_match=False))
    assert not refresh_report(directory)
    evaluate_fake(directory, "improved")
    saved_calibration(directory)
    assert refresh_report(directory)
    text = (tmp_path / "REPORT.md").read_text()
    assert "# Evaluation report" in text and "## Label audit" not in text
    (directory / "LABEL_AUDIT.md").write_text("# Label audit")
    assert refresh_report(directory)  # a recalibration must keep the audit's disclosure
    assert "[the label audit](results/LABEL_AUDIT.md)" in (tmp_path / "REPORT.md").read_text()


@pytest.mark.parametrize(
    "changed", ["case_sha256", "runtime", "judge_prompt_sha256", "implementation_sha256"]
)
def test_report_rejects_mismatched_cases_models_or_prompts(tmp_path, changed):
    directory = tmp_path / "results"
    evaluate_fake(directory, "baseline", replace(SETTINGS, exact_match=False))
    raw, _, _ = evaluate_fake(directory, "improved")
    raw["configuration"][changed] = "different"
    (directory / "improved.json").write_text(json.dumps(raw))
    with pytest.raises(ValueError, match="incompatible cases or configuration"):
        refresh_report(directory)
    assert not (tmp_path / "REPORT.md").exists()


def test_metadata_never_contains_provider_key_values():
    setting = load_settings(
        {
            "OPENCODE_API_KEY": "synthetic-secret-one",
            "GROQ_API_KEY": "synthetic-secret-two",
            "OPENAI_API_KEY": "synthetic-secret-three",
        }
    )
    data = json.dumps(metadata(cases(), setting))
    assert "synthetic-secret" not in data


def test_make_targets_set_live_models_and_matching_flags_without_shell_commands():
    makefile = Path("Makefile").read_text()
    assert "eval-dev eval-baseline eval: export MERIDIAN_LLM := live" in makefile
    assert "eval-dev eval-baseline eval: export MERIDIAN_RUNTIME_PROVIDER := opencode" in makefile
    assert "eval-dev eval-baseline eval: export MERIDIAN_RUNTIME_MODEL := glm-5.3" in makefile
    assert "eval-dev eval: export MERIDIAN_EXACT_MATCH := 1" in makefile
    assert "eval-baseline: export MERIDIAN_EXACT_MATCH := 0" in makefile
    for name in ("dev", "baseline", "improved"):
        assert f"\t$(PY) -m eval.cli {name}\n" in makefile


@pytest.mark.parametrize(
    "relative",
    [
        "api/orders.py",
        "contracts/catalog.py",
        "data/policies/delivery.md",
    ],
)
def test_implementation_digest_tracks_runtime_inputs(tmp_path, monkeypatch, relative):
    monkeypatch.setattr(cli, "ROOT", tmp_path)
    source = tmp_path / relative
    source.parent.mkdir(parents=True)
    source.write_text("synthetic initial content", encoding="utf-8")
    original = cli.implementation_digest()
    assert cli.implementation_digest() == original
    source.write_text("synthetic changed content", encoding="utf-8")
    assert cli.implementation_digest() != original
    source.write_text("synthetic initial content", encoding="utf-8")
    assert cli.implementation_digest() == original


@pytest.mark.parametrize(
    "relative",
    [
        "notes.md",
        "eval/results/notes.txt",
        "eval/results/synthetic.py",
        "eval/cases/synthetic.txt",
        "assistant/__pycache__/synthetic.py",
    ],
)
def test_implementation_digest_ignores_nonruntime_artifacts(tmp_path, monkeypatch, relative):
    monkeypatch.setattr(cli, "ROOT", tmp_path)
    before = cli.implementation_digest()
    artifact = tmp_path / relative
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text("synthetic excluded content", encoding="utf-8")
    assert cli.implementation_digest() == before
