"""HTTP routes and static files, and nothing else: the pipeline holds the logic.

`create_app` builds the dependencies once, from settings, so `uvicorn assistant.app:create_app
--factory` runs the real assistant and a test passes its own model script, steps and API client.
In live mode without the runtime's key, it stops at startup with a message naming the key.
"""

from pathlib import Path

import httpx
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from assistant import escalation, pipeline
from assistant.api_client import connect
from assistant.llm import FakeSender, make_client
from assistant.session import SessionStore
from assistant.settings import Settings, load_settings
from contracts.chat import ChatReply, ChatRequest, HandoffReply, HandoffRequest

WIDGET = Path(__file__).resolve().parent.parent / "widget"


def create_app(
    settings: Settings | None = None,
    steps: pipeline.Steps | None = None,
    fake: FakeSender | None = None,
    http: httpx.Client | None = None,
    widget: Path = WIDGET,
) -> FastAPI:
    settings = settings or load_settings()
    llm = make_client(settings, settings.runtime, fake)
    api = http or connect(settings)
    turn_steps = steps or pipeline.Steps()
    sessions = SessionStore()
    app = FastAPI(title="Meridian assistant", version="0.1.0")

    @app.post("/chat", response_model=ChatReply)
    def chat(request: ChatRequest) -> ChatReply:
        session = sessions.get(request.session_id)
        return pipeline.run_turn(request, session, turn_steps, llm, api).reply

    @app.post("/handoff", response_model=HandoffReply)
    def handoff(request: HandoffRequest) -> HandoffReply:
        return escalation.handoff(request.session_id, sessions.get(request.session_id), api)

    if widget.is_dir():
        app.mount("/widget", StaticFiles(directory=widget), name="widget")
    if (widget / "demo.html").is_file():

        @app.get("/demo", include_in_schema=False)
        def demo() -> FileResponse:
            return FileResponse(widget / "demo.html")

    return app
