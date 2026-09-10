"""API-level tests for telegram_live_execution -- exercised through the
real app and the real webhook route, matching the pattern
test_telegram_approvals_api.py already uses."""

from __future__ import annotations

from uuid import UUID, uuid4

import httpx
import pytest
from fastapi.testclient import TestClient

from app.executive_mt5_live_order_executor.models import LiveOrderCreate, LiveOrderState
from app.executive_mt5_live_order_executor.service import live_order_executor_service
from app.main import app
from app.notification_hub.telegram_delivery import TelegramDeliveryClient, TelegramDeliveryConfig
from app.telegram_live_execution import service as service_module
from app.telegram_live_execution.models import TelegramLiveExecutionConfig
from app.telegram_live_execution.service import TelegramLiveExecutionService, telegram_live_execution_service
from app.telegram_live_execution.tokens import EXECUTE, make_token

client = TestClient(app)
SECRET = "api-test-secret"
CHAT_ID = "777"
WORKSPACE = "ws-live-exec-api-tests"

_source_counter = [0]


def _source_key() -> str:
    _source_counter[0] += 1
    return f"api-src-{_source_counter[0]}"


def _approval_required_order() -> str:
    record = live_order_executor_service.create(LiveOrderCreate(
        workspace_id=WORKSPACE, source_key=_source_key(), actor_id="tester",
        native_adapter_ready=True,
        account_login=555222, approved_account_logins=[555222],
        symbol="XAUUSD.s", side="buy", volume=0.10,
        quote_bid=2400.00, quote_ask=2400.20, quote_age_seconds=1.0,
        stop_loss=2395.00, take_profit=2410.00,
        account_risk_approved=True, prop_rules_approved=True,
        expected_risk_amount=50.0, max_risk_amount=200.0,
    ))
    assert record.state == LiveOrderState.APPROVAL_REQUIRED
    return str(record.id)


def setup_function() -> None:
    live_order_executor_service.reset()
    telegram_live_execution_service.reset()


@pytest.fixture(autouse=True)
def _configured_service(monkeypatch):
    """Swap the module-level singleton for a fake-Telegram-backed one --
    same "patch the singleton" approach test_telegram_approvals_api.py
    already uses."""

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/getMe"):
            return httpx.Response(200, json={"ok": True, "result": {"id": 1, "username": "auron_bot"}})
        return httpx.Response(200, json={"ok": True, "result": {"message_id": 1}})

    fake = TelegramLiveExecutionService(
        config=TelegramLiveExecutionConfig(callback_secret=SECRET, allowed_chat_id=CHAT_ID),
        client=TelegramDeliveryClient(
            config=TelegramDeliveryConfig(bot_token="123:ABC", chat_id=CHAT_ID),
            client=httpx.Client(transport=httpx.MockTransport(handler)),
        ),
    )
    monkeypatch.setattr(service_module, "telegram_live_execution_service", fake)
    import app.telegram_live_execution.api as api_module
    monkeypatch.setattr(api_module, "telegram_live_execution_service", fake)
    yield fake


def _callback_body(token: str, chat_id: str = CHAT_ID) -> dict:
    return {
        "update_id": 1,
        "callback_query": {
            "id": "cb1", "data": token,
            "from": {"id": 7, "username": "brano"},
            "message": {"chat": {"id": int(chat_id)}, "message_id": 101},
        },
    }


def test_notify_endpoint_returns_message_id():
    record_id = _approval_required_order()
    resp = client.post(f"/v1/telegram-live-execution/notify/{record_id}")
    assert resp.status_code == 200
    assert resp.json() == {"message_id": 1}


def test_notify_endpoint_unknown_id_returns_404():
    resp = client.post(f"/v1/telegram-live-execution/notify/{uuid4()}")
    assert resp.status_code == 404


def test_webhook_executes_via_the_real_route_and_sets_human_approved():
    record_id = _approval_required_order()
    token = make_token(SECRET, UUID(record_id), EXECUTE)
    resp = client.post("/v1/telegram-live-execution/webhook", json=_callback_body(token))
    assert resp.status_code == 200
    assert resp.json() == {"state": "preflight-ready"}
    fresh = live_order_executor_service.get(UUID(record_id), WORKSPACE)
    assert fresh.request.human_approved is True
    assert fresh.state == LiveOrderState.PREFLIGHT_READY


def test_webhook_non_callback_update_returns_200_with_no_state():
    resp = client.post("/v1/telegram-live-execution/webhook", json={"update_id": 1, "message": {"text": "hi"}})
    assert resp.status_code == 200
    assert resp.json() == {"state": None}


def test_webhook_unauthorized_chat_returns_403_and_never_touches_the_order():
    record_id = _approval_required_order()
    token = make_token(SECRET, UUID(record_id), EXECUTE)
    resp = client.post("/v1/telegram-live-execution/webhook", json=_callback_body(token, chat_id="000000"))
    assert resp.status_code == 403
    fresh = live_order_executor_service.get(UUID(record_id), WORKSPACE)
    assert fresh.request.human_approved is False
    assert fresh.state == LiveOrderState.APPROVAL_REQUIRED


def test_webhook_forged_token_returns_403_and_never_touches_the_order():
    record_id = _approval_required_order()
    forged = make_token("wrong-secret", UUID(record_id), EXECUTE)
    resp = client.post("/v1/telegram-live-execution/webhook", json=_callback_body(forged))
    assert resp.status_code == 403
    fresh = live_order_executor_service.get(UUID(record_id), WORKSPACE)
    assert fresh.request.human_approved is False


def test_status_endpoint_is_read_only():
    resp = client.get("/v1/telegram-live-execution/status")
    assert resp.status_code == 200
    body = resp.json()
    assert body["callback_secret_configured"] is True
    assert body["allowed_chat_configured"] is True


def test_audit_endpoint_reflects_a_real_execution():
    record_id = _approval_required_order()
    token = make_token(SECRET, UUID(record_id), EXECUTE)
    client.post("/v1/telegram-live-execution/webhook", json=_callback_body(token))

    resp = client.get("/v1/telegram-live-execution/audit")
    assert resp.status_code == 200
    actions = [r["action"] for r in resp.json()]
    assert "execute" in actions
