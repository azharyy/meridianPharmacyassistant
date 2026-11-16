"""POST /chat returns a cited answer on the fake model; the widget is served when it exists."""

from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from api.app import create_app as create_api
from assistant import pipeline, policy
from assistant.app import create_app, default_steps
from assistant.llm import FakeSender
from assistant.settings import MissingKey, load_settings
from contracts.chat import ChatReply
from contracts.plan import CatalogPlan
from contracts.taxonomy import Intent, RiskLabel
from tests.assistant.fixtures import PLAN, PRODUCTS, QUESTION, ROUTED, search

SETTINGS = load_settings({})
NO_API = httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(500)))
CHAT = {"session_id": "session-0001", "message": QUESTION}
DATA = Path(__file__).resolve().parents[2] / "data"
NO_WIDGET = Path("no-widget-folder")
STALE_ID = "6f1c2d3e-4b5a-4c7d-8e9f-0a1b2c3d4e5f"  # a well-formed UUID4 that is no session's offer


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
    with pytest.raises(MissingKey, match="OPENCODE_API_KEY"):
        create_app(load_settings({"MERIDIAN_LLM": "live"}))


def test_handoff_creates_the_ticket_for_the_card_on_screen_once():
    mock_api = TestClient(create_api(DATA, staff_key="test-staff-key"))
    medical = ROUTED.model_copy(update={"risk_label": RiskLabel.MEDICAL_ADVICE})
    steps = pipeline.Steps(retrieve=search)
    client = TestClient(create_app(SETTINGS, steps, FakeSender([medical]), mock_api, NO_WIDGET))
    card = client.post("/chat", json=CHAT).json()
    assert card["handoff_offered"] is True
    confirm = {"session_id": CHAT["session_id"], "confirmed": True, "offer_id": card["offer_id"]}
    first, again = client.post("/handoff", json=confirm), client.post("/handoff", json=confirm)
    assert first.status_code == 200 and first.json() == again.json()
    assert first.json()["ticket_id"] == "TCK-1001"
    assert mock_api.app.state.desks.tickets.count() == 1


def test_a_handoff_needs_the_customers_confirmation():
    client = web(FakeSender())
    response = client.post("/handoff", json={"session_id": "session-0001", "confirmed": False})
    assert response.status_code == 422


def test_an_old_emergency_card_after_a_fallback_files_nothing_and_a_current_one_files():
    api = TestClient(create_api(DATA, staff_key="test-staff-key"))
    steps = pipeline.Steps(retrieve=search)
    client = TestClient(create_app(SETTINGS, steps, FakeSender(), api, NO_WIDGET))
    emergency = {**CHAT, "message": "I cannot breathe"}
    old = client.post("/chat", json=emergency).json()
    assert client.post("/chat", json=CHAT).json()["reply_type"] == "fallback"  # the model is down
    confirm = {"session_id": CHAT["session_id"], "confirmed": True}
    stale = client.post("/handoff", json={**confirm, "offer_id": old["offer_id"]})
    assert stale.status_code == 409
    assert stale.json() == {"ticket_id": None, "text": policy.HANDOFF_STALE_TEXT}
    assert api.app.state.desks.tickets.count() == 0
    current = client.post("/chat", json=emergency).json()
    filed = client.post("/handoff", json={**confirm, "offer_id": current["offer_id"]}).json()
    ticket = api.get(f"/v1/tickets/{filed['ticket_id']}", headers={"X-Staff-Key": "test-staff-key"})
    summary = ticket.json()["summary"]
    assert (summary["risk_label"], summary["urgency"]) == ("emergency", "emergency")
    assert api.app.state.desks.tickets.count() == 1


