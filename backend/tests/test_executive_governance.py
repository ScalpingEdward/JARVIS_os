from datetime import datetime, timezone

import pytest

from app.executive_governance.models import (
    ControlSeverity,
    ControlUpdate,
    EscalationRule,
    GovernanceControl,
    GovernanceFrameworkCreate,
    GovernanceRole,
    GovernanceStatus,
    ReviewCycle,
)
from app.executive_governance.service import ExecutiveGovernanceService


def payload(workspace_id: str = "ws-a") -> GovernanceFrameworkCreate:
    return GovernanceFrameworkCreate(
        workspace_id=workspace_id,
        owner_id="owner",
        title="Executive accountability framework",
        scope="Govern strategy delivery and executive performance",
        roles=[
            GovernanceRole(actor_id="ceo", role="accountable", accountable_for=["strategy"], decision_rights=["approve-strategy"]),
            GovernanceRole(actor_id="cfo", role="responsible", accountable_for=["budget"], decision_rights=["approve-budget"]),
        ],
        controls=[
            GovernanceControl(control_key="strategy-review", title="Strategy review completed", owner_id="ceo", severity=ControlSeverity.high, passed=True, evidence_refs=["review-1"]),
            GovernanceControl(control_key="budget-control", title="Budget control passed", owner_id="cfo", severity=ControlSeverity.critical, passed=False),
        ],
        review_cycles=[ReviewCycle(review_key="quarterly", title="Quarterly review", reviewer_ids=["board"], frequency_days=90, last_reviewed_at=datetime.now(timezone.utc))],
        escalation_rules=[EscalationRule(trigger="critical control failure", severity=ControlSeverity.critical, escalation_owner_id="board", response_sla_hours=24)],
    )


def test_assessment_detects_violation_and_escalation() -> None:
    service = ExecutiveGovernanceService()
    record = service.create(payload())
    assessed = service.assess(record.id, "ws-a", "auditor")
    assert assessed.status == GovernanceStatus.non_compliant
    assert assessed.assessment is not None
    assert assessed.assessment.violations
    assert assessed.assessment.escalation_queue[0].escalation_owner_id == "board"
    assert assessed.assessment.autonomous_actions_enabled is False


def test_control_remediation_can_restore_compliance() -> None:
    service = ExecutiveGovernanceService()
    record = service.create(payload())
    updated = service.update_control(record.id, "ws-a", ControlUpdate(actor_id="cfo", control_key="budget-control", passed=True, evidence_refs=["budget-audit"] ))
    assessed = service.assess(updated.id, "ws-a", "auditor")
    assert assessed.status == GovernanceStatus.compliant
    assert assessed.assessment is not None
    assert assessed.assessment.governance_compliance_score == 100


def test_workspace_isolation_duplicates_status_and_audit() -> None:
    service = ExecutiveGovernanceService()
    record = service.create(payload())
    assert service.get(record.id, "ws-b") is None
    assert service.list_frameworks("ws-b") == []
    with pytest.raises(ValueError):
        service.create(payload())
    service.assess(record.id, "ws-a", "auditor")
    status = service.status("ws-a")
    assert status.version == "18.5"
    assert status.frameworks == 1
    assert status.open_violations == 1
    assert status.autonomous_actions_enabled is False
    assert len(service.audit_records("ws-a")) == 2
    assert service.audit_records("ws-b") == []


def test_duplicate_roles_and_controls_are_rejected() -> None:
    data = payload()
    data.roles.append(data.roles[0])
    with pytest.raises(ValueError):
        GovernanceFrameworkCreate(**data.model_dump())
