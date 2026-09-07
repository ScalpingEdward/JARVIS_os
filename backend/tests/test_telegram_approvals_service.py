"""Tests for telegram_approvals.service."""

from __future__ import annotations

import json
from uuid import uuid4

import httpx
import pytest

from app.accounts.models import AccountType, StrategyAssignmentCreate, TradingAccountCreate
from app.accounts.service import AccountRegistryService, account_registry_service
from app.notification_hub.telegram_delivery import TelegramDeliveryClient, TelegramDeliveryConfig
from app.setup_submission.models import SetupDecisionRequest, SetupDecisionStatus, SetupSubmissionRequest
from app.setup_submission.service import SetupSubmissionService, setup_submission_service
from app.strategies.models import FairValueGap, HTFBias, MarketSnapshot, OrderBlock, OrderBlockType
from app.telegram_approvals.models import TelegramApprovalConfig
from app.telegram_approvals.service import TelegramApprovalError, TelegramApprovalService
from app.telegram_approvals.tokens import APPROVE, REJECT, make_token

SECRET = "test-secret"
CHAT_ID = "555"

_login_counter = [80000000]


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


def _register_account(registry: AccountRegistryService) -> None:
    login = _next_login()
    account = registry.register_account(TradingAccountCreate(
        label=f"Demo {login}", account_type=AccountType.demo, broker="TestBroker",
        login=login, server="Test-Server", currency="USD", initial_balance=100000.0,
    ))
    registry.assign_strategy(account.id, StrategyAssignmentCreate(
        strategy_id="scalping_3tp", strategy_name="scalping_3tp", allocation_pct=100.0, enabled=True,
    ))


@pytest.fixture()
def registry(tmp_path) -> AccountRegistryService:
    return AccountRegistryService(db_path=tmp_path / "accounts.db")


@pytest.fixture()
def submissions(registry) -> SetupSubmissionService:
    return SetupSubmissionService(account_registry=registry)


def _submit_one(submissions: SetupSubmissionService, registry: AccountRegistryService):
    _register_account(registry)
    report = submissions.submit(SetupSubmissionRequest(snapshot=_snapshot()))
    assert report.total_submitted >= 1
    return report.submitted_setups[0].approval_request_id


def _client_and_capture():
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json={"ok": True, "result": {"message_id": 42}})

    return TelegramDeliveryClient(
        config=TelegramDeliveryConfig(bot_token="123:ABC", chat_id=CHAT_ID),
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    ), captured


def _service(submissions: SetupSubmissionService | None = None):
    """Build a TelegramApprovalService wired to an injected submissions
    service where relevant -- but note: the service module talks to the
    *shared* setup_submission_service singleton, not an injectable one (it
    calls decide()/get_approval() at module level), matching how
    trade_risk_pipeline already depends on that same singleton. Tests use
    the shared singleton directly and reset() it, same as
    test_trade_risk_pipeline.py already does.
    """
    tg_client, captured = _client_and_capture()
    svc = TelegramApprovalService(
        config=TelegramApprovalConfig(callback_secret=SECRET, allowed_chat_id=CHAT_ID),
        client=tg_client,
    )
    return svc, captured


def setup_function() -> None:
    setup_submission_service.reset()
    account_registry_service.reset()


def _callback_update(token: str, chat_id: str = CHAT_ID, username: str = "brano") -> dict:
    return {
        "update_id": 1,
        "callback_query": {
            "id": "cb1",
            "data": token,
            "from": {"id": 7, "username": username},
            "message": {"chat": {"id": int(chat_id)}, "message_id": 101},
        },
    }


# -- notify() -----------------------------------------------------------------


def test_notify_sends_a_card_with_two_buttons():
    _register_account(account_registry_service)
    report = setup_submission_service.submit(SetupSubmissionRequest(snapshot=_snapshot()))
    approval_id = report.submitted_setups[0].approval_request_id

    svc, captured = _service()
    message_id = svc.notify(approval_id)

    assert message_id == 42
    keyboard = captured["body"]["reply_markup"]["inline_keyboard"][0]
    assert [b["text"] for b in keyboard] == ["\u2705 Approve", "\u274c Reject"]
    assert str(approval_id) in captured["body"]["text"]


def test_notify_fails_closed_without_a_callback_secret():
    _register_account(account_registry_service)
    report = setup_submission_service.submit(SetupSubmissionRequest(snapshot=_snapshot()))
    approval_id = report.submitted_setups[0].approval_request_id

    tg_client, _ = _client_and_capture()
    svc = TelegramApprovalService(
        config=TelegramApprovalConfig(callback_secret=None, allowed_chat_id=CHAT_ID), client=tg_client,
    )
    with pytest.raises(TelegramApprovalError, match="TELEGRAM_CALLBACK_SECRET"):
        svc.notify(approval_id)