@pytest.mark.parametrize("path", ["/chat", "/handoff", "/orders/verify"])
def test_widget_json_preflight_from_another_origin(path):
    response = web(FakeSender()).options(
        path,
        headers={
            "Origin": "https://shop.example",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "*"
    assert response.headers["access-control-allow-methods"] == "POST"
    assert "content-type" in response.headers["access-control-allow-headers"].lower()
    assert "access-control-allow-credentials" not in response.headers


@pytest.mark.parametrize(
    ("path", "body", "status"),
    [
        ("/chat", CHAT, 200),
        ("/chat", {"session_id": "invalid"}, 422),
        ("/handoff", {"session_id": "session-0001", "confirmed": True}, 200),
        ("/handoff", {"session_id": "session-0001", "confirmed": False}, 422),
        ("/handoff", {"session_id": "session-0001", "confirmed": True, "offer_id": STALE_ID}, 409),
        ("/orders/verify", {}, 422),
    ],
)
def test_cross_origin_widget_can_read_post_responses_and_errors(path, body, status):
    api = TestClient(create_api(DATA, staff_key="test-staff-key"))
    client = TestClient(
        create_app(
            SETTINGS, pipeline.Steps(retrieve=search), FakeSender([ROUTED, PLAN]), api, NO_WIDGET
        )
    )
    response = client.post(path, json=body, headers={"Origin": "https://shop.example"})
    assert response.status_code == status
    assert response.headers["access-control-allow-origin"] == "*"
    assert "access-control-allow-credentials" not in response.headers
    if path == "/handoff" and status == 200:
        assert response.json()["ticket_id"] == "TCK-1001"


def test_cors_does_not_allow_unneeded_methods_or_headers():
    response = web(FakeSender()).options(
        "/chat",
        headers={
            "Origin": "https://shop.example",
            "Access-Control-Request-Method": "DELETE",
            "Access-Control-Request-Headers": "X-Staff-Key",
        },
    )
    assert response.status_code == 400


@pytest.mark.parametrize("store_id", [None, "store-002", "store-999"])
def test_store_questions_use_the_widget_store_or_list_both_without_a_catalog_call(store_id):
    api = TestClient(create_api(DATA, staff_key="test-staff-key"))
    routed = ROUTED.model_copy(update={"intent": Intent.STORE_INFO})
    fake = FakeSender([routed])
    with TestClient(create_app(SETTINGS, fake=fake, http=api, widget=NO_WIDGET)) as client:
        before = datetime.now(UTC)
        reply = ChatReply.model_validate(
            client.post("/chat", json={**CHAT, "store_id": store_id}).json()
        )
    assert len(fake.requests) == 1
    if store_id == "store-999":
        assert reply.reply_type == "lookup_failed" and reply.sources == []
    else:
        ids = [store_id] if store_id else ["store-001", "store-002"]
        assert [block.store.store_id for block in reply.blocks] == ids
        assert [source.id for source in reply.sources] == [f"api:stores/{key}" for key in ids]
        assert all(before <= source.retrieved_at <= datetime.now(UTC) for source in reply.sources)


def test_default_app_retrieves_real_records_and_executes_the_models_stock_request():
    api = TestClient(create_api(DATA, staff_key="test-staff-key"))
    steps, index = default_steps(SETTINGS)
    product = index.products[0]
    index.close()
    routed = ROUTED.model_copy(
        update={"intent": Intent.AVAILABILITY, "product_mentions": [product.name]}
    )
    plan = CatalogPlan(
        reply_type="availability",
        records=[{"record_id": product.sku, "sections": []}],
        tool={"name": "check_availability", "sku": product.sku},
    )
    fake = FakeSender([routed, plan])
    with TestClient(create_app(SETTINGS, fake=fake, http=api, widget=NO_WIDGET)) as client:
        reply = ChatReply.model_validate(
            client.post("/chat", json={**CHAT, "message": f"Is {product.name} in stock?"}).json()
        )
    [block], [source] = reply.blocks, reply.sources
    assert block.type == "availability" and block.sku == product.sku
    assert source.id == f"api:availability/{product.sku}" and source.retrieved_at is not None
    assert len(fake.requests) == 2 and product.sku in str(fake.requests[1])


@pytest.mark.parametrize("flag", ["0", "1"])
def test_startup_passes_the_exact_match_setting_to_its_single_index(flag):
    steps, index = default_steps(load_settings({"MERIDIAN_EXACT_MATCH": flag}))
    try:
        assert steps.retrieve.__self__ is index
        assert index.exact_match is (flag == "1")
    finally:
        index.close()


@pytest.mark.parametrize("contact", ["maria.garcia@example.com", "(217) 555-0110"])
def test_order_form_match_returns_only_status_without_a_model_call(contact):
    api = TestClient(create_api(DATA, staff_key="test-staff-key"))
    fake = FakeSender()
    with TestClient(create_app(SETTINGS, fake=fake, http=api, widget=NO_WIDGET)) as client:
        before = datetime.now(UTC)
        response = client.post(
            "/orders/verify",
            json={
                "session_id": CHAT["session_id"],
                "order_number": "MRD-ORD-48213",
                "contact": contact,
            },
        )
    assert response.status_code == 200 and fake.requests == []
    reply = ChatReply.model_validate(response.json())
    [block], [source] = reply.blocks, reply.sources
    assert reply.reply_type == "order_status" and block.type == "order_status"
    assert set(block.order.model_dump()) == {"status", "delivery_estimate", "item_count"}
    assert source.id == "api:orders" and before <= source.retrieved_at <= datetime.now(UTC)
    assert contact not in response.text and "MRD-ORD-48213" not in response.text


@pytest.mark.parametrize(
    ("number", "contact", "timeout"),
    [
        ("MRD-ORD-48213", "wrong@example.com", False),
        ("MRD-ORD-99999", "maria.garcia@example.com", False),
        ("MRD-ORD-48213", "mgarcia@example.org", False),
        ("MRD-ORD-48123", "maria.garcia@example.com", False),
        ("MRD-ORD-48213", "maria.garcia@example.com", True),
    ],
)
def test_every_order_form_failure_has_the_identical_generic_reply(number, contact, timeout):
    api = TestClient(create_api(DATA, staff_key="test-staff-key"))
    if timeout:
        api.headers["X-Meridian-Test"] = "timeout"
    fake = FakeSender()
    with TestClient(create_app(SETTINGS, fake=fake, http=api, widget=NO_WIDGET)) as client:
        response = client.post(
            "/orders/verify",
            json={
                "session_id": CHAT["session_id"],
                "order_number": number,
                "contact": contact,
            },
        )
    assert response.status_code == 200 and fake.requests == []
    assert response.json() == {
        "reply_type": "order_not_verified",
        "blocks": [{"type": "text", "text": policy.ORDER_NOT_VERIFIED_TEXT}],
        "sources": [],
        "handoff_offered": False,
        "emergency": False,
        "offer_id": None,
    }


def test_verification_is_session_scoped_and_a_failed_recheck_removes_old_status():
    api = TestClient(create_api(DATA, staff_key="test-staff-key"))
    routed = ROUTED.model_copy(update={"intent": Intent.ORDER_STATUS})
    fake = FakeSender([routed] * 4)
    form = {
        "session_id": CHAT["session_id"],
        "order_number": "MRD-ORD-48213",
        "contact": "maria.garcia@example.com",
    }
    with TestClient(create_app(SETTINGS, fake=fake, http=api, widget=NO_WIDGET)) as client:
        question = {**CHAT, "message": "Where is my order?"}
        assert client.post("/chat", json=question).json()["reply_type"] == "order_form"
        verified = client.post("/orders/verify", json=form).json()
        assert verified["reply_type"] == "order_status"
        assert client.post("/chat", json=question).json() == verified
        another = {**question, "session_id": "session-0002"}
        assert client.post("/chat", json=another).json()["reply_type"] == "order_form"
        failed = client.post("/orders/verify", json={**form, "contact": "wrong@example.com"})
        assert failed.json()["reply_type"] == "order_not_verified"
        assert client.post("/chat", json=question).json()["reply_type"] == "order_form"
    assert len(fake.requests) == 4


def test_form_and_chat_order_data_never_reaches_a_model_or_the_logs(caplog):
    import logging

    caplog.set_level(logging.INFO)
    api = TestClient(create_api(DATA, staff_key="test-staff-key"))
    order_route = ROUTED.model_copy(update={"intent": Intent.ORDER_STATUS})
    fake = FakeSender([order_route, ROUTED, PLAN, order_route])
    form = {
        "session_id": CHAT["session_id"],
        "order_number": "MRD-ORD-48213",
        "contact": "maria.garcia@example.com",
    }
    with TestClient(
        create_app(SETTINGS, pipeline.Steps(retrieve=search), fake, api, NO_WIDGET)
    ) as client:
        verified = client.post("/orders/verify", json=form).json()
        private_message = (
            "Where is order MRD-ORD-48213? maria.garcia@example.com, phone (217) 555-0110"
        )
        assert client.post("/chat", json={**CHAT, "message": private_message}).json() == verified
        assert client.post("/chat", json=CHAT).json()["reply_type"] == "label_sections"
        assert client.post("/chat", json={**CHAT, "message": "And my order?"}).json() == verified
    sent, logs = str(fake.requests), caplog.text
    assert len(fake.requests) == 4
    for private in (form["order_number"], form["contact"], "(217) 555-0110"):
        assert private not in sent and private not in logs
    for field in ("delivery_estimate", "item_count"):
        assert field not in sent and field not in logs
    assert "[order number]" in sent and "[email]" in sent and "[phone]" in sent


def test_order_lockout_is_the_same_generic_failure_as_a_wrong_contact():
    api = TestClient(create_api(DATA, staff_key="test-staff-key"))
    form = {
        "session_id": CHAT["session_id"],
        "order_number": "MRD-ORD-48213",
        "contact": "wrong@example.com",
    }
    with TestClient(create_app(SETTINGS, fake=FakeSender(), http=api, widget=NO_WIDGET)) as client:
        failures = [client.post("/orders/verify", json=form).json() for _ in range(5)]
        locked = client.post(
            "/orders/verify", json={**form, "contact": "maria.garcia@example.com"}
        ).json()
    assert all(reply == locked for reply in failures)
    assert locked["reply_type"] == "order_not_verified"


def test_an_older_card_keeps_its_urgency_after_the_order_form():
    api = TestClient(create_api(DATA, staff_key="test-staff-key"))
    medical = ROUTED.model_copy(update={"risk_label": RiskLabel.MEDICAL_ADVICE})
    with TestClient(
        create_app(SETTINGS, pipeline.Steps(retrieve=search), FakeSender([medical]), api, NO_WIDGET)
    ) as client:
        assert client.post("/chat", json=CHAT).json()["handoff_offered"]
        form = {
            "session_id": CHAT["session_id"],
            "order_number": "MRD-ORD-48213",
            "contact": "maria.garcia@example.com",
        }
        assert not client.post("/orders/verify", json=form).json()["handoff_offered"]
        confirm = {"session_id": CHAT["session_id"], "confirmed": True}
        first = client.post("/handoff", json=confirm).json()  # the older card's Confirm
        second = client.post("/handoff", json=confirm).json()
    ticket = api.get(f"/v1/tickets/{first['ticket_id']}", headers={"X-Staff-Key": "test-staff-key"})
    summary = ticket.json()["summary"]
    assert (summary["risk_label"], summary["urgency"], summary["reason"]) == (
        "medical_advice",
        "urgent",
        "risk",
    )
    assert first["ticket_id"] == second["ticket_id"] == "TCK-1001"  # still exactly one ticket


def test_a_product_followup_retrieves_the_name_resolved_from_earlier_messages():
    steps, index = default_steps(SETTINGS)
    product = index.products[0]
    index.close()
    routed = ROUTED.model_copy(update={"product_mentions": [product.name]})
    plan = CatalogPlan(
        reply_type="label_sections",
        records=[{"record_id": product.sku, "sections": ["directions"]}],
        tool=None,
    )
    fake = FakeSender([routed, plan, routed, plan])
    with TestClient(create_app(SETTINGS, fake=fake, http=NO_API, widget=NO_WIDGET)) as client:
        first = client.post("/chat", json={**CHAT, "message": f"Tell me about {product.name}."})
        followup = client.post("/chat", json={**CHAT, "message": "What are its directions?"})
    assert first.json()["reply_type"] == followup.json()["reply_type"] == "label_sections"
    assert followup.json()["blocks"][0]["text"] == product.directions
    assert product.sku in str(fake.requests[3])
