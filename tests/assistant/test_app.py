"""POST /chat returns a cited answer on the fake model; the widget is served when it exists."""

from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from api.app import create_app as create_api
from assistant import pipeline
from assistant.app import create_app
from assistant.llm import FakeSender
from assistant.settings import MissingKey, load_settings
from contracts.chat import ChatReply
from contracts.taxonomy import RiskLabel
from tests.assistant.fixtures import PLAN, PRODUCTS, QUESTION, ROUTED, search

SETTINGS = load_settings({})
NO_API = httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(500)))
CHAT = {"session_id": "session-0001", "message": QUESTION}
DATA = Path(__file__).resolve().parents[2] / "data"
NO_WIDGET = Path("no-widget-folder")


def web(fake: FakeSender, widget: Path = Path("no-widget-folder")) -> TestClient:
    steps = pipeline.Steps(retrieve=search)
    return TestClient(create_app(SETTINGS, steps, fake, NO_API, widget=widget))


def test_chat_returns_one_cited_answer_on_the_fake_model():
    response = web(FakeSender([ROUTED, PLAN])).post("/chat", json=CHAT)
    assert response.status_code == 200
    reply = ChatReply.model_validate(response.json())
    [block] = reply.blocks
    assert (block.type, block.text) == ("label_section", PRODUCTS[0].directions)
    assert [source.id for source in reply.sources] == ["MRD-ALG-012#directions"]
    assert reply.sources[0].text == PRODUCTS[0].directions
    assert (reply.handoff_offered, reply.emergency) == (False, False)


def test_without_a_model_the_chat_gets_the_fallback():
    reply = web(FakeSender()).post("/chat", json=CHAT).json()
    assert (reply["reply_type"], reply["handoff_offered"]) == ("fallback", True)


def test_a_malformed_request_is_rejected():
    response = web(FakeSender()).post("/chat", json={"session_id": "s1", "message": ""})
    assert response.status_code == 422


def test_the_widget_and_demo_are_served_when_the_folder_exists(tmp_path):
    (tmp_path / "meridian-chat.js").write_text("// widget", encoding="utf-8")
    (tmp_path / "demo.html").write_text("<p>demo</p>", encoding="utf-8")
    client = web(FakeSender(), tmp_path)
    assert client.get("/widget/meridian-chat.js").text == "// widget"
    assert client.get("/demo").text == "<p>demo</p>"


def test_without_the_folder_there_are_no_widget_routes(tmp_path):
    client = web(FakeSender(), tmp_path / "absent")
    assert client.get("/widget/meridian-chat.js").status_code == 404
    assert client.get("/demo").status_code == 404


def test_the_default_app_starts_on_the_fake_model_without_a_key():
    assert TestClient(create_app(SETTINGS)).post("/chat", json=CHAT).status_code == 200


def test_live_mode_without_the_key_stops_at_startup():
    with pytest.raises(MissingKey, match="GROQ_API_KEY"):
        create_app(load_settings({"MERIDIAN_LLM": "live"}))


def test_handoff_creates_the_ticket_for_the_card_on_screen_once():
    mock_api = TestClient(create_api(DATA, staff_key="test-staff-key"))
    medical = ROUTED.model_copy(update={"risk_label": RiskLabel.MEDICAL_ADVICE})
    steps = pipeline.Steps(retrieve=search)
    client = TestClient(create_app(SETTINGS, steps, FakeSender([medical]), mock_api, NO_WIDGET))
    assert client.post("/chat", json=CHAT).json()["handoff_offered"] is True
    confirm = {"session_id": CHAT["session_id"], "confirmed": True}
    first, again = client.post("/handoff", json=confirm), client.post("/handoff", json=confirm)
    assert first.status_code == 200 and first.json() == again.json()
    assert first.json()["ticket_id"] == "TCK-1001"
    assert mock_api.app.state.desks.tickets.count() == 1


def test_a_handoff_needs_the_customers_confirmation():
    client = web(FakeSender())
    response = client.post("/handoff", json={"session_id": "session-0001", "confirmed": False})
    assert response.status_code == 422
