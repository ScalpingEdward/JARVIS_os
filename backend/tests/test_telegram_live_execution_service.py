"""Tests for telegram_live_execution.service -- the final "place the real
order" gate. Extra scrutiny here versus most other test files: this is
the one module in the codebase whose whole job is turning a phone tap
into a real broker order becoming reachable, so the refusal paths matter
at least as much as the happy path.
"""

from __future__ import annotations

import json
from uuid import UUID, uuid4

import httpx
import pytest

from app.executive_mt5_live_order_executor.models import (
    LiveOrderCreate,
    LiveOrderExecuteRequest,
    LiveOrderState,
)
from app.executive_mt5_live_order_executor.service import live_order_executor_service
from app.notification_hub.telegram_delivery import TelegramDeliveryClient, TelegramDeliveryConfig
from app.telegram_approvals.tokens import APPROVE as SETUP_APPROVE
from app.telegram_approvals.tokens import make_token as setup_make_token
from app.telegram_live_execution.models import TelegramLiveExecutionConfig
from app.telegram_live_execution.service import (
    TelegramLiveExecutionError,
    TelegramLiveExecutionService,
    telegram_live_execution_service,
)
from app.telegram_live_execution.tokens import CANCEL, EXECUTE, make_token

SECRET = "live-exec-test-secret"
CHAT_ID = "999"
WORKSPACE = "ws-live-exec-tests"

_source_counter = [0]


def setup_function() -> None:
    live_order_executor_service.reset()
    telegram_live_execution_service.reset()


def _source_key() -> str:
    _source_counter[0] += 1
    return f"src-{_source_counter[0]}"


def _approval_required_order(**overrides) -> str:
    """Creates a real order via the real service, landing in
    APPROVAL_REQUIRED -- passes every deterministic check except the
    human-approval one, exactly the state this module's cards exist for."""
    payload = dict(
        workspace_id=WORKSPACE, source_key=_source_key(), actor_id="tester",
        native_adapter_ready=True,
        account_login=555111, approved_account_logins=[555111],
        symbol="XAUUSD.s", side="buy", volume=0.10,
        quote_bid=2400.00, quote_ask=2400.20, quote_age_seconds=1.0,
        stop_loss=2395.00, take_profit=2410.00,
        account_risk_approved=True, prop_rules_approved=True,
        expected_risk_amount=50.0, max_risk_amount=200.0,
    )
    payload.update(overrides)
    record = live_order_executor_service.create(LiveOrderCreate(**payload))
    assert record.state == LiveOrderState.APPROVAL_REQUIRED
    return str(record.id)


def _client_and_capture():
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        if request.content:
            captured["body"] = json.loads(request.content)
        return httpx.Response(200, json={"ok": True, "result": {"message_id": 77}})

    return TelegramDeliveryClient(
        config=TelegramDeliveryConfig(bot_token="123:ABC", chat_id=CHAT_ID),
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    ), captured


def _service():
    tg_client, captured = _client_and_capture()
    svc = TelegramLiveExecutionService(
        config=TelegramLiveExecutionConfig(callback_secret=SECRET, allowed_chat_id=CHAT_ID),
        client=tg_client,
    )
    return svc, captured


def _callback_update(token: str, chat_id: str = CHAT_ID, username: str = "brano") -> dict:
    return {
        "update_id": 1,
        "callback_query": {
            "id": "cb1", "data": token,
            "from": {"id": 7, "username": username},
            "message": {"chat": {"id": int(chat_id)}, "message_id": 202},
        },
    }


# -- notify() -----------------------------------------------------------------


def test_notify_sends_a_card_with_execute_and_cancel_buttons():
    record_id = _approval_required_order()
    svc, captured = _service()

    message_id = svc.notify(record_id)

    assert message_id == 77
    buttons = captured["body"]["reply_markup"]["inline_keyboard"][0]
    assert len(buttons) == 2
    assert "JETZT AUSF" in buttons[0]["text"]
    assert "XAUUSD.s" in captured["body"]["text"]


def test_notify_refuses_for_an_unknown_record():
    svc, _ = _service()
    with pytest.raises(TelegramLiveExecutionError, match="unknown"):
        svc.notify(uuid4())


def test_notify_refuses_without_callback_secret_configured():
    record_id = _approval_required_order()
    tg_client, _ = _client_and_capture()
    svc = TelegramLiveExecutionService(
        config=TelegramLiveExecutionConfig(callback_secret=None, allowed_chat_id=CHAT_ID),
        client=tg_client,
    )
    with pytest.raises(TelegramLiveExecutionError, match="CALLBACK_SECRET"):
        svc.notify(record_id)


def test_notify_refuses_for_an_order_not_in_approval_required():
    """The one refusal that matters most: never offer an execute button
    for an order that isn't actually, right now, waiting on this exact
    decision -- e.g. one already paused, cancelled, or executed."""
    record_id = _approval_required_order()
    svc, _ = _service()
    live_order_executor_service.execute(
        UUID(record_id), WORKSPACE,
        LiveOrderExecuteRequest(actor_id="someone_else", action="cancel"),
    )
    with pytest.raises(TelegramLiveExecutionError, match="not approval-required"):
        svc.notify(record_id)


def test_notify_pending_sends_for_every_approval_required_order_in_the_workspace():
    id1 = _approval_required_order()
    id2 = _approval_required_order()
    svc, _ = _service()

    result = svc.notify_pending(WORKSPACE)

    sent_ids = {str(o.record_id) for o in result.sent}
    assert sent_ids == {id1, id2}
    assert result.failed == []


