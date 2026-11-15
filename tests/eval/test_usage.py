"""Capture retries and cache usage while marking missing provider token counts unavailable."""

import json
from dataclasses import replace

import httpx
import pytest

from assistant.llm import sdk_sender
from assistant.settings import COMPARISON_RUNTIME_MODEL, DEFAULT_RUNTIME_MODEL, runtime_role
from eval.judge.judge import Verdict
from eval.usage import MeteredModel, UsageCapture, token_counts


def body(role, usage):
    return {
        "id": "synthetic",
        "object": "chat.completion",
        "created": 0,
        "model": role.model,
        "choices": [
            {
                "index": 0,
                "finish_reason": "stop",
                "message": {"role": "assistant", "content": '{"answers_question":true}'},
            }
        ],
        "usage": usage,
    }


@pytest.mark.parametrize(
    "runtime_model,cost",
    [(DEFAULT_RUNTIME_MODEL, 0.000238), (COMPARISON_RUNTIME_MODEL, 0.0005106)],
)
def test_actual_sdk_response_hooks_capture_cache_counts_without_double_counting_reasoning(
    runtime_model, cost
):
    role, capture, requests = runtime_role(runtime_model), UsageCapture(), []
    usage = {
        "prompt_tokens": 1000,
        "completion_tokens": 200,
        "total_tokens": 1200,
        "prompt_tokens_details": {"cached_tokens": 100},
        "completion_tokens_details": {"reasoning_tokens": 150},
    }

    def send(request):
        requests.append(json.loads(request.content))
        return httpx.Response(200, json=body(role, usage))

    with httpx.Client(
        transport=httpx.MockTransport(send),
        event_hooks={"request": [capture.request], "response": [capture.response]},
    ) as http:
        model = MeteredModel(role, sdk_sender(role, "synthetic-key", http), capture)
        assert model.complete([{"role": "user", "content": "Synthetic question"}], Verdict)
    result = capture.snapshot(role)
    assert result["requests"] == result["responses_with_usage"] == 1
    assert result["unaccounted"] == 0 and result["completion_tokens"] == 200
    assert result["cached_tokens"] == 100 and result["cache_write_tokens"] == 0
    assert result["estimated_cost_usd"] == cost
    assert "2026-11-15" == result["pricing"]["verified_on"]
    assert "synthetic-key" not in json.dumps(result)
    assert "tools" not in requests[0]
    assert requests[0]["response_format"]["json_schema"]["strict"]
    assert role.provider == "opencode" and role.key_variable == "OPENCODE_API_KEY"


@pytest.mark.parametrize(
    "usage",
    [
        None,
        {},
        {"prompt_tokens": "10", "completion_tokens": 1},
        {"prompt_tokens": True, "completion_tokens": 1},
        {"prompt_tokens": 10, "completion_tokens": -1},
        {"prompt_tokens": 10, "completion_tokens": 1, "prompt_tokens_details": []},
        {
            "prompt_tokens": 10,
            "completion_tokens": 1,
            "prompt_tokens_details": {"cached_tokens": 8, "cache_write_tokens": 3},
        },
    ],
)
def test_missing_or_malformed_usage_is_unaccounted_and_never_priced(usage):
    capture = UsageCapture()
    capture.request(httpx.Request("POST", "https://model.test"))
    capture.response(httpx.Response(200, json={"usage": usage}))
    result = capture.snapshot(runtime_role())
    assert result["unaccounted"] == 1 and result["responses_with_usage"] == 0
    assert result["prompt_tokens"] == 0 and result["estimated_cost_usd"] == 0


def test_optional_cache_counters_default_to_zero_as_the_api_defines():
    assert token_counts({"prompt_tokens": 10, "completion_tokens": 5}) == {
        "prompt_tokens": 10,
        "completion_tokens": 5,
        "cached_tokens": 0,
        "cache_write_tokens": 0,
    }


def test_a_transport_failure_then_retry_does_not_disappear_from_usage_accounting():
    role, capture, calls = runtime_role(), UsageCapture(), []

    def send(request):
        calls.append(request)
        if len(calls) == 1:
            raise httpx.ReadTimeout("synthetic timeout", request=request)
        return httpx.Response(200, json=body(role, {"prompt_tokens": 10, "completion_tokens": 5}))

    with httpx.Client(
        transport=httpx.MockTransport(send),
        event_hooks={"request": [capture.request], "response": [capture.response]},
    ) as http:
        model = MeteredModel(role, sdk_sender(role, "synthetic-key", http), capture)
        assert model.complete([{"role": "user", "content": "Synthetic question"}], Verdict)
    result = capture.snapshot(role)
    assert result["requests"] == 2 and result["unaccounted"] == 1
    assert result["completion_tokens"] == 5 and result["estimated_cost_usd"] == 0.000004


def test_rate_limited_attempts_count_as_unbilled_but_other_failures_stay_unknown():
    role, capture = runtime_role(), UsageCapture()
    for response in (
        httpx.Response(429, headers={"Retry-After": "6"}),
        httpx.Response(200, json=body(role, {"prompt_tokens": 1000, "completion_tokens": 100})),
    ):
        capture.request(httpx.Request("POST", "https://model.test"))
        capture.response(response)
    result = capture.snapshot(role)
    assert (result["rate_limited"], result["unaccounted"]) == (1, 0)
    assert result["prompt_tokens"] == 1000 and result["estimated_cost_usd"] == 0.0002
    capture.request(httpx.Request("POST", "https://model.test"))
    capture.response(httpx.Response(500))  # unknown cost: counted, never priced
    result = capture.snapshot(role)
    assert result["unaccounted"] == 1 and result["estimated_cost_usd"] == 0.0002


def test_unknown_pricing_and_unsupported_cache_writes_are_unavailable():
    role = runtime_role()
    capture = UsageCapture(requests=1, responses_with_usage=1, prompt_tokens=100)
    assert capture.estimated_cost(replace(role, model="unknown")) is None
    capture.cache_write_tokens = 10
    assert capture.estimated_cost(role) is None
    empty = UsageCapture().snapshot(role)
    assert empty["unaccounted"] == 0 and empty["estimated_cost_usd"] == 0


def test_non_json_and_failed_responses_do_not_fabricate_usage():
    capture = UsageCapture(requests=2)
    capture.response(httpx.Response(200, text="not json"))
    capture.response(httpx.Response(429, json={"usage": {"prompt_tokens": 10}}))
    assert capture.responses_with_usage == 0 and capture.prompt_tokens == 0
    assert (capture.rate_limited, capture.unaccounted) == (1, 1)
