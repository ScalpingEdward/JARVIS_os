import pytest
from pydantic import ValidationError

from app.workflow_designer.models import (
    NodeApproval,
    NodeCompletion,
    NodeType,
    RunState,
    WorkflowActivation,
    WorkflowCreate,
    WorkflowEdge,
    WorkflowNode,
    WorkflowRunCreate,
    WorkflowState,
    WorkflowUpdate,
)
from app.workflow_designer.service import WorkflowDesignerService


def workflow_payload(**overrides) -> WorkflowCreate:
    values = {
        "workspace_id": "personal",
        "owner_id": "owner-1",
        "name": "Faceless content pipeline",
        "nodes": [
            WorkflowNode(key="start", node_type=NodeType.START, name="Start"),
            WorkflowNode(
                key="research",
                node_type=NodeType.AGENT_TASK,
                name="Research topic",
                required_capability="research",
            ),
            WorkflowNode(
                key="approval",
                node_type=NodeType.HUMAN_APPROVAL,
                name="Approve draft",
            ),
            WorkflowNode(key="end", node_type=NodeType.END, name="End"),
        ],
        "edges": [
            WorkflowEdge(source="start", target="research"),
            WorkflowEdge(source="research", target="approval"),
            WorkflowEdge(source="approval", target="end"),
        ],
    }
    values.update(overrides)
    return WorkflowCreate(**values)


def test_valid_workflow_can_activate_and_complete() -> None:
    service = WorkflowDesignerService()
    workflow = service.create(workflow_payload())
    validation = service.validate(workflow.id, "personal")
    assert validation is not None and validation.valid is True
    active = service.activate(
        workflow.id,
        "personal",
        "owner-1",
        WorkflowActivation(),
    )
    assert active is not None and active.state == WorkflowState.ACTIVE

    run = service.start_run(
        workflow.id,
        WorkflowRunCreate(workspace_id="personal", requester_id="owner-1"),
    )
    assert run is not None
    assert run.state == RunState.RUNNING
    assert run.current_node_keys == ["research"]

    run = service.complete_node(
        run.id,
        "research",
        "personal",
        NodeCompletion(success=True, result={"topic": "AI trading discipline"}),
    )
    assert run is not None
    assert run.state == RunState.WAITING_APPROVAL
    assert run.current_node_keys == ["approval"]

    run = service.approve_node(
        run.id,
        "approval",
        "personal",
        NodeApproval(approved=True, approved_by="owner-1"),
    )
    assert run is not None
    assert run.state == RunState.COMPLETED
    assert run.current_node_keys == []


def test_invalid_cycle_cannot_activate() -> None:
    service = WorkflowDesignerService()
    payload = workflow_payload(
        edges=[
            WorkflowEdge(source="start", target="research"),
            WorkflowEdge(source="research", target="approval"),
            WorkflowEdge(source="approval", target="research"),
            WorkflowEdge(source="approval", target="end"),
        ]
    )
    workflow = service.create(payload)
    validation = service.validate(workflow.id, "personal")
    assert validation is not None and validation.valid is False
    assert any("cycle" in item.lower() for item in validation.errors)
    active = service.activate(workflow.id, "personal", "owner-1", WorkflowActivation())
    assert active is not None and active.state == WorkflowState.DRAFT


def test_update_creates_new_version_and_returns_to_draft() -> None:
    service = WorkflowDesignerService()
    workflow = service.create(workflow_payload())
    service.activate(workflow.id, "personal", "owner-1", WorkflowActivation())
    updated = service.update(
        workflow.id,
        "personal",
        "owner-1",
        WorkflowUpdate(description="Updated workflow"),
    )
    assert updated is not None
    assert updated.version == 2
    assert updated.state == WorkflowState.DRAFT


def test_workspace_and_owner_isolation() -> None:
    service = WorkflowDesignerService()
    workflow = service.create(workflow_payload())
    assert service.get(workflow.id, "other") is None
    assert service.update(
        workflow.id,
        "personal",
        "other-owner",
        WorkflowUpdate(name="Hijacked"),
    ) is None


def test_denied_approval_cancels_run() -> None:
    service = WorkflowDesignerService()
    workflow = service.create(workflow_payload())
    service.activate(workflow.id, "personal", "owner-1", WorkflowActivation())
    run = service.start_run(
        workflow.id,
        WorkflowRunCreate(workspace_id="personal", requester_id="owner-1"),
    )
    assert run is not None
    service.complete_node(
        run.id,
        "research",
        "personal",
        NodeCompletion(success=True),
    )
    run = service.approve_node(
        run.id,
        "approval",
        "personal",
        NodeApproval(approved=False, approved_by="owner-1"),
    )
    assert run is not None and run.state == RunState.CANCELLED


def test_failed_node_fails_run() -> None:
    service = WorkflowDesignerService()
    workflow = service.create(workflow_payload())
    service.activate(workflow.id, "personal", "owner-1", WorkflowActivation())
    run = service.start_run(
        workflow.id,
        WorkflowRunCreate(workspace_id="personal", requester_id="owner-1"),
    )
    assert run is not None
    run = service.complete_node(
        run.id,
        "research",
        "personal",
        NodeCompletion(success=False, error="Research agent unavailable"),
    )
    assert run is not None and run.state == RunState.FAILED


def test_automatic_external_actions_and_unapproved_changes_are_rejected() -> None:
    with pytest.raises(ValidationError):
        WorkflowNode(
            key="publish",
            node_type=NodeType.AGENT_TASK,
            name="Publish",
            required_capability="instagram_publish",
            automatic_external_action=True,
        )
    with pytest.raises(ValidationError):
        workflow_payload(human_approved=False)
    with pytest.raises(ValidationError):
        WorkflowRunCreate(
            workspace_id="personal",
            requester_id="owner-1",
            automatic_external_action=True,
        )
