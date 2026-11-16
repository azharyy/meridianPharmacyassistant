"""HTTP routes and static files, and nothing else: the pipeline holds the logic.

`create_app` builds the dependencies once, from settings, so `uvicorn assistant.app:create_app
--factory` runs the real assistant and a test passes its own model script, steps and API client.
In live mode without the runtime's key, it stops at startup with a message naming the key.
"""

from contextlib import asynccontextmanager
from functools import partial
from pathlib import Path

import httpx
import yaml
from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool

from assistant import escalation, pipeline
from assistant.api_client import connect
from assistant.llm import FakeSender, make_client
from assistant.retrieval.index import SearchIndex
from assistant.session import SessionStore
from assistant.settings import Settings, load_settings
from assistant.tools import execute
from contracts.chat import ChatReply, ChatRequest, HandoffReply, HandoffRequest, OrderFormRequest

WIDGET = Path(__file__).resolve().parent.parent / "widget"


async def chat_turn(request: ChatRequest, session, steps: pipeline.Steps, llm, api) -> ChatReply:
    """Dispatch blocking turns after the cheap emergency path has had a chance to finish."""
    if steps.emergency(request.message):
        return pipeline.run_turn(request, session, steps, llm, api).reply
    result = await run_in_threadpool(pipeline.run_turn, request, session, steps, llm, api)
    return result.reply


def default_steps(settings: Settings) -> tuple[pipeline.Steps, SearchIndex]:
    """Bind startup search and trusted public-tool identities once."""
    index = SearchIndex(exact_match=settings.exact_match)
    stores = yaml.safe_load((WIDGET.parent / "data" / "stores.yaml").read_text(encoding="utf-8"))
    executor = partial(
        execute,
        skus={product.sku for product in index.products},
        store_ids={store["store_id"] for store in stores},
    )
    return pipeline.Steps(retrieve=index.search, find_product=index.named, execute=executor), index


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
    turn_steps, index = (steps, None) if steps is not None else default_steps(settings)
    sessions = SessionStore()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        try:
            yield
        finally:
            if index is not None:
                index.close()
            if http is None:
                api.close()

    app = FastAPI(title="Meridian assistant", version="0.1.0", lifespan=lifespan)
    # The embeddable widget calls this public API without cookies or browser credentials.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["POST"],
        allow_headers=["Content-Type"],
    )

    @app.post("/chat", response_model=ChatReply)
    async def chat(request: ChatRequest) -> ChatReply:
        return await chat_turn(request, sessions.get(request.session_id), turn_steps, llm, api)

    @app.post("/orders/verify", response_model=ChatReply)
    def verify_order(request: OrderFormRequest) -> ChatReply:
        return pipeline.verify_order(request, sessions.get(request.session_id), turn_steps, api)

    @app.post("/handoff", response_model=HandoffReply, responses={409: {"model": HandoffReply}})
    def handoff(request: HandoffRequest, response: Response) -> HandoffReply:
        session = sessions.get(request.session_id)
        reply = escalation.handoff(request.session_id, session, api, request.offer_id)
        response.status_code = 409 if reply == escalation.STALE else 200  # 409: nothing was filed
        return reply

    if widget.is_dir():
        app.mount("/widget", StaticFiles(directory=widget), name="widget")
    if (widget / "demo.html").is_file():

        @app.get("/demo", include_in_schema=False)
        def demo() -> FileResponse:
            return FileResponse(widget / "demo.html")

    return app
