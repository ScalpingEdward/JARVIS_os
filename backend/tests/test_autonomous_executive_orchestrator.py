import pytest

from app.modules.autonomous_executive_orchestrator.models import (
    OrchestrationAction,
    OrchestrationCommand,
    OrchestrationCreate,
    OrchestrationState,
    StageInput,
)
from app.modules.autonomous_executive_orchestrator.service import (
    AutonomousExecutiveOrchestratorService,
    OrchestrationError,
)


def payload(workspace: str = "ws-a", source: str = "plan-1") -> OrchestrationCreate:
    return OrchestrationCreate(
        workspace_id=workspace,
        source_key=source,
        execution_plan_id="execution-21-09",
        execution_plan_approved=True,
        v21_09_evidence={"approval": "valid"},
        max_parallel_stages=2,
        stages=[
            StageInput(
                key="design",
                title="Prepare governed dispatch",
                module="engineering-master",
                owner="phoenix",
                rollback_action="discard prepared dispatch",
                expected_output="validated dispatch package",
            ),
            StageInput(
                key="verify",
                title="Verify delivery",
                module="quality-master",
                owner="phoenix",
                dependencies=["design"],
                rollback_action="return package to design",
                expected_output="verified delivery receipt",
            ),
        ],
    )


def test_prepare_approve_dispatch_and_complete_workflow() -> None:
    service = AutonomousExecutiveOrchestratorService()
    record = service.create(payload())
    assert record.state == OrchestrationState.ORCHESTRATION_READY
    assert record.ready_queue == ["design"]

    record = service.execute(
        "ws-a",
        record.id,
        OrchestrationAction(command=OrchestrationCommand.APPROVE, actor="human", approval_token="approval-1"),
    )
    assert record.state == OrchestrationState.APPROVED

    record = service.execute(
        "ws-a",
        record.id,
        OrchestrationAction(command=OrchestrationCommand.DISPATCH, actor="orchestrator", stage_key="design", dispatch_token="dispatch-1"),
    )
    assert record.state == OrchestrationState.MONITORING

    record = service.execute(
        "ws-a",
        record.id,
        OrchestrationAction(command=OrchestrationCommand.COMPLETE_STAGE, actor="worker", stage_key="design", result_receipt="receipt-1"),
    )
    assert "verify" in record.ready_queue

    service.execute(
        "ws-a",
        record.id,
        OrchestrationAction(command=OrchestrationCommand.DISPATCH, actor="orchestrator", stage_key="verify", dispatch_token="dispatch-2"),
    )
    record = service.execute(
        "ws-a",
        record.id,
        OrchestrationAction(command=OrchestrationCommand.COMPLETE_STAGE, actor="worker", stage_key="verify", result_receipt="receipt-2"),
    )
    assert record.state == OrchestrationState.COMPLETED


def test_hard_block_and_missing_evidence() -> None:
    service = AutonomousExecutiveOrchestratorService()
    blocked = payload(source="blocked")
    blocked.risk_brain_hard_block = True
    assert service.create(blocked).state == OrchestrationState.BLOCKED

    missing = payload(source="missing")
    missing.v21_09_evidence = {}
    assert service.create(missing).state == OrchestrationState.EVIDENCE_REQUIRED


def test_duplicate_workspace_isolation_and_replay_protection() -> None:
    service = AutonomousExecutiveOrchestratorService()
    record = service.create(payload())
    with pytest.raises(OrchestrationError, match="duplicate"):
        service.create(payload())
    with pytest.raises(OrchestrationError, match="record not found"):
        service.get("ws-b", record.id)

    service.execute(
        "ws-a",
        record.id,
        OrchestrationAction(command=OrchestrationCommand.APPROVE, actor="human", approval_token="same-token"),
    )
    other = service.create(payload(source="plan-2"))
    with pytest.raises(OrchestrationError, match="replay"):
        service.execute(
            "ws-a",
            other.id,
            OrchestrationAction(command=OrchestrationCommand.APPROVE, actor="human", approval_token="same-token"),
        )


def test_failure_retry_and_cycle_detection() -> None:
    service = AutonomousExecutiveOrchestratorService()
    record = service.create(payload())
    service.execute("ws-a", record.id, OrchestrationAction(command=OrchestrationCommand.APPROVE, actor="human"))
    service.execute("ws-a", record.id, OrchestrationAction(command=OrchestrationCommand.DISPATCH, actor="system", stage_key="design"))
    record = service.execute(
        "ws-a",
        record.id,
        OrchestrationAction(command=OrchestrationCommand.FAIL_STAGE, actor="worker", stage_key="design", reason="timeout"),
    )
    assert record.state == OrchestrationState.HUMAN_REVIEW_REQUIRED
    record = service.execute(
        "ws-a",
        record.id,
        OrchestrationAction(command=OrchestrationCommand.RETRY_STAGE, actor="human", stage_key="design"),
    )
    assert record.state == OrchestrationState.APPROVED

    cyclic = payload(source="cycle")
    cyclic.stages[0].dependencies = ["verify"]
    with pytest.raises(OrchestrationError, match="cyclic"):
        service.create(cyclic)


def test_audit_is_workspace_scoped() -> None:
    service = AutonomousExecutiveOrchestratorService()
    service.create(payload(workspace="ws-a", source="a"))
    service.create(payload(workspace="ws-b", source="b"))
    assert service.audit("ws-a")
    assert all(event.workspace_id == "ws-a" for event in service.audit("ws-a"))
