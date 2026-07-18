import pytest

from app.executive_decision_engine.models import (
    ApprovalRequest,
    ConstraintType,
    DecisionAlternative,
    DecisionConstraint,
    DecisionCriterion,
    DecisionStatus,
    ExecutiveDecisionCreate,
)
from app.executive_decision_engine.service import ExecutiveDecisionService


def payload(workspace_id: str = "ws-a", owner_id: str = "owner") -> ExecutiveDecisionCreate:
    return ExecutiveDecisionCreate(
        workspace_id=workspace_id,
        owner_id=owner_id,
        title="Expansion decision",
        objective="Select the strongest governed expansion option",
        criteria=[
            DecisionCriterion(name="value", weight=50),
            DecisionCriterion(name="readiness", weight=30),
            DecisionCriterion(name="resilience", weight=20),
        ],
        alternatives=[
            DecisionAlternative(
                alternative_key="alpha",
                title="Alpha rollout",
                criterion_scores={"value": 90, "readiness": 85, "resilience": 80},
                attributes={"budget": 80, "compliant": True},
                confidence=90,
                risk_score=20,
                implementation_cost=80,
                expected_value=150,
            ),
            DecisionAlternative(
                alternative_key="beta",
                title="Beta rollout",
                criterion_scores={"value": 75, "readiness": 70, "resilience": 90},
                attributes={"budget": 60, "compliant": True},
                confidence=80,
                risk_score=30,
                implementation_cost=60,
                expected_value=120,
            ),
        ],
        constraints=[
            DecisionConstraint(name="budget-cap", constraint_type=ConstraintType.maximum, field_name="budget", value=100),
            DecisionConstraint(name="compliance", constraint_type=ConstraintType.required, field_name="compliant", value=True),
        ],
    )


def test_evaluation_ranks_alternatives_and_builds_trace() -> None:
    service = ExecutiveDecisionService()
    record = service.create(payload())
    evaluated = service.evaluate(record.id, "ws-a", "analyst")
    assert evaluated.status == DecisionStatus.evaluated
    assert evaluated.evaluation is not None
    assert evaluated.evaluation.recommended_alternative_key == "alpha"
    assert evaluated.evaluation.evaluations[0].rank == 1
    assert evaluated.evaluation.trace
    assert evaluated.evaluation.autonomous_actions_enabled is False


def test_constraints_block_infeasible_decision() -> None:
    service = ExecutiveDecisionService()
    data = payload()
    data.alternatives[0].attributes["budget"] = 150
    data.alternatives[1].attributes["compliant"] = False
    record = service.create(data)
    evaluated = service.evaluate(record.id, "ws-a", "analyst")
    assert evaluated.evaluation is not None
    assert evaluated.evaluation.recommended_alternative_key is None
    assert evaluated.evaluation.blocking_reasons
    with pytest.raises(ValueError):
        service.approve(record.id, "ws-a", ApprovalRequest(actor_id="approver", approved=True))


def test_independent_human_approval_is_required() -> None:
    service = ExecutiveDecisionService()
    record = service.create(payload())
    service.evaluate(record.id, "ws-a", "analyst")
    with pytest.raises(ValueError):
        service.approve(record.id, "ws-a", ApprovalRequest(actor_id="owner", approved=True))
    approved = service.approve(record.id, "ws-a", ApprovalRequest(actor_id="approver", approved=True, comment="Approved after review"))
    assert approved.status == DecisionStatus.approved
    assert approved.approval is not None
    assert approved.approval.actor_id == "approver"


def test_workspace_isolation_duplicates_status_and_audit() -> None:
    service = ExecutiveDecisionService()
    record = service.create(payload())
    assert service.get(record.id, "ws-b") is None
    assert service.list_decisions("ws-b") == []
    with pytest.raises(ValueError):
        service.create(payload())
    service.evaluate(record.id, "ws-a", "analyst")
    status = service.status("ws-a")
    assert status.version == "18.2"
    assert status.decisions == 1
    assert status.evaluated_decisions == 1
    assert status.autonomous_actions_enabled is False
    assert len(service.audit_records("ws-a")) == 2
    assert service.audit_records("ws-b") == []


def test_invalid_weights_and_missing_scores_are_rejected() -> None:
    with pytest.raises(ValueError):
        ExecutiveDecisionCreate(
            workspace_id="ws",
            owner_id="owner",
            title="Invalid weights",
            objective="Invalid",
            criteria=[DecisionCriterion(name="value", weight=60), DecisionCriterion(name="risk", weight=30)],
            alternatives=[
                DecisionAlternative(alternative_key="a", title="A", criterion_scores={"value": 50, "risk": 50}),
                DecisionAlternative(alternative_key="b", title="B", criterion_scores={"value": 50, "risk": 50}),
            ],
        )
