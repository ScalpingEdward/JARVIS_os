import pytest
from pydantic import ValidationError

from app.integration_hub.models import (
    ApprovalRequest,
    CircuitState,
    CommandCreate,
    CommandState,
    EventState,
    HealthUpdate,
    IntegrationEventCreate,
    ModuleHealth,
    ModuleRegistrationCreate,
    ReplayRequest,
    SubscriptionCreate,
)
from app.integration_hub.service import IntegrationHubService


def module_payload(key: str, owner: str = "owner-1", workspace: str = "workspace-1") -> ModuleRegistrationCreate:
    return ModuleRegistrationCreate(
        workspace_id=workspace,
        owner_id=owner,
        module_key=key,
        name=key.replace("-", " ").title(),
        version="8.8",
        capabilities=["events", "commands"],
        published_events=["TaskCompleted", "TaskFailed"],
        accepted_commands=["CreateTask", "UpdateMemory"],
    )


def test_register_publish_subscribe_and_replay():
    service = IntegrationHubService()
    publisher = service.create_module(module_payload("task-engine"))
    service.create_module(module_payload("knowledge-engine"))
    subscription = service.create_subscription(
        SubscriptionCreate(
            workspace_id="workspace-1",
            owner_id="owner-1",
            subscriber_module="knowledge-engine",
            event_types=["TaskCompleted"],
            command_name="UpdateMemory",
        )
    )
    event = service.publish_event(
        IntegrationEventCreate(
            workspace_id="workspace-1",
            publisher_module="task-engine",
            event_type="TaskCompleted",
            subject="task-1",
            payload={"progress": 100},
            correlation_id="workflow-1",
        )
    )
    replayed = service.replay_events(ReplayRequest(workspace_id="workspace-1", requester_id="owner-1", event_ids=[event.id]))
    assert publisher.module_key == "task-engine"
    assert subscription.subscriber_module == "knowledge-engine"
    assert event.state == EventState.ACCEPTED
    assert replayed[0].state == EventState.REPLAYED
    assert replayed[0].replay_of == event.id
    assert replayed[0].sequence > event.sequence


def test_command_planning_approval_and_no_execution():
    service = IntegrationHubService()
    service.create_module(module_payload("workflow-designer"))
    service.create_module(module_payload("task-engine"))
    command = service.create_command(
        CommandCreate(
            workspace_id="workspace-1",
            requester_id="owner-1",
            source_module="workflow-designer",
            target_module="task-engine",
            command_name="CreateTask",
            arguments={"title": "Analyze report"},
        )
    )
    assert command.state == CommandState.PLANNED
    approved = service.approve_command(command.id, "workspace-1", ApprovalRequest(requester_id="owner-1", approved=True))
    assert approved is not None
    assert approved.state == CommandState.APPROVED
    assert approved.executed is False


def test_unknown_command_is_blocked():
    service = IntegrationHubService()
    service.create_module(module_payload("workflow-designer"))
    service.create_module(module_payload("task-engine"))
    command = service.create_command(
        CommandCreate(
            workspace_id="workspace-1",
            requester_id="owner-1",
            source_module="workflow-designer",
            target_module="task-engine",
            command_name="DeleteEverything",
        )
    )
    assert command.state == CommandState.BLOCKED
    assert command.blocked_reason


def test_circuit_breaker_blocks_unavailable_module():
    service = IntegrationHubService()
    payload = module_payload("task-engine").model_dump()
    payload["failure_threshold"] = 1
    module = service.create_module(ModuleRegistrationCreate.model_validate(payload))
    updated = service.update_health(module.id, "workspace-1", HealthUpdate(requester_id="owner-1", health=ModuleHealth.UNAVAILABLE, reason="timeout"))
    assert updated is not None
    assert updated.circuit_state == CircuitState.OPEN
    with pytest.raises(ValueError):
        service.publish_event(
            IntegrationEventCreate(
                workspace_id="workspace-1",
                publisher_module="task-engine",
                event_type="TaskCompleted",
            )
        )


def test_rate_limiter_marks_excess_events():
    service = IntegrationHubService()
    service.create_module(
        ModuleRegistrationCreate(
            workspace_id="workspace-1",
            owner_id="owner-1",
            module_key="task-engine",
            name="Task Engine",
            version="8.8",
            published_events=["TaskCompleted"],
            accepted_commands=["CreateTask"],
            rate_limit_per_minute=1,
        )
    )
    first = service.publish_event(IntegrationEventCreate(workspace_id="workspace-1", publisher_module="task-engine", event_type="TaskCompleted"))
    second = service.publish_event(IntegrationEventCreate(workspace_id="workspace-1", publisher_module="task-engine", event_type="TaskCompleted"))
    assert first.state == EventState.ACCEPTED
    assert second.state == EventState.RATE_LIMITED


def test_workspace_and_owner_isolation():
    service = IntegrationHubService()
    module = service.create_module(module_payload("task-engine"))
    assert service.get_module(module.id, "other-workspace") is None
    assert service.update_health(module.id, "workspace-1", HealthUpdate(requester_id="wrong-owner", health=ModuleHealth.DEGRADED)) is None


def test_safety_rejects_external_dispatch_and_execution():
    payload = module_payload("task-engine").model_dump()
    with pytest.raises(ValidationError):
        ModuleRegistrationCreate.model_validate({**payload, "automatic_external_connection": True})
    with pytest.raises(ValidationError):
        IntegrationEventCreate(
            workspace_id="workspace-1",
            publisher_module="task-engine",
            event_type="TaskCompleted",
            dispatch_external=True,
        )
    with pytest.raises(ValidationError):
        CommandCreate(
            workspace_id="workspace-1",
            requester_id="owner-1",
            source_module="task-engine",
            target_module="knowledge-engine",
            command_name="UpdateMemory",
            execute_command=True,
        )
    with pytest.raises(ValidationError):
        SubscriptionCreate(
            workspace_id="workspace-1",
            owner_id="owner-1",
            subscriber_module="knowledge-engine",
            event_types=["TaskCompleted"],
            automatic_external_action=True,
        )


def test_status_reports_safe_defaults():
    status = IntegrationHubService().status()
    assert status.version == "8.8"
    assert status.external_dispatch_enabled is False
    assert status.real_command_execution_enabled is False
