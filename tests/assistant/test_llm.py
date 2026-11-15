"""The model client: strict structured output with no tools, one retry, then ModelUnavailable."""

import json

import httpx
import pytest

from assistant.llm import (
    FakeSender,
    ModelClient,
    ModelUnavailable,
    TransportError,
    make_client,
    sdk_sender,
)
from assistant.settings import MissingKey, Role, load_settings
from contracts.router import RouterOutput

ROUTED = {
    "intent": "product_info",
    "risk_label": "none",
    "product_mentions": [],
    "label_sections": ["directions"],
    "store_topic": None,
}
MESSAGES = [{"role": "user", "content": "How do I take it?"}]
SETTINGS = load_settings({})
RUNTIME = SETTINGS.runtime


def completion(content: str) -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "id": "chatcmpl-1",
            "object": "chat.completion",
            "created": 0,
            "model": RUNTIME.model,
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": content},
                    "finish_reason": "stop",
                }
            ],
        },
    )


def live_client(
    *answers: httpx.Response | str, role: Role = RUNTIME
) -> tuple[ModelClient, list[httpx.Request]]:
    """The real SDK sender, with each HTTP call answered in turn; "timeout" raises a timeout."""
    seen: list[httpx.Request] = []
    queue = list(answers)

    def handle(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        answer = queue.pop(0)
        if answer == "timeout":
            raise httpx.ReadTimeout("timed out", request=request)
        return answer

    http = httpx.Client(transport=httpx.MockTransport(handle))
    return ModelClient(role, sdk_sender(role, "gsk_test", http_client=http)), seen


@pytest.mark.parametrize(
    ("provider", "url", "model"),
    [
        ("groq", "https://api.groq.com/openai/v1/chat/completions", "openai/gpt-oss-120b"),
        (
            "opencode",
            "https://opencode.ai/inference/go/openai/v1/chat/completions",
            "glm-5.3-flash",
        ),
    ],
)
def test_the_request_is_strict_structured_output_without_tools(provider, url, model):
    role = load_settings({"MERIDIAN_RUNTIME_PROVIDER": provider}).runtime
    client, seen = live_client(completion(json.dumps(ROUTED)), role=role)
    assert client.complete(MESSAGES, RouterOutput) == RouterOutput(**ROUTED)
    assert str(seen[0].url) == url
    assert seen[0].headers["authorization"] == "Bearer gsk_test"
    body = json.loads(seen[0].content)
    assert "tools" not in body
    assert (body["model"], body["reasoning_effort"]) == (model, "low")
    assert body["messages"] == MESSAGES
    response_format = body["response_format"]
    assert response_format["type"] == "json_schema"
    assert response_format["json_schema"]["strict"] is True
    assert response_format["json_schema"]["schema"] == RouterOutput.model_json_schema()


@pytest.mark.parametrize(
    "failure",
    ["timeout", httpx.Response(429, json={"error": {"message": "rate limited"}})],
    ids=["timeout", "rate_limit"],
)
def test_a_transport_failure_is_retried_once_then_the_model_is_unavailable(failure):
    client, seen = live_client(failure, failure)
    with pytest.raises(ModelUnavailable):
        client.complete(MESSAGES, RouterOutput)
    assert len(seen) == 2


def test_a_transport_failure_then_a_good_answer_succeeds():
    client, seen = live_client("timeout", completion(json.dumps(ROUTED)))
    assert client.complete(MESSAGES, RouterOutput).intent == "product_info"
    assert len(seen) == 2


def test_invalid_output_is_retried_once():
    client, seen = live_client(completion('{"intent": "invented"}'), completion(json.dumps(ROUTED)))
    assert client.complete(MESSAGES, RouterOutput) == RouterOutput(**ROUTED)
    assert len(seen) == 2


def test_output_still_invalid_after_the_retry_means_unavailable():
    client, seen = live_client(completion("not json"), completion('{"intent": "invented"}'))
    with pytest.raises(ModelUnavailable):
        client.complete(MESSAGES, RouterOutput)
    assert len(seen) == 2


def test_the_fake_is_the_default_and_replays_its_script():
    fake = FakeSender([TransportError("timeout"), RouterOutput(**ROUTED)])
    client = make_client(SETTINGS, RUNTIME, fake)
    assert client.complete(MESSAGES, RouterOutput) == RouterOutput(**ROUTED)
    assert fake.requests == [(MESSAGES, "RouterOutput"), (MESSAGES, "RouterOutput")]
    assert isinstance(make_client(SETTINGS, RUNTIME).send, FakeSender)


def test_an_empty_script_means_the_model_is_unavailable():
    with pytest.raises(ModelUnavailable):
        make_client(SETTINGS, RUNTIME).complete(MESSAGES, RouterOutput)


@pytest.mark.parametrize("role_name", ["runtime", "judge"])
def test_live_mode_uses_the_sdk_and_both_roles_need_the_groq_key(role_name):
    live = load_settings({"MERIDIAN_LLM": "live", "GROQ_API_KEY": "gsk_test"})
    assert not isinstance(make_client(live, getattr(live, role_name)).send, FakeSender)
    missing = load_settings({"MERIDIAN_LLM": "live", "OPENAI_API_KEY": "ignored_test"})
    with pytest.raises(MissingKey, match="GROQ_API_KEY"):
        make_client(missing, getattr(missing, role_name))
