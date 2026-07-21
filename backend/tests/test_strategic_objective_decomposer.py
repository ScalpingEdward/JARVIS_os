import pytest

from app.modules.strategic_objective_decomposer.models import (
    StrategicObjectiveCreate,
    StrategicObjectiveExecuteRequest,
    StrategicObjectiveState,
)
from app.modules.strategic_objective_decomposer.service import StrategicObjectiveDecomposerService


def payload(**overrides):
    data = dict(
        workspace_id="alpha",
        source_key="objective-1",
        actor_id="owner",
        objective="Launch governed multi-agent trading operations",
        target_date="2026-12-31",
        business_value=92,
        urgency=80,
        confidence=75,
        budget_limit=50000,
        constraints=["no autonomous risk increase", "human approval before production"],
        known_dependencies=["risk-brain", "broker-sandbox"],
        success_metrics=["all production actions remain governed", "roadmap approved before execution"],
        upstream_risk_brain_blocked=False,
    )
    data.update(overrides)
    return StrategicObjectiveCreate(**data)


def test_decomposes_objective_into_milestones_and_deliverables():
    service = StrategicObjectiveDecomposerService()
    record = service.create(payload())
    assert record.state == StrategicObjectiveState.HUMAN_REVIEW_REQUIRED
    assert record.plan is not None
    assert len(record.plan.milestones) == 3
    assert len(record.plan.deliverables) == 3
    assert record.plan.total_effort_points == 16
    assert record.plan.planning_boundary == "executive-planning-only"


def test_approval_and_issue_require_explicit_human_authorization():
    service = StrategicObjectiveDecomposerService()
    record = service.create(payload())
    with pytest.raises(ValueError, match="human approval required"):
        service.execute(record.id, "alpha", StrategicObjectiveExecuteRequest(action="approve", actor_id="agent"))

    approved = service.execute(
        record.id,
        "alpha",
        StrategicObjectiveExecuteRequest(action="approve", actor_id="owner", human_approved=True),
    )
    assert approved.state == StrategicObjectiveState.APPROVED
    assert approved.approval_token

    issued = service.execute(
        record.id,
        "alpha",
        StrategicObjectiveExecuteRequest(action="issue-to-executive-planning", actor_id="owner", human_approved=True),
    )
    assert issued.state == StrategicObjectiveState.ISSUED_TO_EXECUTIVE_PLANNING


def test_missing_success_metrics_fails_closed():
    service = StrategicObjectiveDecomposerService()
    record = service.create(payload(success_metrics=[]))
    assert record.state == StrategicObjectiveState.EVIDENCE_REQUIRED
    assert record.plan is None


def test_missing_constraints_fails_closed():
    service = StrategicObjectiveDecomposerService()
    record = service.create(payload(constraints=[]))
    assert record.state == StrategicObjectiveState.EVIDENCE_REQUIRED


def test_risk_brain_block_is_authoritative():
    service = StrategicObjectiveDecomposerService()
    record = service.create(payload(upstream_risk_brain_blocked=True))
    assert record.state == StrategicObjectiveState.BLOCKED


def test_duplicate_source_key_is_rejected_per_workspace():
    service = StrategicObjectiveDecomposerService()
    service.create(payload())
    with pytest.raises(ValueError, match="duplicate source_key"):
        service.create(payload())


def test_workspace_isolation_and_audit():
    service = StrategicObjectiveDecomposerService()
    record = service.create(payload())
    assert service.get(record.id, "other") is None
    assert service.list_records("other") == []
    assert len(service.audit_records("alpha")) == 1
