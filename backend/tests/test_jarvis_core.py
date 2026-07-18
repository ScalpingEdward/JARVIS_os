import pytest

from app.jarvis_core.models import (
    ApprovalDecision,
    CoreDecisionCreate,
    DecisionApprovalRequest,
    DecisionStatus,
    ModuleSignal,
)
from app.jarvis_core.service import JarvisCoreService


def payload(workspace_id: str = "ws-1") -> CoreDecisionCreate:
    return CoreDecisionCreate(
        workspace_id=workspace_id,
        owner_id="owner-1",
        title="Coordinate strategic execution",
        objective="Deliver the highest-value approved work safely",
        available_capabilities=["planning", "execution"],
        max_parallel_actions=2,
        signals=[
            ModuleSignal(
                module="planning-intelligence",
                signal_type="approved-plan",
                reference_id="plan-1",
                summary="Launch approved plan",
                urgency=0.9,
                confidence=0.9,
                risk=0.2,
                expected_value=0.95,
                required_capabilities=["planning"],
            ),
            ModuleSignal(
                module="strategic-execution",
                signal_type="execution-readiness",
                reference_id="execution-1",
                summary="Prepare controlled execution",
                urgency=0.8,
                confidence=0.8,
                risk=0.3,
                expected_value=0.85,
                dependencies=["plan-1"],
                required_capabilities=["execution"],
            ),
            ModuleSignal(
                module="optimization-governance",
                signal_type="approved-optimization",
                reference_id="optimization-1",
                summary="Schedule approved optimization",
                urgency=0.4,
                confidence=0.7,
                risk=0.5,
                expected_value=0.6,
                required_capabilities=["execution"],
            ),
        ],
    )


def test_core_analysis_ranks_and_limits_parallel_work():
    service = JarvisCoreService()
    decision = service.create(payload())

    analyzed = service.analyze(decision.id, "ws-1", "analyst-1")

    assert analyzed is not None
    assert analyzed.status == DecisionStatus.pending_approval
    assert analyzed.analysis is not None
    assert analyzed.analysis.arbitration[0].reference_id == "plan-1"
    assert len(analyzed.analysis.recommended_sequence) == 2
    assert "optimization-1" in analyzed.analysis.deferred_references
    assert analyzed.analysis.autonomous_execution_enabled is False
    assert analyzed.analysis.requires_human_approval is True


def test_missing_dependency_creates_governed_conflict():
    service = JarvisCoreService()
    data = payload()
    data.signals[1].dependencies = ["missing-plan"]
    decision = service.create(data)

    analyzed = service.analyze(decision.id, "ws-1", "analyst-1")

    assert analyzed is not None and analyzed.analysis is not None
    assert any(conflict.key == "missing-dependency:missing-plan" for conflict in analyzed.analysis.conflicts)
    blocked = next(task for task in analyzed.analysis.unified_task_graph if task.source_reference_id == "execution-1")
    assert blocked.blocked is True


def test_missing_capability_blocks_task():
    service = JarvisCoreService()
    data = payload()
    data.available_capabilities = ["planning"]
    decision = service.create(data)

    analyzed = service.analyze(decision.id, "ws-1", "analyst-1")

    task = next(task for task in analyzed.analysis.unified_task_graph if task.source_reference_id == "execution-1")
    assert task.blocked is True
    assert "execution" in task.block_reasons[0]


def test_owner_cannot_self_approve():
    service = JarvisCoreService()
    decision = service.create(payload())
    service.analyze(decision.id, "ws-1", "analyst-1")

    with pytest.raises(ValueError, match="cannot approve"):
        service.approve(
            decision.id,
            DecisionApprovalRequest(
                workspace_id="ws-1",
                reviewer_id="owner-1",
                decision=ApprovalDecision.approve,
                reason="Self approval must fail",
            ),
        )


def test_independent_reviewer_can_approve_analyzed_decision():
    service = JarvisCoreService()
    decision = service.create(payload())
    service.analyze(decision.id, "ws-1", "analyst-1")

    approved = service.approve(
        decision.id,
        DecisionApprovalRequest(
            workspace_id="ws-1",
            reviewer_id="reviewer-2",
            decision=ApprovalDecision.approve,
            reason="Governance checks completed",
        ),
    )

    assert approved is not None
    assert approved.status == DecisionStatus.approved
    assert approved.approved_by == "reviewer-2"


def test_workspace_isolation_applies_to_reads_status_and_audit():
    service = JarvisCoreService()
    first = service.create(payload("ws-1"))
    service.create(payload("ws-2"))
    service.analyze(first.id, "ws-1", "analyst-1")

    assert service.get(first.id, "ws-2") is None
    assert len(service.list_decisions("ws-1")) == 1
    assert service.status("ws-1").decisions == 1
    assert all(record.workspace_id == "ws-1" for record in service.audit("ws-1"))


def test_duplicate_signal_reference_ids_are_rejected():
    data = payload().model_dump()
    data["signals"][1]["reference_id"] = "plan-1"

    with pytest.raises(ValueError, match="unique"):
        CoreDecisionCreate(**data)
