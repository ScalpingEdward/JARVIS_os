import pytest

from app.runbook_engine.models import (
    ApprovalCreate, Mutation, RunbookCreate, RunbookState, RunCreate, RunState,
    RunbookStep, StepKind, StepResultCreate, StepState,
)
from app.runbook_engine.service import RunbookService


def _runbook(workspace: str = "alpha", owner: str = "owner", **overrides) -> RunbookCreate:
    data = dict(
        workspace_id=workspace,
        owner_id=owner,
        runbook_key=f"restart-{workspace}",
        name="Service recovery",
        scenario="event bus degraded",
        required_approvals=1,
        steps=[
            RunbookStep(step_key="check", title="Check status", instructions="Inspect metrics", kind=StepKind.CHECK),
            RunbookStep(step_key="evidence", title="Capture evidence", instructions="Attach evidence", kind=StepKind.EVIDENCE, required_evidence=True),
        ],
    )
    data.update(overrides)
    return RunbookCreate(**data)


def _publish(service: RunbookService):
    item = service.create_runbook(_runbook())
    service.set_state(item.id, "alpha", Mutation(requester_id="owner"), RunbookState.REVIEW)
    service.approve(ApprovalCreate(workspace_id="alpha", requester_id="reviewer", runbook_id=item.id))
    service.set_state(item.id, "alpha", Mutation(requester_id="owner"), RunbookState.PUBLISHED)
    return item


def test_runbook_review_approval_publish_and_isolation() -> None:
    service = RunbookService()
    item = _publish(service)
    assert item.state == RunbookState.PUBLISHED
    assert service.get_runbook(item.id, "beta") is None
    assert service.metrics("alpha").published_runbooks == 1


def test_dry_run_step_evidence_and_completion() -> None:
    service = RunbookService()
    item = _publish(service)
    run = service.create_run(RunCreate(workspace_id="alpha", requester_id="owner", runbook_id=item.id, operator_id="operator"))
    service.set_run_state(run.id, "alpha", Mutation(requester_id="operator"), RunState.IN_PROGRESS)
    service.record_step(StepResultCreate(workspace_id="alpha", requester_id="operator", run_id=run.id, step_key="check", state=StepState.COMPLETED))
    with pytest.raises(ValueError, match="required step evidence"):
        service.record_step(StepResultCreate(workspace_id="alpha", requester_id="operator", run_id=run.id, step_key="evidence", state=StepState.COMPLETED))
    service.record_step(StepResultCreate(workspace_id="alpha", requester_id="operator", run_id=run.id, step_key="evidence", state=StepState.COMPLETED, evidence_references=["evidence://1"]))
    assert run.state == RunState.COMPLETED


def test_owner_self_approval_duplicate_steps_and_permissions() -> None:
    service = RunbookService()
    item = service.create_runbook(_runbook())
    service.set_state(item.id, "alpha", Mutation(requester_id="owner"), RunbookState.REVIEW)
    with pytest.raises(ValueError, match="self-approve"):
        service.approve(ApprovalCreate(workspace_id="alpha", requester_id="owner", runbook_id=item.id))
    service.approve(ApprovalCreate(workspace_id="alpha", requester_id="reviewer", runbook_id=item.id))
    service.set_state(item.id, "alpha", Mutation(requester_id="owner"), RunbookState.PUBLISHED)
    run = service.create_run(RunCreate(workspace_id="alpha", requester_id="owner", runbook_id=item.id, operator_id="operator"))
    service.set_run_state(run.id, "alpha", Mutation(requester_id="operator"), RunState.IN_PROGRESS)
    with pytest.raises(ValueError, match="assigned operator"):
        service.record_step(StepResultCreate(workspace_id="alpha", requester_id="other", run_id=run.id, step_key="check", state=StepState.COMPLETED))


def test_safety_guards() -> None:
    with pytest.raises(ValueError, match="automatic runbook publication"):
        RunbookCreate(**{**_runbook().model_dump(), "automatic_publish": True})
    with pytest.raises(ValueError, match="never execute operational steps"):
        RunbookCreate(**{**_runbook().model_dump(), "execute_steps": True})
    with pytest.raises(ValueError, match="external runbook runners"):
        RunbookCreate(**{**_runbook().model_dump(), "external_runner": True})
    with pytest.raises(ValueError, match="planning and evidence records only"):
        RunCreate(workspace_id="alpha", requester_id="owner", runbook_id="00000000-0000-0000-0000-000000000000", operator_id="operator", execute_steps=True)
