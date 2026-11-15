"""Ask a model for one structured output: the real client over the OpenAI SDK, and a scripted fake.

Every call uses strict structured outputs and never carries `tools`. A call makes at most two
attempts: a transport error or an output that fails validation is retried once, and then the
caller gets ModelUnavailable, which the pipeline turns into the fallback reply.
"""

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TypeVar

import httpx
import openai
from pydantic import BaseModel, ValidationError

from assistant.settings import Role, Settings

Output = TypeVar("Output", bound=BaseModel)
Messages = list[dict[str, str]]
Send = Callable[[Messages, type[BaseModel]], str]  # one request; returns the raw JSON text


class ModelUnavailable(Exception):
    """No valid output after one retry."""


class TransportError(Exception):
    """One request failed: a timeout, a rate limit, a lost connection or an error status."""


@dataclass
class ModelClient:
    """One role's model, behind a `send` function: the SDK in live mode, a script otherwise."""

    role: Role
    send: Send

    def complete(self, messages: Messages, output: type[Output]) -> Output:
        problem: Exception | None = None
        for _attempt in range(2):
            try:
                return output.model_validate_json(self.send(messages, output))
            except (TransportError, ValidationError) as error:
                problem = error
        reason = type(problem).__name__
        raise ModelUnavailable(f"no valid {output.__name__} after a retry ({reason})") from problem


def response_format(output: type[BaseModel]) -> dict:
    schema = output.model_json_schema()
    return {
        "type": "json_schema",
        "json_schema": {"name": output.__name__, "schema": schema, "strict": True},
    }


def sdk_sender(role: Role, api_key: str, http_client: httpx.Client | None = None) -> Send:
    """A `send` that calls the role's provider through the OpenAI SDK, with no SDK retries."""
    client = openai.OpenAI(
        api_key=api_key,
        base_url=role.base_url,
        timeout=role.timeout,
        max_retries=0,
        http_client=http_client,
    )

    def send(messages: Messages, output: type[BaseModel]) -> str:
        try:
            completion = client.chat.completions.create(
                model=role.model,
                messages=messages,  # type: ignore[arg-type]
                response_format=response_format(output),  # type: ignore[arg-type]
                reasoning_effort=role.reasoning_effort,  # type: ignore[arg-type]
            )
        except openai.APIError as error:
            raise TransportError(type(error).__name__) from error
        return completion.choices[0].message.content or ""

    return send


@dataclass
class FakeSender:
    """Scripted responses, used in order, and a record of every request made."""

    script: list[str | dict | BaseModel | Exception] = field(default_factory=list)
    requests: list[tuple[Messages, str]] = field(default_factory=list)

    def __call__(self, messages: Messages, output: type[BaseModel]) -> str:
        self.requests.append((messages, output.__name__))
        if not self.script:
            raise TransportError("no scripted response left")
        item = self.script.pop(0)
        if isinstance(item, Exception):
            raise item
        if isinstance(item, BaseModel):
            return item.model_dump_json()
        return item if isinstance(item, str) else json.dumps(item)


def make_client(settings: Settings, role: Role, fake: FakeSender | None = None) -> ModelClient:
    """The client for a role: the scripted fake unless MERIDIAN_LLM=live."""
    if settings.llm == "live":
        return ModelClient(role, sdk_sender(role, settings.api_key(role)))
    return ModelClient(role, fake if fake is not None else FakeSender())
