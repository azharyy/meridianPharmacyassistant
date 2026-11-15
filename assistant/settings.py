"""Read every environment variable the assistant uses, once, into typed settings.

No other module reads the environment. Keys never appear in a repr, so logging the settings
can't leak one. The assistant never reads MERIDIAN_STAFF_KEY: only the mock API holds it.
"""

import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Literal

GROQ_URL = "https://api.groq.com/openai/v1"
OPENAI_URL = "https://api.openai.com/v1"
DEFAULT_API_URL = "http://127.0.0.1:8001"
KEY_VARIABLES = ("GROQ_API_KEY", "OPENAI_API_KEY")
RUNTIME_TIMEOUT = 8.0
JUDGE_TIMEOUT = 30.0


class MissingKey(SystemExit):
    """Live mode without the key a role needs: stops the program with a clear message."""


@dataclass(frozen=True)
class Role:
    """Who answers one kind of model call, and how."""

    provider: Literal["groq", "openai"]
    base_url: str
    model: str
    reasoning_effort: str
    timeout: float  # seconds for one request
    key_variable: str  # the environment variable that holds this provider's key


def runtime_role(provider: str) -> Role:
    """The assistant's model: gpt-oss-120b on Groq, or GPT-6 Luna on OpenAI for the comparison."""
    if provider == "openai":
        return Role("openai", OPENAI_URL, "gpt-6-luna", "low", RUNTIME_TIMEOUT, "OPENAI_API_KEY")
    return Role("groq", GROQ_URL, "openai/gpt-oss-120b", "low", RUNTIME_TIMEOUT, "GROQ_API_KEY")


JUDGE = Role("openai", OPENAI_URL, "gpt-6-luna", "low", JUDGE_TIMEOUT, "OPENAI_API_KEY")


@dataclass(frozen=True)
class Settings:
    llm: Literal["fake", "live"]
    exact_match: bool
    api_url: str
    runtime: Role
    judge: Role
    keys: Mapping[str, str] = field(repr=False)

    def api_key(self, role: Role) -> str:
        """The key a live role needs; stops with a message naming it when it's missing."""
        key = self.keys.get(role.key_variable)
        if not key:
            raise MissingKey(
                f"MERIDIAN_LLM=live needs {role.key_variable}, and it is not set. Add it to the "
                ".env file in the repo root: copy .env.example to .env and fill it in."
            )
        return key


def choice(env: Mapping[str, str], name: str, default: str, allowed: tuple[str, ...]) -> str:
    value = env.get(name, "").strip().lower() or default
    if value not in allowed:
        raise ValueError(f"{name} must be one of {', '.join(allowed)}, not {value!r}")
    return value


def load_settings(env: Mapping[str, str] = os.environ) -> Settings:
    """Settings from a mapping of variables: the real environment, or a dict in a test."""
    keys = {name: env[name].strip() for name in KEY_VARIABLES if env.get(name, "").strip()}
    return Settings(
        llm=choice(env, "MERIDIAN_LLM", "fake", ("fake", "live")),  # type: ignore[arg-type]
        exact_match=choice(env, "MERIDIAN_EXACT_MATCH", "1", ("0", "1")) == "1",
        api_url=(env.get("MERIDIAN_API_URL", "").strip() or DEFAULT_API_URL).rstrip("/"),
        runtime=runtime_role(choice(env, "MERIDIAN_RUNTIME_PROVIDER", "groq", ("groq", "openai"))),
        judge=JUDGE,
        keys=keys,
    )