def test_notify_unknown_approval_id_fails_closed():
    svc, _ = _service()
    with pytest.raises(TelegramApprovalError, match="unknown"):
        svc.notify(uuid4())


def test_notify_wraps_delivery_failure():
    _register_account(account_registry_service)
    report = setup_submission_service.submit(SetupSubmissionRequest(snapshot=_snapshot()))
    approval_id = report.submitted_setups[0].approval_request_id

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, text="Bad Request")

    tg_client = TelegramDeliveryClient(
        config=TelegramDeliveryConfig(bot_token="123:ABC", chat_id=CHAT_ID),
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    svc = TelegramApprovalService(
        config=TelegramApprovalConfig(callback_secret=SECRET, allowed_chat_id=CHAT_ID), client=tg_client,
    )
    with pytest.raises(TelegramApprovalError, match="could not deliver"):
        svc.notify(approval_id)


# -- handle_update(): the callback path ---------------------------------------


def test_approve_tap_decides_the_setup():
    _register_account(account_registry_service)
    report = setup_submission_service.submit(SetupSubmissionRequest(snapshot=_snapshot()))
    approval_id = report.submitted_setups[0].approval_request_id

    svc, _ = _service()
    token = make_token(SECRET, approval_id, APPROVE)
    decided = svc.handle_update(_callback_update(token))

    assert decided.decision.value == "approved"
    assert decided.decided_by == "brano"
    assert setup_submission_service.get_approval(approval_id).decision.value == "approved"


def test_reject_tap_decides_the_setup():
    _register_account(account_registry_service)
    report = setup_submission_service.submit(SetupSubmissionRequest(snapshot=_snapshot()))
    approval_id = report.submitted_setups[0].approval_request_id

    svc, _ = _service()
    token = make_token(SECRET, approval_id, REJECT)
    decided = svc.handle_update(_callback_update(token))

    assert decided.decision.value == "rejected"


def test_non_callback_update_is_a_no_op():
    svc, _ = _service()
    assert svc.handle_update({"update_id": 1, "message": {"text": "hi"}}) is None


def test_callback_from_an_unauthorized_chat_is_refused():
    _register_account(account_registry_service)
    report = setup_submission_service.submit(SetupSubmissionRequest(snapshot=_snapshot()))
    approval_id = report.submitted_setups[0].approval_request_id

    svc, _ = _service()
    token = make_token(SECRET, approval_id, APPROVE)
    with pytest.raises(TelegramApprovalError, match="not authorized"):
        svc.handle_update(_callback_update(token, chat_id="999999"))
    assert setup_submission_service.get_approval(approval_id).decision.value == "pending"


def test_forged_token_is_refused():
    _register_account(account_registry_service)
    report = setup_submission_service.submit(SetupSubmissionRequest(snapshot=_snapshot()))
    approval_id = report.submitted_setups[0].approval_request_id

    svc, _ = _service()
    forged = make_token("wrong-secret", approval_id, APPROVE)
    with pytest.raises(TelegramApprovalError, match="invalid callback token"):
        svc.handle_update(_callback_update(forged))
    assert setup_submission_service.get_approval(approval_id).decision.value == "pending"


def test_a_stale_token_for_an_already_decided_setup_is_refused():
    """One-shot at the setup_submission layer -- a double tap (or two people
    tapping the same message) must not silently overwrite the first decision."""
    _register_account(account_registry_service)
    report = setup_submission_service.submit(SetupSubmissionRequest(snapshot=_snapshot()))
    approval_id = report.submitted_setups[0].approval_request_id

    svc, _ = _service()
    token = make_token(SECRET, approval_id, APPROVE)
    svc.handle_update(_callback_update(token))
    with pytest.raises(TelegramApprovalError, match="already"):
        svc.handle_update(_callback_update(make_token(SECRET, approval_id, REJECT)))


def test_missing_secret_refuses_even_an_authorized_chat():
    _register_account(account_registry_service)
    report = setup_submission_service.submit(SetupSubmissionRequest(snapshot=_snapshot()))
    approval_id = report.submitted_setups[0].approval_request_id

    tg_client, _ = _client_and_capture()
    svc = TelegramApprovalService(
        config=TelegramApprovalConfig(callback_secret=None, allowed_chat_id=CHAT_ID), client=tg_client,
    )
    token = make_token(SECRET, approval_id, APPROVE)  # signed with *some* secret
    with pytest.raises(TelegramApprovalError, match="TELEGRAM_CALLBACK_SECRET"):
        svc.handle_update(_callback_update(token))


def test_no_allowed_chat_configured_refuses_everything():
    svc, _ = _service()
    svc.config = TelegramApprovalConfig(callback_secret=SECRET, allowed_chat_id=None)
    with pytest.raises(TelegramApprovalError, match="not authorized"):
        svc.handle_update(_callback_update(make_token(SECRET, uuid4(), APPROVE)))


# -- notify_pending() ----------------------------------------------------------


def test_notify_pending_sends_every_undecided_setup():
    _register_account(account_registry_service)
    _register_account(account_registry_service)
    report = setup_submission_service.submit(SetupSubmissionRequest(snapshot=_snapshot()))
    assert len(report.submitted_setups) == 2

    svc, captured_calls = _service_multi()
    result = svc.notify_pending()

    assert len(result.sent) == 2
    assert result.failed == []
    sent_ids = {o.approval_request_id for o in result.sent}
    assert sent_ids == {s.approval_request_id for s in report.submitted_setups}


def test_notify_pending_skips_already_decided_setups():
    _register_account(account_registry_service)
    _register_account(account_registry_service)
    report = setup_submission_service.submit(SetupSubmissionRequest(snapshot=_snapshot()))
    setup_submission_service.decide(
        report.submitted_setups[0].approval_request_id,
        SetupDecisionRequest(decision=SetupDecisionStatus.approved, decided_by="brano"),
    )

    svc, _ = _service_multi()
    result = svc.notify_pending()

    assert len(result.sent) == 1
    assert result.sent[0].approval_request_id == report.submitted_setups[1].approval_request_id


def test_notify_pending_one_failure_does_not_stop_the_rest():
    _register_account(account_registry_service)
    _register_account(account_registry_service)
    report = setup_submission_service.submit(SetupSubmissionRequest(snapshot=_snapshot()))
    first_id = report.submitted_setups[0].approval_request_id

    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(400, text="Bad Request")
        return httpx.Response(200, json={"ok": True, "result": {"message_id": 99}})

    tg_client = TelegramDeliveryClient(
        config=TelegramDeliveryConfig(bot_token="123:ABC", chat_id=CHAT_ID),
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    svc = TelegramApprovalService(
        config=TelegramApprovalConfig(callback_secret=SECRET, allowed_chat_id=CHAT_ID), client=tg_client,
    )
    result = svc.notify_pending()

    assert len(result.failed) == 1 and len(result.sent) == 1
    assert "could not deliver" in result.failed[0].error


def test_notify_pending_with_nothing_pending_is_empty():
    svc, _ = _service_multi()
    result = svc.notify_pending()
    assert result.sent == [] and result.failed == []


# -- submit_and_notify() --------------------------------------------------------


def test_submit_and_notify_submits_and_sends_in_one_call():
    _register_account(account_registry_service)
    svc, _ = _service_multi()

    result = svc.submit_and_notify(SetupSubmissionRequest(snapshot=_snapshot()))

    assert result.report.total_submitted == 1
    assert len(result.notified.sent) == 1
    assert result.notified.sent[0].approval_request_id == result.report.submitted_setups[0].approval_request_id
    # and it is genuinely in the pending queue now, same as plain submit()
    assert setup_submission_service.get_approval(
        result.report.submitted_setups[0].approval_request_id
    ) is not None


def test_submit_and_notify_with_no_setups_notifies_nothing():
    svc, _ = _service_multi()
    result = svc.submit_and_notify(SetupSubmissionRequest(snapshot=_snapshot()))
    assert result.report.total_submitted == 0
    assert result.notified.sent == [] and result.notified.failed == []


def _service_multi():
    """Same as _service() but with a transport that answers every call
    successfully with a distinct message_id -- for tests that expect
    multiple cards to go out in one method call."""
    counter = {"n": 100}

    def handler(request: httpx.Request) -> httpx.Response:
        counter["n"] += 1
        return httpx.Response(200, json={"ok": True, "result": {"message_id": counter["n"]}})

    tg_client = TelegramDeliveryClient(
        config=TelegramDeliveryConfig(bot_token="123:ABC", chat_id=CHAT_ID),
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    svc = TelegramApprovalService(
        config=TelegramApprovalConfig(callback_secret=SECRET, allowed_chat_id=CHAT_ID), client=tg_client,
    )
    return svc, handler
