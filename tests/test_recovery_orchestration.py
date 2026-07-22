import pytest
from pydantic import ValidationError

from backend.app.modules.recovery_orchestration.models import (
    ExecutionMode,
    OrchestrationActionRequest,
    OrchestrationCreate,
    OrchestrationState,
    OrchestrationTask,
    RiskDecision,
)
from backend.app.modules.recovery_orchestration.service import (
    RecoveryOrchestrationError,
    RecoveryOrchestrationService,
)


def payload(**overrides):
    data = dict(
        workspace_id="workspace-a",
        source_key="recovery-35",
        recovery_plan_id="plan-34",
        execution_mode=ExecutionMode.SEQUENTIAL,
        max_parallel_tasks=1,
        tasks=[
            OrchestrationTask(task_id="isolate", recovery_step_id="step-1", command_type="isolate", target="worker-a", required_evidence_refs=["plan:e1"]),
            OrchestrationTask(task_id="restart", recovery_step_id="step-2", command_type="restart", target="worker-a", depends_on=["isolate"], required_evidence_refs=["plan:e2"]),
        ],
        planning_evidence_refs=["plan:verified"],
        runtime_evidence_refs=["runtime:healthy"],
        risk_decision=RiskDecision.ALLOW,
    )
    data.update(overrides)
    return OrchestrationCreate(**data)


def action(name, **kwargs):
    return OrchestrationActionRequest(action=name, actor="operator", **kwargs)


def advance_to_running(service, record):
    service.act(record.record_id, record.workspace_id, action("validate"))
    service.act(record.record_id, record.workspace_id, action("request-review"))
    service.act(record.record_id, record.workspace_id, action("approve", approval_token="approval-1"))
    service.act(record.record_id, record.workspace_id, action("schedule", receipt_id="schedule-1"))
    return service.act(record.record_id, record.workspace_id, action("start", receipt_id="start-1"))


def test_full_orchestration_lifecycle():
    service = RecoveryOrchestrationService()
    record = service.create(payload())
    assert advance_to_running(service, record).state == OrchestrationState.RUNNING
    first = service.act(record.record_id, record.workspace_id, action("complete-task", task_id="isolate", attempt=1, receipt_id="task-1", evidence_refs=["exec:isolate"]))
    assert first.execution["isolate"].completed
    completed = service.act(record.record_id, record.workspace_id, action("complete-task", task_id="restart", attempt=1, receipt_id="task-2", evidence_refs=["exec:restart"]))
    assert completed.state == OrchestrationState.COMPLETED
    verified = service.act(record.record_id, record.workspace_id, action("verify", receipt_id="verify-1", evidence_refs=["verify:healthy"]))
    assert verified.state == OrchestrationState.VERIFIED
    assert len(service.audit("workspace-a")) == 9


def test_dependency_and_replay_protection():
    service = RecoveryOrchestrationService()
    record = service.create(payload())
    advance_to_running(service, record)
    with pytest.raises(RecoveryOrchestrationError, match="dependencies"):
        service.act(record.record_id, record.workspace_id, action("complete-task", task_id="restart", attempt=1, receipt_id="early", evidence_refs=["e1"]))
    service.act(record.record_id, record.workspace_id, action("complete-task", task_id="isolate", attempt=1, receipt_id="shared", evidence_refs=["e2"]))
    with pytest.raises(RecoveryOrchestrationError, match="replay"):
        service.act(record.record_id, record.workspace_id, action("complete-task", task_id="restart", attempt=1, receipt_id="shared", evidence_refs=["e3"]))


def test_risk_brain_block_is_authoritative():
    service = RecoveryOrchestrationService()
    record = service.create(payload(source_key="blocked", risk_decision=RiskDecision.BLOCK, risk_reason="unsafe"))
    result = service.act(record.record_id, record.workspace_id, action("validate"))
    assert result.state == OrchestrationState.BLOCKED
    with pytest.raises(RecoveryOrchestrationError):
        service.act(record.record_id, record.workspace_id, action("request-review"))


def test_graph_validation_and_workspace_isolation():
    with pytest.raises(ValidationError, match="acyclic"):
        payload(source_key="cycle", tasks=[
            OrchestrationTask(task_id="a", recovery_step_id="s1", command_type="restart", target="a", depends_on=["b"], required_evidence_refs=["e"]),
            OrchestrationTask(task_id="b", recovery_step_id="s2", command_type="restart", target="b", depends_on=["a"], required_evidence_refs=["e"]),
        ])
    service = RecoveryOrchestrationService()
    record = service.create(payload())
    with pytest.raises(RecoveryOrchestrationError, match="not found"):
        service.get(record.record_id, "workspace-b")


def test_duplicate_source_and_sequential_concurrency_validation():
    service = RecoveryOrchestrationService()
    service.create(payload())
    with pytest.raises(RecoveryOrchestrationError, match="duplicate"):
        service.create(payload())
    with pytest.raises(ValidationError, match="max_parallel_tasks"):
        payload(source_key="bad-parallel", max_parallel_tasks=2)
