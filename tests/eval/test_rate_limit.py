"""Eval retries respect Retry-After while runtime backoff remains in stage latency."""

import httpx
import openai
import pytest

from assistant import pipeline
from assistant.llm import FakeSender, ModelClient, ModelUnavailable, TransportError, sdk_sender
from assistant.settings import load_settings
from eval.judge.judge import Verdict
from eval.metrics.latency import score as latency
from eval.rate_limit import rate_limited_sender, retry_after
from eval.runner import run_cases
from tests.assistant.fixtures import PLAN, ROUTED, search
from tests.eval.test_runner import case, chat, no_api

ROLE = load_settings({}).judge
MESSAGES = [{"role": "user", "content": "Synthetic evidence"}]


def limited(header="6", status=429):
    request = httpx.Request("POST", "https://model.test/chat/completions")
    response = httpx.Response(status, request=request, headers={"Retry-After": header})
    error = TransportError("safe provider error type")
    error.__cause__ = openai.APIStatusError("synthetic-private-body", response=response, body=None)
    return error


def test_judge_retries_429_after_the_requested_wait_without_changing_its_messages_or_schema(capsys):
    pauses, requests = [], []

    def transport(request):
        requests.append(request)
        if len(requests) == 1:
            return httpx.Response(
                429,
                headers={"Retry-After": "6"},
                json={"error": {"message": "synthetic-private-body"}},
            )
        return httpx.Response(
            200, json={"choices": [{"message": {"content": '{"answers_question":true}'}}]}
        )

    with httpx.Client(transport=httpx.MockTransport(transport)) as http:
        sender = rate_limited_sender(sdk_sender(ROLE, "synthetic-key", http), ROLE, pauses.append)
        result = ModelClient(ROLE, sender).complete(MESSAGES, Verdict)
    assert result.answers_question and pauses == [6.0] and len(requests) == 2
    assert requests[0].content == requests[1].content
    assert "synthetic-private" not in capsys.readouterr().out


@pytest.mark.parametrize(
    "header", ["", "bad", "nan", "inf", "-1", "61", "Wed, 21 Oct 2015 07:28:00 GMT"]
)
def test_invalid_or_excessive_retry_after_never_sleeps_or_adds_a_retry(header):
    pauses = []
    fake = FakeSender([limited(header), {"answers_question": True}])
    with pytest.raises(TransportError):
        rate_limited_sender(fake, ROLE, pauses.append)(MESSAGES, Verdict)
    assert pauses == [] and len(fake.requests) == 1


@pytest.mark.parametrize("seconds", ["0", "0.5", "60"])
def test_safe_numeric_retry_after_values_are_accepted(seconds):
    assert retry_after(limited(seconds)) == float(seconds)


@pytest.mark.parametrize("status", [400, 401, 403, 500, 503])
def test_other_http_errors_never_sleep_or_add_a_retry(status):
    pauses = []
    fake = FakeSender([limited(status=status)])
    with pytest.raises(TransportError):
        rate_limited_sender(fake, ROLE, pauses.append)(MESSAGES, Verdict)
    assert pauses == [] and len(fake.requests) == 1


def test_errors_without_an_http_response_keep_the_existing_failure_behavior():
    fake = FakeSender([TransportError("synthetic transport failure")])
    pauses = []
    with pytest.raises(TransportError):
        rate_limited_sender(fake, ROLE, pauses.append)(MESSAGES, Verdict)
    assert pauses == [] and len(fake.requests) == 1


def test_repeated_rate_limits_exhaust_the_bounded_eval_retries():
    fake = FakeSender([limited()] * 6)
    pauses = []
    model = ModelClient(ROLE, rate_limited_sender(fake, ROLE, pauses.append))
    with pytest.raises(ModelUnavailable):
        model.complete(MESSAGES, Verdict)
    # Two shared-client attempts, each with at most two additional eval retries.
    assert len(fake.requests) == 6 and pauses == [6.0] * 4


def test_runtime_rate_limit_recovery_is_included_in_recorded_stage_latency(monkeypatch):
    settings, clock, requests = load_settings({}), [0.0], []
    monkeypatch.setattr(pipeline.time, "perf_counter", lambda: clock[0])

    def pause(seconds):
        clock[0] += seconds

    def transport(request):
        requests.append(request)
        if len(requests) == 2:
            return httpx.Response(429, headers={"Retry-After": "12"})
        output = ROUTED if len(requests) == 1 else PLAN
        return httpx.Response(
            200, json={"choices": [{"message": {"content": output.model_dump_json()}}]}
        )

    with httpx.Client(transport=httpx.MockTransport(transport)) as http, no_api() as api:
        send = rate_limited_sender(
            sdk_sender(settings.runtime, "synthetic-key", http), settings.runtime, pause
        )
        model = ModelClient(settings.runtime, send)
        [record] = run_cases([case(chat())], settings, model, api, pipeline.Steps(retrieve=search))
    assert record.turns[0].reply.reply_type.value == "label_sections" and len(requests) == 3
    assert record.turns[0].timings["catalog_agent"] == 12_000
    assert latency([record])["p95_ms"] == 12_000


def test_an_emergency_never_enters_model_retries_or_waits():
    settings, pauses, fake = load_settings({}), [], FakeSender([limited()])
    model = ModelClient(
        settings.runtime, rate_limited_sender(fake, settings.runtime, pauses.append)
    )
    steps = pipeline.Steps(emergency=lambda message: True)
    with no_api() as api:
        [record] = run_cases([case(chat())], settings, model, api, steps)
    assert record.turns[0].reply.emergency
    assert pauses == [] and fake.requests == []
