import pytest

from app.approvals.models import ApprovalRequestCreate, ApprovalStatus
from app.approvals.service import approval_service
from app.mobile.models import TelegramUpdate
from app.mobile.service import MobileControlError, mobile_control_service
from app.orchestrator.service import orchestrator_service
from app.roadmap.service import roadmap_service


def setup_function() -> None:
    mobile_control_service.reset()
    mobile_control_service.set_authorized_users({12345})
    approval_service.reset()
    orchestrator_service.reset()
    roadmap_service.reset()


def update(text: str, user_id: int = 12345) -> TelegramUpdate:
    return TelegramUpdate(telegram_user_id=user_id, chat_id=99, text=text)


def test_unauthorized_user_is_rejected() -> None:
    with pytest.raises(MobileControlError, match="not authorized"):
        mobile_control_service.handle(update("/status", user_id=999))


def test_pause_resume_and_status_commands() -> None:
    paused = mobile_control_service.handle(update("/pause"))
    assert paused.ok is True
    assert mobile_control_service.execution_allowed() is False
    status = mobile_control_service.handle(update("/status"))
    assert "Paused: True" in status.text
    resumed = mobile_control_service.handle(update("/resume"))
    assert resumed.sensitive_data_redacted is True
    assert mobile_control_service.execution_allowed() is True


def test_approval_can_be_decided_without_returning_secret_token() -> None:
    approval = approval_service.request(
        ApprovalRequestCreate(action="release.deploy", requested_by="planner", reason="Release candidate ready")
    )
    reply = mobile_control_service.handle(update(f"/approve {approval.id}"))
    assert "intentionally not sent" in reply.text
    assert approval_service.get(approval.id).status == ApprovalStatus.approved
    assert "token_urlsafe" not in reply.text


def test_unknown_command_and_invalid_approval_id_are_safe_errors() -> None:
    with pytest.raises(MobileControlError, match="Unknown command"):
        mobile_control_service.handle(update("/shell rm -rf"))
    with pytest.raises(MobileControlError, match="valid UUID"):
        mobile_control_service.handle(update("/approve nope"))


def test_api_contract_functions_are_registered() -> None:
    from app.mobile.api import mobile_status, telegram_update

    status = mobile_status()
    assert status.authorized_users == 1
    reply = telegram_update(update("/help"))
    assert "/approve ID" in reply.text


# -- account intake, reached via free text that matches no known command ----


def _fake_anthropic_client(payload: dict):
    import httpx
    import json as jsonlib

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"content": [{"type": "text", "text": jsonlib.dumps(payload)}]})

    return httpx.Client(transport=httpx.MockTransport(handler))


def _configure_account_intake(monkeypatch, payload: dict):
    from app.account_intake.service import AccountIntakeConfig, account_intake_service

    monkeypatch.setattr(account_intake_service, "config", AccountIntakeConfig(api_key="test-key"))
    monkeypatch.setattr(account_intake_service, "_client", _fake_anthropic_client(payload))
    account_intake_service._proposals.clear()


def test_unrecognized_text_without_an_api_key_falls_back_to_unknown_command() -> None:
    """The original, pre-existing behavior must survive untouched when
    account-intake extraction genuinely isn't available."""
    with pytest.raises(MobileControlError, match="Unknown command"):
        mobile_control_service.handle(update("gibberish that matches nothing"))


def test_a_message_with_credential_language_is_refused_not_extracted() -> None:
    reply = mobile_control_service.handle(update("here's the login and password: hunter2xyz"))
    assert reply.ok is False
    assert "MT5 terminal" in reply.text


def test_a_clean_account_instruction_produces_a_proposal_reply(monkeypatch) -> None:
    _configure_account_intake(monkeypatch, {
        "label": "PUPrime Demo", "broker": "PUPrime", "login": "20481337",
        "server": "PUPrime-Demo", "account_type": "demo", "strategy_id": "vwap_pullback",
    })
    reply = mobile_control_service.handle(update(
        "new demo account, broker PUPrime, login 20481337, server PUPrime-Demo, vwap"
    ))
    assert reply.ok is True
    assert reply.command is None
    assert "PUPrime" in reply.text
    assert "confirmed" in reply.text.lower()


def test_confirming_a_pending_proposal_registers_a_real_account(monkeypatch) -> None:
    from app.accounts.service import account_registry_service
    account_registry_service.reset()
    _configure_account_intake(monkeypatch, {
        "label": "PUPrime Demo", "broker": "PUPrime", "login": "20481337",
        "server": "PUPrime-Demo", "account_type": "demo",
    })
    mobile_control_service.handle(update("new demo account, broker PUPrime, login 20481337, server PUPrime-Demo"))

    reply = mobile_control_service.handle(update("confirmed"))
    assert reply.ok is True
    assert "registered" in reply.text.lower()
    assert "PUPrime" in reply.text


def test_confirming_with_no_pending_proposal_is_treated_as_an_unknown_command() -> None:
    with pytest.raises(MobileControlError, match="Unknown command"):
        mobile_control_service.handle(update("confirmed"))


def test_a_second_proposal_replaces_the_first_pending_one(monkeypatch) -> None:
    from app.accounts.service import account_registry_service
    account_registry_service.reset()
    _configure_account_intake(monkeypatch, {
        "label": "First", "broker": "PUPrime", "login": "111", "server": "S1", "account_type": "demo",
    })
    mobile_control_service.handle(update("account one, broker PUPrime, login 111, server S1"))

    _configure_account_intake(monkeypatch, {
        "label": "Second", "broker": "ICMarkets", "login": "222", "server": "S2", "account_type": "demo",
    })
    mobile_control_service.handle(update("account two, broker ICMarkets, login 222, server S2"))

    reply = mobile_control_service.handle(update("confirmed"))
    assert "ICMarkets" in reply.text
    assert "PUPrime" not in reply.text


def test_a_message_with_no_recognizable_account_fields_falls_back_to_unknown_command(monkeypatch) -> None:
    _configure_account_intake(monkeypatch, {
        "label": "New Account", "broker": "", "login": "", "server": "", "account_type": "demo",
    })
    with pytest.raises(MobileControlError, match="Unknown command"):
        mobile_control_service.handle(update("just chatting, nothing about an account here"))
