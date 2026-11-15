"""Provide a fresh, temporary localhost mock API for each evaluation run."""

import socket
import subprocess
import sys
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path

import httpx

from assistant.settings import Settings

ROOT = Path(__file__).resolve().parents[1]


def unused_port() -> int:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return listener.getsockname()[1]


def command(port: int) -> list[str]:
    return [
        sys.executable,
        "-m",
        "uvicorn",
        "api.app:app",
        "--host",
        "127.0.0.1",
        "--port",
        str(port),
        "--log-level",
        "critical",
        "--no-access-log",
    ]


def stop(server: subprocess.Popen) -> None:
    if server.poll() is None:
        server.terminate()
    try:
        server.wait(timeout=5)
    except subprocess.TimeoutExpired:
        server.kill()
        server.wait(timeout=5)


def ready(server, http, pause: Callable[[float], None], attempts: int = 100) -> None:
    for _ in range(attempts):
        if server.poll() is not None:
            raise RuntimeError("the evaluation mock API exited before becoming ready")
        try:
            if http.get("/v1/stores").is_success:
                return
        except httpx.HTTPError:
            pass
        pause(0.1)
    raise RuntimeError("the evaluation mock API did not become ready")


@contextmanager
def local_api(
    settings: Settings,
    *,
    start: Callable = subprocess.Popen,
    port: int | None = None,
    pause: Callable[[float], None] = time.sleep,
    client: Callable = httpx.Client,
) -> Iterator[Settings]:
    port = unused_port() if port is None else port
    isolated = replace(settings, api_url=f"http://127.0.0.1:{port}")
    server = start(
        command(port),
        cwd=ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    try:
        with client(base_url=isolated.api_url, timeout=0.25, trust_env=False) as http:
            ready(server, http, pause)
        yield isolated
    finally:
        stop(server)
