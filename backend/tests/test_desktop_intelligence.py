import pytest
from pydantic import ValidationError

from app.desktop_intelligence.models import (
    ActionType,
    ApprovalRequest,
    DesktopActionCreate,
    DesktopElement,
    DesktopSessionCreate,
    DesktopSnapshotCreate,
    ElementKind,
    RiskLevel,
)
from app.desktop_intelligence.service import DesktopIntelligenceService


def session_payload(workspace: str = "workspace-1") -> DesktopSessionCreate:
    return DesktopSessionCreate(
        workspace_id=workspace,
        owner_id="owner-1",
        session_key="office-session",
        allowed_applications=["Excel", "Chrome"],
        maximum_steps=3,
    )


def test_session_snapshot_and_action_planning():
    service = DesktopIntelligenceService()
    session = service.create_session(session_payload())
    snapshot = service.add_snapshot(
        DesktopSnapshotCreate(
            workspace_id="workspace-1",
            session_id=session.id,
            active_application="Excel",
            active_window_title="Budget.xlsx",
            snapshot_hash="snapshot-123456",
            elements=[DesktopElement(element_id="save", kind=ElementKind.BUTTON, label="Save", app_name="Excel")],
        )
    )
    assert snapshot.active_application == "Excel"
    action = service.plan_action(
        DesktopActionCreate(
            workspace_id="workspace-1",
            session_id=session.id,
            action=ActionType.SAVE,
            target_application="Excel",
            target_element_id="save",
        )
    )
    assert action.risk_level == RiskLevel.CRITICAL
    assert action.executed is False
    assert action.requires_human_approval is True


def test_sensitive_type_preview_is_redacted():
    service = DesktopIntelligenceService()
    session = service.create_session(session_payload())
    action = service.plan_action(
        DesktopActionCreate(
            workspace_id="workspace-1",
            session_id=session.id,
            action=ActionType.TYPE_TEXT,
            target_application="Chrome",
            value_preview="secret-password",
        )
    )
    assert action.value_preview == "[REDACTED INPUT]"
    assert action.risk_level == RiskLevel.MEDIUM


def test_workspace_and_owner_isolation():
    service = DesktopIntelligenceService()
    session = service.create_session(session_payload())
    assert service.get_session(session.id, "other") is None
    action = service.plan_action(
        DesktopActionCreate(
            workspace_id="workspace-1",
            session_id=session.id,
            action=ActionType.OBSERVE,
            target_application="Excel",
        )
    )
    assert service.approve_action(action.id, "workspace-1", ApprovalRequest(requester_id="wrong", approved=True)) is None
    approved = service.approve_action(action.id, "workspace-1", ApprovalRequest(requester_id="owner-1", approved=True))
    assert approved is not None and approved.approved is True


def test_application_allowlist_and_duplicate_snapshot():
    service = DesktopIntelligenceService()
    session = service.create_session(session_payload())
    with pytest.raises(ValueError):
        service.add_snapshot(
            DesktopSnapshotCreate(
                workspace_id="workspace-1",
                session_id=session.id,
                active_application="PowerShell",
                snapshot_hash="snapshot-123456",
            )
        )
    payload = DesktopSnapshotCreate(
        workspace_id="workspace-1",
        session_id=session.id,
        active_application="Excel",
        snapshot_hash="snapshot-123456",
    )
    service.add_snapshot(payload)
    with pytest.raises(ValueError):
        service.add_snapshot(payload)


def test_safety_rejects_real_execution_and_capture():
    data = session_payload().model_dump()
    with pytest.raises(ValidationError):
        DesktopSessionCreate.model_validate({**data, "execute_desktop": True})
    with pytest.raises(ValidationError):
        DesktopSessionCreate.model_validate({**data, "capture_credentials": True})
    service = DesktopIntelligenceService()
    session = service.create_session(session_payload())
    with pytest.raises(ValidationError):
        DesktopActionCreate(
            workspace_id="workspace-1",
            session_id=session.id,
            action=ActionType.CLICK,
            execute_action=True,
        )
    with pytest.raises(ValidationError):
        DesktopSnapshotCreate(
            workspace_id="workspace-1",
            session_id=session.id,
            active_application="Excel",
            snapshot_hash="snapshot-123456",
            live_capture_performed=True,
        )


def test_status_reports_safety_defaults():
    status = DesktopIntelligenceService().status()
    assert status.version == "8.6"
    assert status.planning_only is True
    assert status.real_desktop_execution is False
    assert status.credential_capture is False
    assert status.clipboard_persistence is False