# -- handle_update(): execute --------------------------------------------------


def test_tapping_execute_sets_human_approved_and_advances_the_real_order():
    record_id = _approval_required_order()
    svc, _ = _service()
    token = make_token(SECRET, UUID(record_id), EXECUTE)

    result = svc.handle_update(_callback_update(token))

    assert result is not None
    assert result.request.human_approved is True
    # In this Linux test environment there is no native MetaTrader5
    # adapter, so a fully-approved order lands one step further at
    # PREFLIGHT_READY, awaiting the real remote execution agent -- exactly
    # mirroring what a human calling POST /execute by hand would see.
    assert result.state == LiveOrderState.PREFLIGHT_READY

    fresh = live_order_executor_service.get(UUID(record_id), WORKSPACE)
    assert fresh.state == LiveOrderState.PREFLIGHT_READY
    assert fresh.request.human_approved is True


def test_tapping_execute_is_recorded_in_the_audit_trail_with_the_tapper():
    record_id = _approval_required_order()
    svc, _ = _service()
    token = make_token(SECRET, UUID(record_id), EXECUTE)

    svc.handle_update(_callback_update(token, username="brano"))

    records = svc.audit_records()
    executed = [r for r in records if r.action == "execute" and r.success]
    assert len(executed) == 1
    assert executed[0].actor == "brano"
    assert str(executed[0].record_id) == record_id


def test_tapping_execute_from_an_unauthorized_chat_is_rejected_and_changes_nothing():
    record_id = _approval_required_order()
    svc, _ = _service()
    token = make_token(SECRET, UUID(record_id), EXECUTE)

    with pytest.raises(TelegramLiveExecutionError, match="not authorized"):
        svc.handle_update(_callback_update(token, chat_id="666"))

    fresh = live_order_executor_service.get(UUID(record_id), WORKSPACE)
    assert fresh.state == LiveOrderState.APPROVAL_REQUIRED
    assert fresh.request.human_approved is False


def test_tapping_execute_with_a_forged_token_is_rejected_and_changes_nothing():
    record_id = _approval_required_order()
    svc, _ = _service()
    forged = make_token("wrong-secret-entirely", UUID(record_id), EXECUTE)

    with pytest.raises(TelegramLiveExecutionError, match="invalid callback token"):
        svc.handle_update(_callback_update(forged))

    fresh = live_order_executor_service.get(UUID(record_id), WORKSPACE)
    assert fresh.state == LiveOrderState.APPROVAL_REQUIRED
    assert fresh.request.human_approved is False


def test_a_setup_approval_token_cannot_be_replayed_here():
    """Cross-module defense in depth: even if someone obtained a valid
    telegram_approvals token (a different secret, a different action
    alphabet), it must not verify against this module's own secret."""
    record_id = _approval_required_order()
    svc, _ = _service()
    # Even minted with the correct secret value coincidentally reused,
    # the action character "a" is outside this module's own {x, c}
    # alphabet, so verify_token here must still refuse it.
    foreign_token = setup_make_token(SECRET, UUID(record_id), SETUP_APPROVE)

    with pytest.raises(TelegramLiveExecutionError, match="invalid callback token"):
        svc.handle_update(_callback_update(foreign_token))


def test_tapping_execute_twice_the_second_tap_is_refused_as_stale():
    """The card may have been sent once, but nothing stops a double-tap
    or a delayed retry -- the second attempt must find the order already
    past APPROVAL_REQUIRED and refuse, not execute or approve twice."""
    record_id = _approval_required_order()
    svc, _ = _service()
    token = make_token(SECRET, UUID(record_id), EXECUTE)

    first = svc.handle_update(_callback_update(token))
    assert first.state == LiveOrderState.PREFLIGHT_READY

    with pytest.raises(TelegramLiveExecutionError, match="no longer approval-required"):
        svc.handle_update(_callback_update(token))


def test_tapping_execute_while_execution_is_paused_never_reaches_pending_execution():
    """Pausing is the single most consequential kill switch in the live
    order executor -- a tap here must still respect it, not bypass it."""
    record_id = _approval_required_order()
    svc, _ = _service()
    live_order_executor_service.pause()
    try:
        token = make_token(SECRET, UUID(record_id), EXECUTE)
        result = svc.handle_update(_callback_update(token))
        assert "paused" in result.detail.lower()
        pending = live_order_executor_service.pending_execution(WORKSPACE)
        assert all(str(r.id) != record_id for r in pending)
    finally:
        live_order_executor_service.resume()


# -- handle_update(): cancel ----------------------------------------------------


def test_tapping_cancel_cancels_the_order_without_ever_setting_human_approved():
    record_id = _approval_required_order()
    svc, _ = _service()
    token = make_token(SECRET, UUID(record_id), CANCEL)

    result = svc.handle_update(_callback_update(token))

    assert result.state == LiveOrderState.CANCELLED
    assert result.request.human_approved is False


# -- non-callback updates are no-ops -------------------------------------------


def test_a_plain_message_update_is_a_no_op():
    svc, _ = _service()
    assert svc.handle_update({"update_id": 5, "message": {"text": "hi"}}) is None


# -- status() -------------------------------------------------------------------


def test_status_reports_configuration_without_any_side_effect():
    record_id = _approval_required_order()
    svc, _ = _service()

    status = svc.status()

    assert status.callback_secret_configured is True
    assert status.allowed_chat_configured is True
    fresh = live_order_executor_service.get(UUID(record_id), WORKSPACE)
    assert fresh.state == LiveOrderState.APPROVAL_REQUIRED
