"""API-level tests for telegram_approvals -- exercised through the real app
and the real webhook route, matching the pattern test_setup_submission.py
already uses for its own API-level tests."""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from app.accounts.models import AccountType, StrategyAssignmentCreate, TradingAccountCreate
from app.accounts.service import account_registry_service
from app.main import app
from app.setup_submission.models import SetupSubmissionRequest
from app.setup_submission.service import setup_submission_service
from app.strategies.models import FairValueGap, HTFBias, MarketSnapshot, OrderBlock, OrderBlockType
from app.telegram_approvals import service as service_module
from app.telegram_approvals.service import TelegramApprovalConfig, TelegramApprovalService
from app.telegram_approvals.tokens import APPROVE, make_token

client = TestClient(app)
SECRET = "test-secret"
CHAT_ID = "555"

_login_counter = [81000000]


def _next_login() -> str:
    _login_counter[0] += 1
    return str(_login_counter[0])


def _snapshot() -> MarketSnapshot:
    return MarketSnapshot(
        symbol="EURUSD", current_price=1.10000, bid=1.09995, ask=1.10005, spread=0.00010,
        htf_bias=HTFBias.bullish, session="london",
        order_blocks=[OrderBlock(type=OrderBlockType.bullish, high=1.10010, low=1.09990,
                                 open=1.09990, close=1.10000)],
        fvgs=[FairValueGap(side="bullish", top=1.10020, bottom=1.09980)],
    )


def _submit_one() -> str:
    login = _next_login()
    account = account_registry_service.register_account(TradingAccountCreate(
        label=f"Demo {login}", account_type=AccountType.demo, broker="TestBroker",
        login=login, server="Test-Server", currency="USD", initial_balance=100000.0,
    ))
    account_registry_service.assign_strategy(account.id, StrategyAssignmentCreate(
        strategy_id="scalping_3tp", strategy_name="scalping_3tp", allocation_pct=100.0, enabled=True,
    ))
    body = {"snapshot": _snapshot().model_dump(mode="json"), "account_ids": [str(account.id)]}
    resp = client.post("/v1/setup-submission/submit", json=body)
    return resp.json()["submitted_setups"][0]["approval_request_id"]


def setup_function() -> None:
    setup_submission_service.reset()
    account_registry_service.reset()


@pytest.fixture(autouse=True)
def _configured_service(monkeypatch):
    """Swap the module-level singleton for a fake-Telegram-backed one, for
    the duration of each test -- same "patch the singleton" approach the
    rest of this test suite uses for module-level services."""
    import httpx

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/getMe"):
            return httpx.Response(200, json={"ok": True, "result": {"id": 1, "username": "auron_bot"}})
        return httpx.Response(200, json={"ok": True, "result": {"message_id": 1}})

    from app.notification_hub.telegram_delivery import TelegramDeliveryClient, TelegramDeliveryConfig

    fake = TelegramApprovalService(
        config=TelegramApprovalConfig(callback_secret=SECRET, allowed_chat_id=CHAT_ID),
        client=TelegramDeliveryClient(
            config=TelegramDeliveryConfig(bot_token="123:ABC", chat_id=CHAT_ID),
            client=httpx.Client(transport=httpx.MockTransport(handler)),
        ),
    )
    monkeypatch.setattr(service_module, "telegram_approval_service", fake)
    # api.py imported the name directly, so patch it there too.
    import app.telegram_approvals.api as api_module
    monkeypatch.setattr(api_module, "telegram_approval_service", fake)
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
    approval_id = _submit_one()
    resp = client.post(f"/v1/telegram-approvals/notify/{approval_id}")
    assert resp.status_code == 200
    assert resp.json() == {"message_id": 1}


def test_notify_endpoint_unknown_id_returns_404():
    resp = client.post(f"/v1/telegram-approvals/notify/{uuid4()}")
    assert resp.status_code == 404


def test_webhook_approves_via_the_real_route():
    approval_id = _submit_one()
    token = make_token(SECRET, approval_id, APPROVE)
    resp = client.post("/v1/telegram-approvals/webhook", json=_callback_body(token))
    assert resp.status_code == 200
    assert resp.json() == {"decision": "approved"}
    assert setup_submission_service.get_approval(UUID(approval_id)).decision.value == "approved"


def test_webhook_non_callback_update_returns_200_with_no_decision():
    resp = client.post("/v1/telegram-approvals/webhook", json={"update_id": 1, "message": {"text": "hi"}})
    assert resp.status_code == 200
    assert resp.json() == {"decision": None}


def test_webhook_unauthorized_chat_returns_403():
    approval_id = _submit_one()
    token = make_token(SECRET, approval_id, APPROVE)
    resp = client.post("/v1/telegram-approvals/webhook", json=_callback_body(token, chat_id="999999"))
    assert resp.status_code == 403
    assert setup_submission_service.get_approval(UUID(approval_id)).decision.value == "pending"


def test_webhook_forged_token_returns_403():
    approval_id = _submit_one()
    forged = make_token("wrong-secret", approval_id, APPROVE)
    resp = client.post("/v1/telegram-approvals/webhook", json=_callback_body(forged))
    assert resp.status_code == 403
    assert setup_submission_service.get_approval(UUID(approval_id)).decision.value == "pending"


def test_notify_pending_endpoint_sends_every_undecided_setup():
    _submit_one()
    _submit_one()
    resp = client.post("/v1/telegram-approvals/notify-pending")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["sent"]) == 2
    assert body["failed"] == []


def test_notify_pending_endpoint_with_nothing_pending():
    resp = client.post("/v1/telegram-approvals/notify-pending")
    assert resp.status_code == 200
    assert resp.json() == {"sent": [], "failed": []}


def test_submit_and_notify_endpoint_does_both_in_one_call():
    login = _next_login()
    account = account_registry_service.register_account(TradingAccountCreate(
        label=f"Demo {login}", account_type=AccountType.demo, broker="TestBroker",
        login=login, server="Test-Server", currency="USD", initial_balance=100000.0,
    ))
    account_registry_service.assign_strategy(account.id, StrategyAssignmentCreate(
        strategy_id="scalping_3tp", strategy_name="scalping_3tp", allocation_pct=100.0, enabled=True,
    ))

    body = {"snapshot": _snapshot().model_dump(mode="json")}
    resp = client.post("/v1/telegram-approvals/submit-and-notify", json=body)
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["report"]["total_submitted"] == 1
    assert len(payload["notified"]["sent"]) == 1


def test_submit_and_notify_endpoint_with_no_matching_setups():
    body = {"snapshot": _snapshot().model_dump(mode="json")}
    resp = client.post("/v1/telegram-approvals/submit-and-notify", json=body)
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["report"]["total_submitted"] == 0
    assert payload["notified"]["sent"] == []


def test_status_endpoint_reports_configured_bot():
    resp = client.get("/v1/telegram-approvals/status")
    assert resp.status_code == 200
    body = resp.json()
    assert body["callback_secret_configured"] is True
    assert body["allowed_chat_configured"] is True
    assert body["bot_reachable"] is True
    assert body["bot_username"] == "auron_bot"
