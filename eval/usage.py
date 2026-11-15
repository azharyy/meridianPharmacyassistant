"""Capture Groq token usage and estimate runtime cost from recorded provider token counts."""

from dataclasses import dataclass

import httpx

from assistant.llm import ModelClient
from assistant.settings import Role

PRICING_DATE = "2026-11-15"
PRICES = {
    ("groq", "openai/gpt-oss-120b"): {
        "input": 0.15,
        "cached_input": 0.075,
        "cache_write": None,
        "output": 0.60,
        "source": "https://console.groq.com/docs/model/openai/gpt-oss-120b",
    },
    ("groq", "openai/gpt-oss-20b"): {
        "input": 0.075,
        "cached_input": 0.037,
        "cache_write": None,
        "output": 0.30,
        "source": "https://console.groq.com/docs/model/openai/gpt-oss-20b",
    },
}


def token_counts(usage: dict) -> dict[str, int]:
    """Read required totals and the API's optional cache counters, which default to zero."""
    details = usage.get("prompt_tokens_details")
    details = {} if details is None else details
    if not isinstance(details, dict):
        raise ValueError("invalid prompt token details")
    counts = {
        "prompt_tokens": usage["prompt_tokens"],
        "completion_tokens": usage["completion_tokens"],
        "cached_tokens": details.get("cached_tokens", 0),
        "cache_write_tokens": details.get("cache_write_tokens", 0),
    }
    if any(type(value) is not int or value < 0 for value in counts.values()):
        raise ValueError("invalid token count")
    if counts["cached_tokens"] + counts["cache_write_tokens"] > counts["prompt_tokens"]:
        raise ValueError("cache counts exceed prompt tokens")
    return counts


@dataclass
class UsageCapture:
    """One model role's actual HTTP attempts and validated provider token totals."""

    requests: int = 0
    responses_with_usage: int = 0
    rate_limited: int = 0  # 429s return no completion, so they count as unbilled
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cached_tokens: int = 0
    cache_write_tokens: int = 0

    @property
    def complete(self) -> bool:
        """Every attempt either reported its usage or was refused with a 429."""
        return self.requests == self.responses_with_usage + self.rate_limited

    def request(self, request: httpx.Request) -> None:
        self.requests += 1

    def response(self, response: httpx.Response) -> None:
        if response.status_code == 429:
            self.rate_limited += 1
            return
        if not response.is_success:
            return
        try:
            response.read()
            counts = token_counts(response.json()["usage"])
        except (ValueError, KeyError, TypeError, AttributeError, httpx.TransportError):
            return
        self.responses_with_usage += 1
        for name, count in counts.items():
            setattr(self, name, getattr(self, name) + count)

    def estimated_cost(self, role: Role) -> float | None:
        price = PRICES.get((role.provider, role.model))
        if price is None or not self.complete:
            return None
        if self.cache_write_tokens:
            return None
        ordinary = self.prompt_tokens - self.cached_tokens
        total = (
            ordinary * price["input"]
            + self.cached_tokens * price["cached_input"]
            + self.completion_tokens * price["output"]
        )
        return round(total / 1_000_000, 12)

    def snapshot(self, role: Role) -> dict:
        names = ("prompt_tokens", "completion_tokens", "cached_tokens", "cache_write_tokens")
        return {
            "requests": self.requests,
            "responses_with_usage": self.responses_with_usage,
            "rate_limited": self.rate_limited,
            "complete": self.complete,
            **{name: getattr(self, name) if self.complete else None for name in names},
            "estimated_cost_usd": self.estimated_cost(role),
            "pricing": {
                "verified_on": PRICING_DATE,
                "usd_per_million_tokens": PRICES.get((role.provider, role.model)),
                "scope": "Runtime only; Groq text requests; judge excluded.",
            },
        }


@dataclass
class MeteredModel(ModelClient):
    """The shared model client with an eval-owned token collector."""

    usage: UsageCapture


def model_usage(model: ModelClient) -> dict:
    if isinstance(model, MeteredModel):
        return model.usage.snapshot(model.role)
    return {"complete": False, "estimated_cost_usd": None, "reason": "Usage was not captured."}
