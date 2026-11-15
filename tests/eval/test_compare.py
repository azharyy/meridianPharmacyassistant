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

DEFAULT = load_settings({"MERIDIAN_LLM": "live", "OPENCODE_API_KEY": "synthetic-opencode-key"})
COMPARE = load_settings(
    {
        "MERIDIAN_LLM": "live",
        "MERIDIAN_RUNTIME_MODEL": COMPARISON_RUNTIME_MODEL,
        "OPENCODE_API_KEY": "synthetic-opencode-key",
    }
)


def test_comparison_shows_accuracy_latency_and_actual_runtime_cost_with_pricing_sources(tmp_path):
    before, _, _ = evaluate_fake(tmp_path, settings=DEFAULT)
    after, _, _ = evaluate_fake(tmp_path, name="dev-compare", settings=COMPARE)
    before["runtime_usage"] = UsageCapture(
        requests=1, responses_with_usage=1, prompt_tokens=1000, completion_tokens=100
    ).snapshot(DEFAULT.runtime)
    after["runtime_usage"] = UsageCapture(
        requests=1, responses_with_usage=1, prompt_tokens=1000, completion_tokens=100
    ).snapshot(COMPARE.runtime)
    text = build(before, after)
    assert "| Metric | opencode glm-5.3-flash | opencode deepseek-v4.1-flash |" in text
    assert "| Answer accuracy | 1/1 (100.0%) | 1/1 (100.0%) |" in text
    assert "| Latency p50 / p95 |" in text
    assert "| Estimated runtime cost (USD) | $0.00020000 | $0.00042000 |" in text
    assert "reasoning tokens" in text and "Judge calls are excluded" in text
    assert "Rate-limited (429) attempts return no completion and count as unbilled" in text
    assert "monthly allowance instead of being billed" in text
    assert "[opencode glm-5.3-flash](https://opencode.ai/docs/go/)" in text
    assert "(peak rate, so an upper bound; off-peak is half)" in text
    assert "gpt-oss" not in text  # only the two compared runtimes are priced
    assert "## Failed opencode deepseek-v4.1-flash cases" in text and "2026-11-15" in text
    after["runtime_usage"]["unaccounted"] = 2
    assert "| $0.00020000 | at least $0.00042000 (2 attempts without usage) |" in build(
        before, after
    )
    after["runtime_usage"]["estimated_cost_usd"] = None
    assert "$0.00020000 | unavailable" in build(before, after)


@pytest.mark.parametrize(
    "changed",
    ["case_sha256", "implementation_sha256", "judge", "mode", "runtime", "exact_match", "usage"],
)
def test_stale_reference_stops_before_models_or_api_start(tmp_path, changed):
    saved, _, _ = evaluate_fake(tmp_path, settings=DEFAULT)
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
            "dev-compare",
            cases(),
            COMPARE,
            models=started.append,
            serve=started.append,
            directory=tmp_path,
        )
    assert started == [] and not (tmp_path / "dev-compare.json").exists()


def test_missing_or_invalid_reference_stops_before_any_startup(tmp_path):
    with pytest.raises(ValueError, match="eval-dev first"):
        reference_run(tmp_path, metadata(cases(), COMPARE))
    (tmp_path / "dev.json").write_text("invalid json")
    with pytest.raises(ValueError, match="eval-dev first"):
        reference_run(tmp_path, metadata(cases(), COMPARE))


@pytest.mark.parametrize("cost", [-1, True, "unknown", float("nan")])
def test_invalid_saved_cost_is_rejected_without_exposing_contents(tmp_path, cost):
    saved, _, _ = evaluate_fake(tmp_path, settings=DEFAULT)
    saved["runtime_usage"]["estimated_cost_usd"] = cost
    (tmp_path / "dev.json").write_text(json.dumps(saved))
    with pytest.raises(ValueError, match="saved metrics are invalid"):
        reference_run(tmp_path, metadata(cases(), COMPARE))


def test_fake_full_comparison_selects_runtime_by_settings_and_excludes_judge_tokens(tmp_path):
    evaluate_fake(tmp_path, settings=DEFAULT)
    started = []

    @contextmanager
    def models(settings):
        started.append(settings.runtime.model)
        assert settings.runtime.provider == settings.judge.provider == "opencode"
        assert settings.runtime.key_variable == settings.judge.key_variable == "OPENCODE_API_KEY"
        assert settings.judge == DEFAULT.judge
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
        "dev-compare",
        cases(),
        COMPARE,
        models=models,
        serve=serve,
        directory=tmp_path,
        steps=Steps(retrieve=search),
    )
    assert started == [COMPARISON_RUNTIME_MODEL, "fresh-api"]
    assert result["runtime_usage"]["prompt_tokens"] == 100
    assert result["runtime_usage"]["completion_tokens"] == 20
    assert result["runtime_usage"]["estimated_cost_usd"] == 0.000054
    assert result["metrics"]["accuracy"]["passed"] == 1
    assert result == json.loads((tmp_path / "dev-compare.json").read_text())
    text = (tmp_path / "dev-compare.md").read_text()
    assert "Development runtime comparison" in text and "unavailable | $0.00005400" in text


def test_comparison_make_target_selects_the_comparison_runtime_using_settings_only():
    makefile = Path("Makefile").read_text()
    assert "eval-compare: export MERIDIAN_LLM := live" in makefile
    assert "eval-compare: export MERIDIAN_RUNTIME_PROVIDER := opencode" in makefile
    assert f"eval-compare: export MERIDIAN_RUNTIME_MODEL := {COMPARISON_RUNTIME_MODEL}" in makefile
    assert "eval-compare: export MERIDIAN_EXACT_MATCH := 1" in makefile
    assert "\t$(PY) -m eval.cli dev-compare\n" in makefile
