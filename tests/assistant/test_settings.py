"""Settings come from one mapping of variables; a missing live key stops with a clear message."""

import re
from pathlib import Path

import pytest

from assistant.settings import MissingKey, load_settings

ASSISTANT = Path(__file__).resolve().parents[2] / "assistant"


def test_defaults_are_the_fake_model_with_groq_as_the_runtime():
    settings = load_settings({})
    assert (settings.llm, settings.exact_match) == ("fake", True)
    assert settings.api_url == "http://127.0.0.1:8001"
    runtime = settings.runtime
    assert (runtime.provider, runtime.model) == ("groq", "openai/gpt-oss-120b")
    assert (runtime.base_url, runtime.reasoning_effort) == ("https://api.groq.com/openai/v1", "low")
    assert (settings.judge.provider, settings.judge.model) == ("openai", "gpt-6-luna")


def test_the_runtime_moves_to_openai_by_settings_alone():
    runtime = load_settings({"MERIDIAN_RUNTIME_PROVIDER": "openai"}).runtime
    assert (runtime.provider, runtime.model) == ("openai", "gpt-6-luna")
    assert (runtime.base_url, runtime.key_variable) == (
        "https://api.openai.com/v1",
        "OPENAI_API_KEY",
    )


@pytest.mark.parametrize(
    ("provider", "variable"), [("groq", "GROQ_API_KEY"), ("openai", "OPENAI_API_KEY")]
)
def test_live_without_the_key_stops_and_names_it(provider, variable):
    settings = load_settings({"MERIDIAN_LLM": "live", "MERIDIAN_RUNTIME_PROVIDER": provider})
    with pytest.raises(MissingKey, match=variable) as stopped:
        settings.api_key(settings.runtime)
    assert ".env" in str(stopped.value)


def test_a_key_is_returned_but_never_shown():
    settings = load_settings({"MERIDIAN_LLM": "live", "GROQ_API_KEY": " gsk_secret "})
    assert settings.api_key(settings.runtime) == "gsk_secret"
    assert "gsk_secret" not in repr(settings)


@pytest.mark.parametrize(
    "env",
    [
        {"MERIDIAN_LLM": "maybe"},
        {"MERIDIAN_EXACT_MATCH": "yes"},
        {"MERIDIAN_RUNTIME_PROVIDER": "elsewhere"},
    ],
)
def test_unknown_values_are_rejected(env):
    with pytest.raises(ValueError):
        load_settings(env)


def test_exact_match_flag_and_api_url():
    settings = load_settings({"MERIDIAN_EXACT_MATCH": "0", "MERIDIAN_API_URL": "http://api:9000/"})
    assert (settings.exact_match, settings.api_url) == (False, "http://api:9000")


def test_no_other_module_reads_the_environment():
    reads = re.compile(r"\benviron\b|\bgetenv\b")
    offenders = [
        str(path.relative_to(ASSISTANT))
        for path in ASSISTANT.rglob("*.py")
        if path.name != "settings.py" and reads.search(path.read_text(encoding="utf-8"))
    ]
    assert not offenders
