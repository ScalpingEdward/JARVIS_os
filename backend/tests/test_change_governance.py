from datetime import datetime, timedelta, timezone

import pytest

from app.change_governance.models import (
    ApprovalCreate, ApprovalDecision, ChangeCreate, ChangeState, Mutation,
    ReleaseCreate, RiskLevel,
)
from app.change_governance.service import ChangeGovernanceService


def _change(**overrides) -> ChangeCreate:
    data = dict(
        workspace_id="alpha",
        owner_id="owner",
        change_key="event-bus-release",
        title="Release event bus update",
        change_type="standard",
        risk_level=RiskLevel.MEDIUM,
        affected_services=["event-bus"],
        implementation_plan="Deploy reviewed package.",
        validation_plan="Run health and regression checks.",
        rollback_plan="Restore previous package.",
        evidence_references=["ci/run-100"],
        required_approvals=1,
    )
    data.update(overrides)
    return ChangeCreate(**data)


def test_change_approval_release_and_lifecycle() -> None:
    service = ChangeGovernanceService()
    change = service.create_change(_change())
    service.set_state(change.id, "alpha", Mutation(requester_id="owner"), ChangeState.REVIEW)
    service.record_approval(ApprovalCreate(
        workspace_id="alpha", requester_id="reviewer", change_id=change.id,
        decision=ApprovalDecision.APPROVE,
    ))
    assert change.state == ChangeState.APPROVED

    start = datetime.now(timezone.utc) + timedelta(hours=1)
    release = service.create_release(ReleaseCreate(
        workspace_id="alpha", requester_id="owner", change_id=change.id,
        release_key="release-1", environment="staging", artifact_reference="artifact:v1",
        scheduled_start=start, scheduled_end=start + timedelta(hours=1),
    ))
    assert release.state == "planned"
    service.set_state(change.id, "alpha", Mutation(requester_id="owner"), ChangeState.SCHEDULED)
    service.set_state(change.id, "alpha", Mutation(requester_id="owner"), ChangeState.IMPLEMENTED)
    service.set_state(change.id, "alpha", Mutation(requester_id="owner"), ChangeState.VERIFIED)
    service.set_state(change.id, "alpha", Mutation(requester_id="owner"), ChangeState.CLOSED)
    assert change.state == ChangeState.CLOSED


def test_high_risk_requires_two_independent_approvals() -> None:
    service = ChangeGovernanceService()
    with pytest.raises(ValueError, match="at least two approvals"):
        _change(risk_level=RiskLevel.HIGH, required_approvals=1)
    change = service.create_change(_change(risk_level=RiskLevel.HIGH, required_approvals=2))
    service.set_state(change.id, "alpha", Mutation(requester_id="owner"), ChangeState.REVIEW)
    service.record_approval(ApprovalCreate(workspace_id="alpha", requester_id="r1", change_id=change.id, decision=ApprovalDecision.APPROVE))
    assert change.state == ChangeState.REVIEW
    service.record_approval(ApprovalCreate(workspace_id="alpha", requester_id="r2", change_id=change.id, decision=ApprovalDecision.APPROVE))
    assert change.state == ChangeState.APPROVED


def test_ownership_isolation_and_release_gates() -> None:
    service = ChangeGovernanceService()
    change = service.create_change(_change(evidence_references=[]))
    assert service.get_change(change.id, "beta") is None
    assert service.set_state(change.id, "alpha", Mutation(requester_id="other"), ChangeState.REVIEW) is None
    service.set_state(change.id, "alpha", Mutation(requester_id="owner"), ChangeState.REVIEW)
    with pytest.raises(ValueError, match="owner cannot approve"):
        service.record_approval(ApprovalCreate(workspace_id="alpha", requester_id="owner", change_id=change.id, decision=ApprovalDecision.APPROVE))
    service.record_approval(ApprovalCreate(workspace_id="alpha", requester_id="reviewer", change_id=change.id, decision=ApprovalDecision.APPROVE))
    start = datetime.now(timezone.utc) + timedelta(hours=1)
    with pytest.raises(ValueError, match="evidence references"):
        service.create_release(ReleaseCreate(
            workspace_id="alpha", requester_id="owner", change_id=change.id,
            release_key="release-1", environment="prod", artifact_reference="artifact:v1",
            scheduled_start=start, scheduled_end=start + timedelta(hours=1),
        ))


def test_safety_guards() -> None:
    with pytest.raises(ValueError, match="automatic change approval"):
        ChangeCreate(**{**_change().model_dump(), "automatic_approval": True})
    with pytest.raises(ValueError, match="never execute deployments"):
        ChangeCreate(**{**_change().model_dump(), "execute_change": True})
    with pytest.raises(ValueError, match="external deployment providers"):
        ChangeCreate(**{**_change().model_dump(), "external_deployment": True})
