"""Settings come from one mapping of variables; a missing live key stops with a clear message."""

import re
from pathlib import Path

import pytest

from assistant.settings import MissingKey, load_settings, runtime_role

ASSISTANT = Path(__file__).resolve().parents[2] / "assistant"
GO = "https://opencode.ai/inference/go/openai/v1"


def test_defaults_are_the_fake_model_with_opencode_go_for_every_role():
    settings = load_settings({})
    assert (settings.llm, settings.exact_match) == ("fake", True)
    assert settings.api_url == "http://127.0.0.1:8001"
    runtime = settings.runtime
    assert (runtime.provider, runtime.model, runtime.reasoning_effort) == (
        "opencode",
        "glm-5.3-flash",
        "low",
    )
    assert (runtime.base_url, runtime.key_variable) == (GO, "OPENCODE_API_KEY")
    judge = settings.judge
    assert (judge.provider, judge.model) == ("opencode", "kimi-k3.1-pro")
    assert (judge.base_url, judge.reasoning_effort, judge.timeout, judge.key_variable) == (
        GO,
        "low",
        30.0,
        "OPENCODE_API_KEY",
    )
    assert runtime_role() == runtime


@pytest.mark.parametrize(
    ("model", "expected"),
    [(None, "openai/gpt-oss-120b"), ("openai/gpt-oss-20b", "openai/gpt-oss-20b")],
)
def test_the_runtime_moves_to_groq_by_settings_alone(model, expected):
    env = {"MERIDIAN_RUNTIME_PROVIDER": "groq"}
    settings = load_settings(env | ({"MERIDIAN_RUNTIME_MODEL": model} if model else {}))
    runtime = settings.runtime
    assert (runtime.provider, runtime.model) == ("groq", expected)
    assert (runtime.base_url, runtime.key_variable) == (
        "https://api.groq.com/openai/v1",
        "GROQ_API_KEY",
    )
    assert runtime == runtime_role(expected, "groq")
    assert settings.judge == load_settings({}).judge


@pytest.mark.parametrize("role_name", ["runtime", "judge"])
def test_live_without_the_opencode_key_stops_and_names_it(role_name):
    settings = load_settings({"MERIDIAN_LLM": "live"})
    with pytest.raises(MissingKey, match="OPENCODE_API_KEY") as stopped:
        settings.api_key(getattr(settings, role_name))
    assert ".env" in str(stopped.value)


def test_a_key_is_returned_but_never_shown():
    settings = load_settings({"MERIDIAN_LLM": "live", "OPENCODE_API_KEY": " oc_secret "})
    assert settings.api_key(settings.runtime) == "oc_secret"
    assert settings.api_key(settings.judge) == "oc_secret"
    assert "oc_secret" not in repr(settings)


def test_a_groq_runtime_needs_the_groq_key_while_the_judge_keeps_opencode():
    env = {"MERIDIAN_LLM": "live", "MERIDIAN_RUNTIME_PROVIDER": "groq", "OPENCODE_API_KEY": "oc"}
    settings = load_settings(env)
    with pytest.raises(MissingKey, match="GROQ_API_KEY"):
        settings.api_key(settings.runtime)
    assert settings.api_key(settings.judge) == "oc"


@pytest.mark.parametrize("role_name", ["runtime", "judge"])
def test_an_openai_key_is_ignored_and_cannot_replace_the_opencode_key(role_name):
    settings = load_settings({"MERIDIAN_LLM": "live", "OPENAI_API_KEY": "ignored_secret"})
    assert not settings.keys
    with pytest.raises(MissingKey, match="OPENCODE_API_KEY"):
        settings.api_key(getattr(settings, role_name))


@pytest.mark.parametrize(
    "env",
    [
        {"MERIDIAN_LLM": "maybe"},
        {"MERIDIAN_EXACT_MATCH": "yes"},
        {"MERIDIAN_RUNTIME_PROVIDER": "elsewhere"},
        {"MERIDIAN_RUNTIME_PROVIDER": "openai"},
        {"MERIDIAN_RUNTIME_MODEL": "gpt-6-luna"},
        {"MERIDIAN_RUNTIME_MODEL": "qwen/qwen3.8-27b"},
        {
            "MERIDIAN_RUNTIME_MODEL": "openai/gpt-oss-120b"
        },  # a Groq model needs MERIDIAN_RUNTIME_PROVIDER=groq
        {"MERIDIAN_RUNTIME_PROVIDER": "groq", "MERIDIAN_RUNTIME_MODEL": "glm-5.3-flash"},
        {"MERIDIAN_RUNTIME_PROVIDER": "opencode", "MERIDIAN_RUNTIME_MODEL": "openai/gpt-oss-120b"},
        {"MERIDIAN_RUNTIME_PROVIDER": "opencode", "MERIDIAN_RUNTIME_MODEL": "beam-free"},
        {"MERIDIAN_RUNTIME_PROVIDER": "opencode", "MERIDIAN_RUNTIME_MODEL": "deepseek-v4.1-flash"},
        {"MERIDIAN_RUNTIME_PROVIDER": "opencode", "MERIDIAN_RUNTIME_MODEL": "kimi-k3"},
    ],
)
def test_unknown_values_are_rejected(env):
    with pytest.raises(ValueError):
        load_settings(env)


def test_exact_match_flag_and_api_url():
    settings = load_settings({"MERIDIAN_EXACT_MATCH": "0", "MERIDIAN_API_URL": "http://api:9000/"})
    assert (settings.exact_match, settings.api_url) == (False, "http://api:9000")


@pytest.mark.parametrize(
    ("model", "expected"),
    [(None, "glm-5.3-flash"), ("glm-5.3", "glm-5.3")],
)
def test_the_runtime_moves_to_an_opencode_go_model_by_settings_alone(model, expected):
    env = {"MERIDIAN_RUNTIME_PROVIDER": "opencode"}
    settings = load_settings(env | ({"MERIDIAN_RUNTIME_MODEL": model} if model else {}))
    runtime = settings.runtime
    assert (runtime.provider, runtime.model, runtime.reasoning_effort) == (
        "opencode",
        expected,
        "low",
    )
    assert (runtime.base_url, runtime.key_variable) == (
        "https://opencode.ai/inference/go/openai/v1",
        "OPENCODE_API_KEY",
    )
    assert settings.judge == load_settings({}).judge  # choosing a runtime never moves the judge


def test_an_opencode_runtime_needs_its_own_key_which_is_never_shown():
    env = {"MERIDIAN_LLM": "live", "MERIDIAN_RUNTIME_PROVIDER": "opencode", "GROQ_API_KEY": "gsk_x"}
    with pytest.raises(MissingKey, match="OPENCODE_API_KEY"):
        load_settings(env).api_key(load_settings(env).runtime)
    settings = load_settings(env | {"OPENCODE_API_KEY": " oc_secret "})
    assert settings.api_key(settings.runtime) == "oc_secret"
    assert "oc_secret" not in repr(settings)


def test_no_other_module_reads_the_environment():
    reads = re.compile(r"\benviron\b|\bgetenv\b")
    offenders = [
        str(path.relative_to(ASSISTANT))
        for path in ASSISTANT.rglob("*.py")
        if path.name != "settings.py" and reads.search(path.read_text(encoding="utf-8"))
    ]
    assert not offenders
