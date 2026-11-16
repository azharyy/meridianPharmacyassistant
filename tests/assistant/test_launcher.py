"""The launcher starts both servers as plain commands and checks the live key before anything."""

import re

import pytest
from fastapi.testclient import TestClient

from api.app import app as api
from assistant import launcher
from assistant.app import create_app
from assistant.settings import MissingKey, load_settings

LIVE = load_settings({"MERIDIAN_LLM": "live", "OPENCODE_API_KEY": "oc_test"})


class FakeServer:
    """A server process that stops after a number of polls, or when terminated."""

    def __init__(self, command, polls_until_exit=10_000):
        self.command = command
        self.polls_left = polls_until_exit
        self.terminated = False

    def poll(self):
        self.polls_left -= 1
        return 0 if self.terminated or self.polls_left < 0 else None

    def terminate(self):
        self.terminated = True

    def wait(self):
        return 0


def interrupt():
    raise KeyboardInterrupt


def test_the_commands_start_the_api_on_8001_and_the_assistant_on_8000():
    api, assistant = launcher.commands("python")
    assert api == ["python", "-m", "uvicorn", "api.app:app", "--port", "8001"]
    assert assistant == [
        "python",
        "-m",
        "uvicorn",
        "assistant.app:create_app",
        "--factory",
        "--port",
        "8000",
    ]


def test_live_mode_without_the_key_stops_before_starting_anything():
    started = []
    with pytest.raises(MissingKey, match="OPENCODE_API_KEY"):
        launcher.main(load_settings({"MERIDIAN_LLM": "live"}), start=started.append)
    assert started == []


def test_every_link_the_launcher_prints_opens_a_page(capsys):
    launcher.main(LIVE, start=FakeServer, wait=interrupt)
    links = re.findall(r"http://localhost:(\d+)(/[^\s,)]*)?", capsys.readouterr().out)
    with TestClient(create_app(load_settings({}))) as assistant, TestClient(api) as mock_api:
        clients = {"8000": assistant, "8001": mock_api}
        opened = [clients[port].get(path or "/").status_code for port, path in links]
    assert opened and opened == [200] * len(opened)


def test_ctrl_c_stops_both_servers():
    servers = []

    def start(command):
        servers.append(FakeServer(command))
        return servers[-1]

    launcher.main(LIVE, start=start, wait=interrupt)
    assert [server.command for server in servers] == launcher.commands()
    assert all(server.terminated for server in servers)


def test_when_one_server_stops_the_other_is_stopped_too():
    servers = []

    def start(command):
        polls = 1 if "api.app:app" in command else 10_000
        servers.append(FakeServer(command, polls_until_exit=polls))
        return servers[-1]

    launcher.main(LIVE, start=start, wait=lambda: None)
    api, assistant = servers
    assert (api.terminated, assistant.terminated) == (False, True)


def test_the_fake_model_needs_no_key():
    servers = []
    launcher.main(
        load_settings({}),
        start=lambda c: servers.append(FakeServer(c)) or servers[-1],
        wait=interrupt,
    )
    assert len(servers) == 2
