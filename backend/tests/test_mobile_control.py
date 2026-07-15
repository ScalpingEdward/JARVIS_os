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
