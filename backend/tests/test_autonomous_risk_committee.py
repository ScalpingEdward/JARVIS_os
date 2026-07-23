import pytest

from app.schemas.autonomous_risk_committee import (
    CommitteeMemberAssessment,
    RiskCommitteeAction,
    RiskCommitteeCreate,
)
from app.services.autonomous_risk_committee import AutonomousRiskCommitteeService


def payload(workspace: str = "ws-1", source: str = "src-1") -> RiskCommitteeCreate:
    return RiskCommitteeCreate(
        workspace_id=workspace,
        source_key=source,
        portfolio_brain_record_id="brain-1",
        requested_by="analyst",
        assessments=[
            CommitteeMemberAssessment(
                member_id="risk",
                domain="risk-brain",
                stance="support",
                confidence=0.90,
                severity=0.30,
                rationale="Risk remains inside governed limits.",
            ),
            CommitteeMemberAssessment(
                member_id="liquidity",
                domain="liquidity",
                stance="support",
                confidence=0.80,
                severity=0.25,
                rationale="Liquidity conditions are resilient.",
            ),
            CommitteeMemberAssessment(
                member_id="infra",
                domain="infrastructure",
                stance="caution",
                confidence=0.70,
                severity=0.40,
                rationale="Monitor execution-path latency.",
            ),
        ],
        approval_threshold=0.60,
    )


def test_deliberation_and_human_approval() -> None:
    service = AutonomousRiskCommitteeService()
    record = service.create(payload())
    assert record.decision.quorum_met is True
    assert record.decision.veto_triggered is False

    reviewed = service.act("ws-1", record.record_id, RiskCommitteeAction(
        action="submit-review", actor="chair", operation_id="op-1"
    ))
    assert reviewed.state.value == "review-required"

    approved = service.act("ws-1", record.record_id, RiskCommitteeAction(
        action="approve", actor="human-chair", operation_id="op-2"
    ))
    assert approved.approved_by == "human-chair"


def test_veto_blocks_approval() -> None:
    service = AutonomousRiskCommitteeService()
    request = payload()
    request.assessments[0].stance = "oppose"
    request.assessments[0].confidence = 0.95
    record = service.create(request)
    assert record.decision.veto_triggered is True
    with pytest.raises(ValueError):
        service.act("ws-1", record.record_id, RiskCommitteeAction(
            action="approve", actor="chair", operation_id="op-veto"
        ))


def test_replay_duplicate_and_workspace_isolation() -> None:
    service = AutonomousRiskCommitteeService()
    record = service.create(payload())
    with pytest.raises(ValueError):
        service.create(payload())
    with pytest.raises(KeyError):
        service.get("ws-2", record.record_id)

    action = RiskCommitteeAction(action="deliberate", actor="chair", operation_id="same-op")
    service.act("ws-1", record.record_id, action)
    with pytest.raises(ValueError):
        service.act("ws-1", record.record_id, action)


def test_safety_boundary() -> None:
    status = AutonomousRiskCommitteeService.status()
    assert status["advisory_only"] is True
    assert status["portfolio_mutation_enabled"] is False
    assert status["allocation_mutation_enabled"] is False
    assert status["limit_mutation_enabled"] is False
    assert status["execution_enabled"] is False
    assert status["human_approval_required"] is True
    assert status["risk_brain_authoritative"] is True
