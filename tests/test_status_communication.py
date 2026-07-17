import pytest

from app.status_communication.models import (
    ApprovalCreate, AudienceType, CommunicationCreate, ComponentCreate,
    ComponentStatus, ComponentStatusUpdate, MessageKind, MessageState, Mutation,
    PageState, StatusPageCreate,
)
from app.status_communication.service import StatusCommunicationService


def _page(workspace: str = "alpha", owner: str = "owner") -> StatusPageCreate:
    return StatusPageCreate(
        workspace_id=workspace,
        owner_id=owner,
        page_key=f"core-{workspace}",
        name="Core services",
        components=[ComponentCreate(component_key="event-bus", name="Event Bus", service_key="event-bus")],
    )


def _message(page_id, component_id, owner: str = "owner") -> CommunicationCreate:
    return CommunicationCreate(
        workspace_id="alpha",
        owner_id=owner,
        page_id=page_id,
        message_key="event-bus-degraded",
        kind=MessageKind.INCIDENT,
        title="Event Bus degradation",
        body="We are investigating degraded event delivery.",
        audiences=[AudienceType.INTERNAL, AudienceType.EXECUTIVE],
        affected_component_ids=[component_id],
    )


def test_page_lifecycle_component_status_and_isolation() -> None:
    service = StatusCommunicationService()
    page = service.create_page(_page())
    assert page.state == PageState.DRAFT
    active = service.set_page_state(page.id, "alpha", Mutation(requester_id="owner"), PageState.ACTIVE)
    assert active is not None and active.state == PageState.ACTIVE
    component = service.update_component(ComponentStatusUpdate(
        workspace_id="alpha",
        requester_id="owner",
        page_id=page.id,
        component_id=page.components[0].id,
        status=ComponentStatus.DEGRADED,
        reason="latency increase",
    ))
    assert component.status == ComponentStatus.DEGRADED
    assert service.get_page(page.id, "beta") is None
    assert service.metrics("alpha").degraded_components == 1


def test_communication_approval_and_publication_gate() -> None:
    service = StatusCommunicationService()
    page = service.create_page(_page())
    service.set_page_state(page.id, "alpha", Mutation(requester_id="owner"), PageState.ACTIVE)
    message = service.create_message(_message(page.id, page.components[0].id))
    service.set_message_state(message.id, "alpha", Mutation(requester_id="owner"), MessageState.REVIEW)
    with pytest.raises(ValueError, match="self-approve"):
        service.approve(ApprovalCreate(workspace_id="alpha", requester_id="owner", communication_id=message.id))
    service.approve(ApprovalCreate(workspace_id="alpha", requester_id="reviewer", communication_id=message.id))
    assert message.state == MessageState.APPROVED
    published = service.set_message_state(message.id, "alpha", Mutation(requester_id="owner"), MessageState.PUBLISHED)
    assert published is not None and published.published_at is not None
    assert service.metrics("alpha").published_messages == 1


def test_publication_requires_active_page_and_approvals() -> None:
    service = StatusCommunicationService()
    page = service.create_page(_page())
    message = service.create_message(_message(page.id, page.components[0].id))
    service.set_message_state(message.id, "alpha", Mutation(requester_id="owner"), MessageState.REVIEW)
    service.approve(ApprovalCreate(workspace_id="alpha", requester_id="reviewer", communication_id=message.id))
    with pytest.raises(ValueError, match="must be active"):
        service.set_message_state(message.id, "alpha", Mutation(requester_id="owner"), MessageState.PUBLISHED)


def test_duplicate_keys_permissions_and_safety() -> None:
    service = StatusCommunicationService()
    page = service.create_page(_page())
    with pytest.raises(ValueError, match="already exists"):
        service.create_page(_page())
    assert service.set_page_state(page.id, "alpha", Mutation(requester_id="other"), PageState.ACTIVE) is None
    with pytest.raises(ValueError, match="automatic status-page activation"):
        StatusPageCreate(**{**_page().model_dump(), "automatic_activation": True})
    with pytest.raises(ValueError, match="automatic status publication"):
        StatusPageCreate(**{**_page().model_dump(), "automatic_publish": True})
    with pytest.raises(ValueError, match="external stakeholder notification"):
        CommunicationCreate(**{**_message(page.id, page.components[0].id).model_dump(), "notify_external": True})
    with pytest.raises(ValueError, match="never execute service changes"):
        ComponentStatusUpdate(
            workspace_id="alpha", requester_id="owner", page_id=page.id,
            component_id=page.components[0].id, status=ComponentStatus.MAJOR_OUTAGE,
            execute_change=True,
        )
