"""An evaluation owns one hidden mock API process and always releases it."""

import subprocess

import httpx
import pytest

from assistant.settings import load_settings
from eval.local_api import command, local_api, ready, stop


class Server:
    def __init__(self, exited=False, stubborn=False):
        self.exited = exited
        self.stubborn = stubborn
        self.terminated = self.killed = False

    def poll(self):
        return 0 if self.exited else None

    def terminate(self):
        self.terminated = True

    def kill(self):
        self.killed = True

    def wait(self, timeout):
        if self.stubborn and not self.killed:
            raise subprocess.TimeoutExpired("synthetic-server", timeout)
        self.exited = True
        return 0


def test_an_isolated_server_has_a_temporary_url_and_is_stopped_on_body_failure():
    started, clients = [], []
    server = Server()

    def start(args, **kwargs):
        started.append((args, kwargs))
        return server

    def client(**kwargs):
        http = httpx.Client(**kwargs, transport=httpx.MockTransport(lambda r: httpx.Response(200)))
        clients.append(http)
        return http

    original = load_settings({})
    with (
        pytest.raises(RuntimeError, match="body failure"),
        local_api(original, start=start, port=49123, client=client) as isolated,
    ):
        assert isolated.api_url == "http://127.0.0.1:49123"
        assert original.api_url != isolated.api_url
        raise RuntimeError("body failure")
    args, kwargs = started[0]
    assert args == command(49123) and "--no-access-log" in args
    assert kwargs["creationflags"] == getattr(subprocess, "CREATE_NO_WINDOW", 0)
    assert kwargs["stdout"] == kwargs["stderr"] == subprocess.DEVNULL
    assert server.terminated and server.exited and clients[0].is_closed


def test_readiness_retries_transport_failures_and_then_succeeds():
    attempts, pauses = [], []

    def request(request):
        attempts.append(request)
        if len(attempts) == 1:
            raise httpx.ConnectError("not ready")
        return httpx.Response(200)

    with httpx.Client(base_url="http://api.test", transport=httpx.MockTransport(request)) as http:
        ready(Server(), http, pauses.append)
    assert len(attempts) == 2 and pauses == [0.1]


@pytest.mark.parametrize("exited", [False, True])
def test_startup_failure_always_stops_the_server(exited):
    server, clients = Server(exited=exited), []

    def client(**kwargs):
        http = httpx.Client(**kwargs, transport=httpx.MockTransport(lambda r: httpx.Response(503)))
        clients.append(http)
        return http

    with (
        pytest.raises(RuntimeError, match="evaluation mock API"),
        local_api(
            load_settings({}),
            start=lambda *a, **k: server,
            port=49124,
            client=client,
            pause=lambda seconds: None,
        ),
    ):
        pytest.fail("an unavailable server must not yield")
    assert server.exited and clients[0].is_closed
    assert server.terminated is not exited


def test_a_server_that_ignores_termination_is_killed_and_reaped():
    server = Server(stubborn=True)
    stop(server)
    assert server.terminated and server.killed and server.exited
