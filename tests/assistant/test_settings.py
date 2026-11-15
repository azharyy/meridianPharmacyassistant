"""Settings come from one mapping of variables; a missing live key stops with a clear message."""

import re
from pathlib import Path

import pytest

from assistant.settings import COMPARISON_RUNTIME_MODEL, MissingKey, load_settings, runtime_role

ASSISTANT = Path(__file__).resolve().parents[2] / "assistant"


def test_defaults_are_the_fake_model_with_groq_as_the_runtime():
    settings = load_settings({})
    assert (settings.llm, settings.exact_match) == ("fake", True)
    assert settings.api_url == "http://127.0.0.1:8001"
    runtime = settings.runtime
    assert (runtime.provider, runtime.model) == ("groq", "openai/gpt-oss-120b")
    assert (runtime.base_url, runtime.reasoning_effort) == ("https://api.groq.com/openai/v1", "low")
    judge = settings.judge
    assert (judge.provider, judge.model) == ("groq", "qwen/qwen3.8-27b")
    assert (judge.base_url, judge.reasoning_effort, judge.timeout, judge.key_variable) == (
        "https://api.groq.com/openai/v1",
        "none",
        30.0,
        "GROQ_API_KEY",
    )
    assert runtime_role() == runtime


def test_the_runtime_moves_to_groq_20b_by_settings_alone():
    settings = load_settings({"MERIDIAN_RUNTIME_MODEL": COMPARISON_RUNTIME_MODEL})
    runtime = settings.runtime
    assert (runtime.provider, runtime.model) == ("groq", "openai/gpt-oss-20b")
    assert (runtime.base_url, runtime.key_variable) == (
        "https://api.groq.com/openai/v1",
        "GROQ_API_KEY",
    )
    assert settings.judge == load_settings({}).judge


@pytest.mark.parametrize("role_name", ["runtime", "judge"])
def test_live_without_the_groq_key_stops_and_names_it(role_name):
    settings = load_settings({"MERIDIAN_LLM": "live"})
    with pytest.raises(MissingKey, match="GROQ_API_KEY") as stopped:
        settings.api_key(getattr(settings, role_name))
    assert ".env" in str(stopped.value)


def test_a_key_is_returned_but_never_shown():
    settings = load_settings({"MERIDIAN_LLM": "live", "GROQ_API_KEY": " gsk_secret "})
    assert settings.api_key(settings.runtime) == "gsk_secret"
    assert settings.api_key(settings.judge) == "gsk_secret"
    assert "gsk_secret" not in repr(settings)


@pytest.mark.parametrize("role_name", ["runtime", "judge"])
def test_an_openai_key_is_ignored_and_cannot_replace_the_groq_key(role_name):
    settings = load_settings({"MERIDIAN_LLM": "live", "OPENAI_API_KEY": "ignored_secret"})
    assert not settings.keys
    with pytest.raises(MissingKey, match="GROQ_API_KEY"):
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
    ],
)
def test_unknown_values_are_rejected(env):
    with pytest.raises(ValueError):
        load_settings(env)


def test_exact_match_flag_and_api_url():
    settings = load_settings({"MERIDIAN_EXACT_MATCH": "0", "MERIDIAN_API_URL": "http://api:9000/"})
    assert (settings.exact_match, settings.api_url) == (False, "http://api:9000")


def test_legacy_groq_provider_still_uses_the_groq_runtime():
    assert load_settings({"MERIDIAN_RUNTIME_PROVIDER": "groq"}).runtime == runtime_role()


def test_no_other_module_reads_the_environment():
    reads = re.compile(r"\benviron\b|\bgetenv\b")
    offenders = [
        str(path.relative_to(ASSISTANT))
        for path in ASSISTANT.rglob("*.py")
        if path.name != "settings.py" and reads.search(path.read_text(encoding="utf-8"))
    ]
    assert not offenders
