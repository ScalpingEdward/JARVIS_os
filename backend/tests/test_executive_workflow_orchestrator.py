from app.executive_workflow_orchestrator.models import (
    StepKind,
    StepState,
    WorkflowAssessmentCreate,
    WorkflowDefinition,
    WorkflowExecutionObservation,
    WorkflowState,
    WorkflowStepDefinition,
    WorkflowStepObservation,
)
from app.executive_workflow_orchestrator.service import ExecutiveWorkflowOrchestratorService


def valid_payload(workspace_id: str = "ws-1") -> WorkflowAssessmentCreate:
    return WorkflowAssessmentCreate(
        workspace_id=workspace_id,
        source_key="workflow-1",
        actor_id="tester",
        sql_outbox_runtime_assessment_id="sql-1",
        sql_outbox_runtime_state="dispatched",
        definition=WorkflowDefinition(
            workflow_key="telegram-signal-analysis",
            version=1,
            name="Telegram signal analysis",
            steps=[
                WorkflowStepDefinition(
                    step_id="collect",
                    name="Collect message",
                    module="executive-telegram-collector",
                ),
                WorkflowStepDefinition(
                    step_id="vision",
                    name="Analyze chart",
                    module="executive-vision-adapter-consensus",
                    depends_on=["collect"],
                    compensation_module="executive-workflow-compensation",
                    compensation_required=True,
                ),
                WorkflowStepDefinition(
                    step_id="approve",
                    name="Human approval",
                    module="executive-decision-engine",
                    kind=StepKind.approval,
                    depends_on=["vision"],
                    requires_human_approval=True,
                ),
            ],
        ),
        execution_context={"signal_valid": "true"},
        observation=WorkflowExecutionObservation(
            context_persisted=True,
            workflow_checkpoint_persisted=True,
            steps=[
                WorkflowStepObservation(
                    step_id="collect",
                    state=StepState.succeeded,
                    attempts=1,
                    output_persisted=True,
                    checkpoint_persisted=True,
                ),
                WorkflowStepObservation(step_id="vision", state=StepState.pending),
                WorkflowStepObservation(step_id="approve", state=StepState.pending),
            ],
        ),
    )


def test_dispatches_dependency_ready_step() -> None:
    result = ExecutiveWorkflowOrchestratorService().create(valid_payload())
    assert result.state == WorkflowState.running
    assert result.dispatchable is True
    assert result.executable_step_ids == ["vision"]


def test_waits_for_human_approval() -> None:
    payload = valid_payload()
    payload.observation.steps[1].state = StepState.succeeded
    payload.observation.steps[1].checkpoint_persisted = True
    result = ExecutiveWorkflowOrchestratorService().create(payload)
    assert result.state == WorkflowState.waiting
    assert "approve" in result.blocked_step_ids


def test_completes_workflow() -> None:
    payload = valid_payload()
    payload.observation.steps[1].state = StepState.succeeded
    payload.observation.steps[1].checkpoint_persisted = True
    payload.observation.steps[2].state = StepState.succeeded
    payload.observation.steps[2].checkpoint_persisted = True
    payload.observation.steps[2].approval_granted = True
    result = ExecutiveWorkflowOrchestratorService().create(payload)
    assert result.state == WorkflowState.completed


def test_enters_compensation_on_failure() -> None:
    payload = valid_payload()
    payload.observation.steps[1].state = StepState.succeeded
    payload.observation.steps[1].checkpoint_persisted = True
    payload.observation.steps[2].state = StepState.failed
    result = ExecutiveWorkflowOrchestratorService().create(payload)
    assert result.state == WorkflowState.compensating
    assert result.compensation_step_ids == ["vision"]


def test_accepts_completed_rollback() -> None:
    payload = valid_payload()
    payload.observation.compensation_requested = True
    payload.observation.rollback_chain_verified = True
    payload.observation.steps[1].state = StepState.succeeded
    payload.observation.steps[1].checkpoint_persisted = True
    payload.observation.steps[1].compensation_completed = True
    result = ExecutiveWorkflowOrchestratorService().create(payload)
    assert result.state == WorkflowState.rolled_back


def test_blocks_missing_persisted_context() -> None:
    payload = valid_payload()
    payload.observation.context_persisted = False
    assert ExecutiveWorkflowOrchestratorService().create(payload).state == WorkflowState.blocked


def test_risk_brain_blocks() -> None:
    payload = valid_payload()
    payload.risk_brain_clear = False
    assert ExecutiveWorkflowOrchestratorService().create(payload).state == WorkflowState.blocked


def test_duplicate_instance_rejected() -> None:
    service = ExecutiveWorkflowOrchestratorService()
    first = valid_payload()
    service.create(first)

    second = valid_payload()
    second.source_key = "workflow-2"
    second.workflow_instance_id = first.workflow_instance_id

    try:
        service.create(second)
    except ValueError as exc:
        assert "Duplicate workflow instance" in str(exc)
    else:
        raise AssertionError("duplicate workflow instance was accepted")


def test_workspace_isolation() -> None:
    service = ExecutiveWorkflowOrchestratorService()
    record = service.create(valid_payload())
    assert service.get(record.id, "other") is None


def test_rejects_cyclic_dag() -> None:
    try:
        WorkflowDefinition(
            workflow_key="cycle",
            version=1,
            name="Cycle",
            steps=[
                WorkflowStepDefinition(step_id="a", name="A", module="a", depends_on=["b"]),
                WorkflowStepDefinition(step_id="b", name="B", module="b", depends_on=["a"]),
            ],
        )
    except ValueError as exc:
        assert "acyclic" in str(exc)
    else:
        raise AssertionError("cyclic DAG was accepted")
