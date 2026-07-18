import pytest

from app.optimization_governance.models import (
    ApprovalDecision,
    ApprovalRequest,
    CandidateStatus,
    MetricImpact,
    OptimizationCandidateCreate,
    OptimizationVariant,
    RiskLevel,
)
from app.optimization_governance.service import optimization_governance_service


@pytest.fixture(autouse=True)
def reset_service():
    optimization_governance_service.reset()


def payload(workspace="alpha", owner="owner-1", target="playbook-1"):
    return OptimizationCandidateCreate(
        workspace_id=workspace,
        owner_id=owner,
        title="Improve incident response",
        target_type="playbook",
        target_id=target,
        conflict_keys=["incident-routing"],
        variants=[
            OptimizationVariant(
                key="control",
                title="Current flow",
                description="Keep existing governed flow",
                risk_level=RiskLevel.low,
                metric_impacts=[MetricImpact(metric="resolution_rate", baseline=70, expected=72)],
            ),
            OptimizationVariant(
                key="adaptive",
                title="Adaptive routing",
                description="Route by learned capability and workload",
                implementation_cost=500,
                estimated_hours=12,
                risk_level=RiskLevel.medium,
                metric_impacts=[MetricImpact(metric="resolution_rate", baseline=70, expected=84, weight=2)],
                rollout_steps=["Deploy to shadow cohort", "Review KPI delta", "Request controlled rollout"],
                rollback_steps=["Disable adaptive routing", "Restore prior routing table"],
            ),
        ],
    )


def test_analysis_ranks_variants_and_disables_automatic_application():
    candidate = optimization_governance_service.create(payload())
    analyzed = optimization_governance_service.analyze(candidate.id, "alpha", "analyst-1")
    assert analyzed.status == CandidateStatus.pending_approval
    assert analyzed.analysis.recommended_variant_key == "adaptive"
    assert analyzed.analysis.automatic_application_enabled is False
    assert analyzed.analysis.requires_human_approval is True


def test_owner_cannot_self_approve():
    candidate = optimization_governance_service.create(payload())
    optimization_governance_service.analyze(candidate.id, "alpha", "analyst-1")
    with pytest.raises(ValueError, match="cannot approve"):
        optimization_governance_service.approve(
            candidate.id,
            ApprovalRequest(
                workspace_id="alpha",
                reviewer_id="owner-1",
                decision=ApprovalDecision.approve,
                reason="Self approval is prohibited",
            ),
        )


def test_independent_reviewer_can_approve_selected_variant():
    candidate = optimization_governance_service.create(payload())
    optimization_governance_service.analyze(candidate.id, "alpha", "analyst-1")
    approved = optimization_governance_service.approve(
        candidate.id,
        ApprovalRequest(
            workspace_id="alpha",
            reviewer_id="reviewer-2",
            decision=ApprovalDecision.approve,
            reason="Metrics and rollback plan accepted",
            variant_key="adaptive",
        ),
    )
    assert approved.status == CandidateStatus.approved
    assert approved.approved_variant_key == "adaptive"


def test_workspace_isolation():
    candidate = optimization_governance_service.create(payload(workspace="alpha"))
    assert optimization_governance_service.get(candidate.id, "beta") is None
    assert optimization_governance_service.list_candidates("beta") == []


def test_conflict_detection_between_active_candidates():
    first = optimization_governance_service.create(payload(target="playbook-1"))
    optimization_governance_service.analyze(first.id, "alpha", "analyst")
    second = optimization_governance_service.create(payload(target="workflow-2"))
    analyzed = optimization_governance_service.analyze(second.id, "alpha", "analyst")
    assert len(analyzed.analysis.conflicts) == 1
    assert analyzed.analysis.conflicts[0].conflict_key == "incident-routing"


def test_ab_comparison_requires_analysis():
    candidate = optimization_governance_service.create(payload())
    with pytest.raises(ValueError, match="analyzed first"):
        optimization_governance_service.compare(candidate.id, "alpha", "control", "adaptive")
    optimization_governance_service.analyze(candidate.id, "alpha", "analyst")
    result = optimization_governance_service.compare(candidate.id, "alpha", "control", "adaptive")
    assert result.recommendation == "adaptive"
    assert result.expected_delta > 0
