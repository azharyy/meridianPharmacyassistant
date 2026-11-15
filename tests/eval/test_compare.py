"""Runtime comparisons reject stale references and report only recorded usage-derived costs."""

import json
from contextlib import contextmanager
from pathlib import Path

import pytest

from assistant.llm import FakeSender
from assistant.pipeline import Steps
from assistant.settings import COMPARISON_RUNTIME_MODEL, load_settings
from eval.cli import metadata, run_live
from eval.compare import build, reference_run
from eval.usage import MeteredModel, UsageCapture
from tests.assistant.fixtures import PLAN, ROUTED, search
from tests.eval.test_cli import cases, evaluate_fake

GROQ = load_settings({"MERIDIAN_LLM": "live", "GROQ_API_KEY": "synthetic-groq-key"})
GROQ20B = load_settings(
    {
        "MERIDIAN_LLM": "live",
        "MERIDIAN_RUNTIME_MODEL": COMPARISON_RUNTIME_MODEL,
        "GROQ_API_KEY": "synthetic-groq-key",
    }
)


def test_comparison_shows_accuracy_latency_and_actual_runtime_cost_with_pricing_sources(tmp_path):
    before, _, _ = evaluate_fake(tmp_path, settings=GROQ)
    after, _, _ = evaluate_fake(tmp_path, name="dev-groq20b", settings=GROQ20B)
    before["runtime_usage"] = UsageCapture(
        requests=1, responses_with_usage=1, prompt_tokens=1000, completion_tokens=100
    ).snapshot(GROQ.runtime)
    after["runtime_usage"] = UsageCapture(
        requests=1, responses_with_usage=1, prompt_tokens=1000, completion_tokens=100
    ).snapshot(GROQ20B.runtime)
    text = build(before, after)
    assert "| Answer accuracy | 1/1 (100.0%) | 1/1 (100.0%) |" in text
    assert "| Latency p50 / p95 |" in text
    assert "| Estimated runtime cost (USD) | $0.00021000 | $0.00010500 |" in text
    assert "reasoning tokens" in text and "Judge calls are excluded" in text
    assert "Rate-limited (429) attempts return no completion and count as unbilled" in text
    assert "https://console.groq.com/docs/model/openai/gpt-oss-120b" in text
    assert "https://console.groq.com/docs/model/openai/gpt-oss-20b" in text
    assert "Groq GPT-OSS 120B | Groq GPT-OSS 20B" in text
    assert "2026-11-15" in text
    after["runtime_usage"]["unaccounted"] = 2
    assert "| $0.00021000 | at least $0.00010500 (2 attempts without usage) |" in build(
        before, after
    )
    after["runtime_usage"]["estimated_cost_usd"] = None
    assert "$0.00021000 | unavailable" in build(before, after)


@pytest.mark.parametrize(
    "changed",
    ["case_sha256", "implementation_sha256", "judge", "mode", "runtime", "exact_match", "usage"],
)
def test_stale_reference_stops_before_models_or_api_start(tmp_path, changed):
    saved, _, _ = evaluate_fake(tmp_path, settings=GROQ)
    if changed == "exact_match":
        saved["exact_match"] = False
    elif changed == "usage":
        saved.pop("runtime_usage")
    else:
        saved["configuration"][changed] = "different"
    (tmp_path / "dev.json").write_text(json.dumps(saved))
    started = []
    with pytest.raises(ValueError, match="eval-dev again"):
        run_live(
            "dev-groq20b",
            cases(),
            GROQ20B,
            models=started.append,
            serve=started.append,
            directory=tmp_path,
        )
    assert started == [] and not (tmp_path / "dev-groq20b.json").exists()


def test_missing_or_invalid_reference_stops_before_any_startup(tmp_path):
    with pytest.raises(ValueError, match="eval-dev first"):
        reference_run(tmp_path, metadata(cases(), GROQ20B))
    (tmp_path / "dev.json").write_text("invalid json")
    with pytest.raises(ValueError, match="eval-dev first"):
        reference_run(tmp_path, metadata(cases(), GROQ20B))


@pytest.mark.parametrize("cost", [-1, True, "unknown", float("nan")])
def test_invalid_saved_cost_is_rejected_without_exposing_contents(tmp_path, cost):
    saved, _, _ = evaluate_fake(tmp_path, settings=GROQ)
    saved["runtime_usage"]["estimated_cost_usd"] = cost
    (tmp_path / "dev.json").write_text(json.dumps(saved))
    with pytest.raises(ValueError, match="saved metrics are invalid"):
        reference_run(tmp_path, metadata(cases(), GROQ20B))


def test_fake_full_comparison_selects_runtime_by_settings_and_excludes_judge_tokens(tmp_path):
    evaluate_fake(tmp_path, settings=GROQ)
    started = []

    @contextmanager
    def models(settings):
        started.append(settings.runtime.model)
        assert settings.runtime.provider == settings.judge.provider == "groq"
        assert settings.runtime.key_variable == settings.judge.key_variable == "GROQ_API_KEY"
        assert settings.judge == GROQ.judge
        yield (
            MeteredModel(
                settings.runtime,
                FakeSender([ROUTED, PLAN]),
                UsageCapture(
                    requests=2, responses_with_usage=2, prompt_tokens=100, completion_tokens=20
                ),
            ),
            MeteredModel(
                settings.judge,
                FakeSender([{"answers_question": True}]),
                UsageCapture(
                    requests=1, responses_with_usage=1, prompt_tokens=9999, completion_tokens=9999
                ),
            ),
        )

    @contextmanager
    def serve(settings):
        started.append("fresh-api")
        yield settings

    result = run_live(
        "dev-groq20b",
        cases(),
        GROQ20B,
        models=models,
        serve=serve,
        directory=tmp_path,
        steps=Steps(retrieve=search),
    )
    assert started == [COMPARISON_RUNTIME_MODEL, "fresh-api"]
    assert result["runtime_usage"]["prompt_tokens"] == 100
    assert result["runtime_usage"]["completion_tokens"] == 20
    assert result["runtime_usage"]["estimated_cost_usd"] == 0.0000135
    assert result["metrics"]["accuracy"]["passed"] == 1
    assert result == json.loads((tmp_path / "dev-groq20b.json").read_text())
    text = (tmp_path / "dev-groq20b.md").read_text()
    assert "Development runtime comparison" in text and "unavailable | $0.00001350" in text


def test_comparison_make_target_selects_smaller_groq_runtime_using_settings_only():
    makefile = Path("Makefile").read_text()
    assert "eval-compare: export MERIDIAN_LLM := live" in makefile
    assert f"eval-compare: export MERIDIAN_RUNTIME_MODEL := {COMPARISON_RUNTIME_MODEL}" in makefile
    assert "eval-compare: export MERIDIAN_EXACT_MATCH := 1" in makefile
    assert "\t$(PY) -m eval.cli dev-groq20b\n" in makefile
