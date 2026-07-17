import pytest
from pydantic import ValidationError

from app.browser_intelligence.models import (
    ActionType,
    BrowserSessionCreate,
    ElementDescriptor,
    ElementKind,
    NavigationStepCreate,
    PageAnalysisRequest,
    PageSnapshotCreate,
    RiskLevel,
    SessionMutation,
    SessionState,
    StepApproval,
)
from app.browser_intelligence.service import BrowserIntelligenceService


def session_payload(workspace: str = "workspace-1", owner: str = "owner-1") -> BrowserSessionCreate:
    return BrowserSessionCreate(
        workspace_id=workspace,
        owner_id=owner,
        session_key="research-session",
        start_url="https://example.com/start",
        allowed_domains=["example.com"],
    )


def test_create_activate_and_pause_session():
    service = BrowserIntelligenceService()
    session = service.create_session(session_payload())
    assert session.state == SessionState.PLANNED
    activated = service.activate_session(
        session.id,
        "workspace-1",
        SessionMutation(requester_id="owner-1", reason="approved"),
    )
    assert activated is not None and activated.state == SessionState.ACTIVE
    paused = service.pause_session(
        session.id,
        "workspace-1",
        SessionMutation(requester_id="owner-1"),
    )
    assert paused is not None and paused.state == SessionState.PAUSED


def test_workspace_and_owner_isolation():
    service = BrowserIntelligenceService()
    session = service.create_session(session_payload())
    assert service.get_session(session.id, "other-workspace") is None
    result = service.activate_session(
        session.id,
        "workspace-1",
        SessionMutation(requester_id="wrong-owner"),
    )
    assert result is None


def test_domain_allowlist_blocks_cross_domain_snapshot_and_step():
    service = BrowserIntelligenceService()
    session = service.create_session(session_payload())
    with pytest.raises(ValueError):
        service.add_snapshot(
            PageSnapshotCreate(
                workspace_id="workspace-1",
                session_id=session.id,
                url="https://evil.example.net",
                dom_hash="abcdefgh1234",
            )
        )
    step = service.plan_step(
        NavigationStepCreate(
            workspace_id="workspace-1",
            session_id=session.id,
            action=ActionType.NAVIGATE,
            target_url="https://evil.example.net",
        )
    )
    assert step.blocked_reason


def test_snapshot_analysis_uses_only_supplied_data():
    service = BrowserIntelligenceService()
    session = service.create_session(session_payload())
    snapshot = service.add_snapshot(
        PageSnapshotCreate(
            workspace_id="workspace-1",
            session_id=session.id,
            url="https://example.com/dashboard",
            title="Dashboard",
            text_content="Account dashboard and reports",
            dom_hash="dashboard-hash-001",
            elements=[
                ElementDescriptor(element_id="report-link", kind=ElementKind.LINK, label="Open reports"),
                ElementDescriptor(element_id="login-form", kind=ElementKind.FORM, label="Login"),
                ElementDescriptor(
                    element_id="password",
                    kind=ElementKind.INPUT,
                    label="Password",
                    sensitive=True,
                ),
                ElementDescriptor(element_id="results", kind=ElementKind.TABLE, label="Reports table"),
            ],
        )
    )
    analysis = service.analyze_page(
        PageAnalysisRequest(
            workspace_id="workspace-1",
            requester_id="owner-1",
            snapshot_id=snapshot.id,
            objective="open reports",
        )
    )
    assert analysis.detected_forms == 1
    assert analysis.detected_tables == 1
    assert analysis.detected_sensitive_elements == 1
    assert "report-link" in analysis.suggested_element_ids
    assert analysis.external_ai_invoked is False


def test_sensitive_actions_require_approval_and_are_never_executed():
    service = BrowserIntelligenceService()
    session = service.create_session(session_payload())
    step = service.plan_step(
        NavigationStepCreate(
            workspace_id="workspace-1",
            session_id=session.id,
            action=ActionType.SUBMIT,
            element_id="payment-form",
            value_preview="secret-value",
            requires_human_approval=False,
            risk_level=RiskLevel.LOW,
        )
    )
    assert step.requires_human_approval is True
    assert step.risk_level == RiskLevel.CRITICAL
    assert step.executed is False
    assert step.value_preview != "secret-value"
    approved = service.approve_step(
        step.id,
        "workspace-1",
        StepApproval(approved=True, approved_by="owner-1"),
    )
    assert approved is not None and approved.human_approved is True
    assert approved.executed is False


def test_duplicate_session_and_snapshot_rejected():
    service = BrowserIntelligenceService()
    session = service.create_session(session_payload())
    with pytest.raises(ValueError):
        service.create_session(session_payload())
    payload = PageSnapshotCreate(
        workspace_id="workspace-1",
        session_id=session.id,
        url="https://example.com/page",
        dom_hash="duplicate-hash-01",
    )
    service.add_snapshot(payload)
    with pytest.raises(ValueError):
        service.add_snapshot(payload)


def test_maximum_step_limit_blocks_session():
    service = BrowserIntelligenceService()
    payload = session_payload()
    payload.maximum_steps = 1
    session = service.create_session(payload)
    service.plan_step(
        NavigationStepCreate(
            workspace_id="workspace-1",
            session_id=session.id,
            action=ActionType.READ,
        )
    )
    with pytest.raises(ValueError):
        service.plan_step(
            NavigationStepCreate(
                workspace_id="workspace-1",
                session_id=session.id,
                action=ActionType.READ,
            )
        )
    assert session.state == SessionState.BLOCKED


def test_real_execution_credentials_and_external_ai_are_rejected():
    with pytest.raises(ValidationError):
        BrowserSessionCreate(
            workspace_id="workspace-1",
            owner_id="owner-1",
            session_key="unsafe",
            start_url="https://example.com",
            allowed_domains=["example.com"],
            execute_browser=True,
        )
    with pytest.raises(ValidationError):
        BrowserSessionCreate(
            workspace_id="workspace-1",
            owner_id="owner-1",
            session_key="cookies",
            start_url="https://example.com",
            allowed_domains=["example.com"],
            persist_cookies=True,
        )
    with pytest.raises(ValidationError):
        NavigationStepCreate(
            workspace_id="workspace-1",
            session_id="00000000-0000-0000-0000-000000000001",
            action=ActionType.CLICK,
            execute_action=True,
        )
    with pytest.raises(ValidationError):
        PageAnalysisRequest(
            workspace_id="workspace-1",
            requester_id="owner-1",
            snapshot_id="00000000-0000-0000-0000-000000000001",
            objective="analyze",
            invoke_external_ai=True,
        )


def test_status_safety_defaults():
    status = BrowserIntelligenceService().status()
    assert status.version == "8.3"
    assert status.dry_run_only is True
    assert status.real_browser_execution is False
    assert status.credential_storage is False
    assert status.cookie_persistence is False
