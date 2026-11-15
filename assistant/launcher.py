"""Start the mock API on port 8001 and the assistant on port 8000: what `make run` calls.

Two plain subprocesses and no shell job control, so it runs the same from Git Bash, PowerShell,
cmd, macOS and Linux. Ctrl+C, or either server stopping, stops both. In live mode without the
runtime's key it stops before starting anything, with a message naming the key.
"""

import subprocess
import sys
import time
from collections.abc import Callable, Sequence

from assistant.settings import Settings, load_settings

Start = Callable[[Sequence[str]], subprocess.Popen]


def commands(python: str = sys.executable) -> list[list[str]]:
    """The API on port 8001 and the assistant on port 8000, each run by uvicorn."""
    return [
        [python, "-m", "uvicorn", "api.app:app", "--port", "8001"],
        [python, "-m", "uvicorn", "assistant.app:create_app", "--factory", "--port", "8000"],
    ]


def pause() -> None:
    time.sleep(0.5)


def main(
    settings: Settings | None = None,
    start: Start = subprocess.Popen,
    wait: Callable[[], None] = pause,
) -> None:
    settings = settings or load_settings()
    if settings.llm == "live":
        settings.api_key(settings.runtime)  # stops here, naming the key, when it's missing
    servers = [start(command) for command in commands()]
    print("Assistant: http://localhost:8000 (demo at /demo), API: http://localhost:8001")
    print("Ctrl+C stops both servers.", flush=True)
    try:
        while all(server.poll() is None for server in servers):
            wait()
    except KeyboardInterrupt:
        pass
    finally:
        for server in servers:
            if server.poll() is None:
                server.terminate()
        for server in servers:
            server.wait()


if __name__ == "__main__":
    main()
