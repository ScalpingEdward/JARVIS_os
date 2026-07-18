import pytest

from app.playbook_engine.models import (
    ActorAction,
    DryRunCreate,
    PlaybookCreate,
    PlaybookState,
    PlaybookStep,
    StepState,
    StepType,
)
from app.playbook_engine.service import PlaybookEngineService


def payload(workspace: str = "ws", approvals: int = 1) -> PlaybookCreate:
    return PlaybookCreate(
        workspace_id=workspace,
        owner_id="owner",
        key="incident-response",
        name="Incident Response",
        required_approvals=approvals,
        steps=[
            PlaybookStep(key="check", name="Validate incident", step_type=StepType.CHECK),
            PlaybookStep(key="approve", name="Human gate", step_type=StepType.HUMAN_APPROVAL),
            PlaybookStep(key="rollback", name="Rollback plan", step_type=StepType.ROLLBACK_PLAN),
        ],
    )


def publish(service: PlaybookEngineService, workspace: str = "ws"):
    item = service.create(payload(workspace))
    service.submit_review(item.id, workspace, ActorAction(actor_id="owner"))
    service.approve(item.id, workspace, ActorAction(actor_id="reviewer"))
    return service.publish(item.id, workspace, ActorAction(actor_id="publisher"))


def test_governed_lifecycle_and_independent_approval() -> None:
    service = PlaybookEngineService()
    item = service.create(payload())

    reviewed = service.submit_review(item.id, "ws", ActorAction(actor_id="owner"))
    assert reviewed.state == PlaybookState.REVIEW

    with pytest.raises(ValueError):
        service.approve(item.id, "ws", ActorAction(actor_id="owner"))

    approved = service.approve(item.id, "ws", ActorAction(actor_id="reviewer"))
    assert approved.state == PlaybookState.APPROVED

    with pytest.raises(ValueError):
        service.publish(item.id, "ws", ActorAction(actor_id="owner"))

    published = service.publish(item.id, "ws", ActorAction(actor_id="publisher"))
    assert published.state == PlaybookState.PUBLISHED


def test_multiple_approvals_are_enforced() -> None:
    service = PlaybookEngineService()
    item = service.create(payload(approvals=2))
    service.submit_review(item.id, "ws", ActorAction(actor_id="owner"))

    first = service.approve(item.id, "ws", ActorAction(actor_id="reviewer-a"))
    assert first.state == PlaybookState.REVIEW
    second = service.approve(item.id, "ws", ActorAction(actor_id="reviewer-b"))
    assert second.state == PlaybookState.APPROVED


def test_dry_run_never_executes_and_stops_at_human_gate() -> None:
    service = PlaybookEngineService()
    item = publish(service)

    run = service.dry_run(item.id, DryRunCreate(workspace_id="ws", requester_id="operator"))

    assert run.state.value == "waiting_approval"
    assert [step.state for step in run.steps] == [
        StepState.SIMULATED,
        StepState.WAITING_APPROVAL,
        StepState.SIMULATED,
    ]
    assert all("no action executed" in step.message.lower() for step in run.steps)


def test_workspace_isolation_and_metrics() -> None:
    service = PlaybookEngineService()
    publish(service, "a")
    service.create(payload("b"))

    assert len(service.list_all("a")) == 1
    assert len(service.list_all("b")) == 1
    assert service.metrics("a").published_playbooks == 1
    assert service.metrics("b").published_playbooks == 0
    assert all(item["workspace_id"] == "a" for item in service.list_audit("a"))


def test_duplicate_keys_and_external_execution_are_blocked() -> None:
    service = PlaybookEngineService()
    service.create(payload())
    with pytest.raises(ValueError):
        service.create(payload())

    with pytest.raises(ValueError):
        PlaybookStep(
            key="unsafe",
            name="Unsafe",
            step_type=StepType.CHECK,
            external_execution=True,
        )

    with pytest.raises(ValueError):
        DryRunCreate(
            workspace_id="ws",
            requester_id="operator",
            external_execution=True,
        )
