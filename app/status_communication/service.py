from datetime import datetime, timezone
from uuid import UUID

from .models import (
    ApprovalCreate, ApprovalRecord, AuditRecord, CommunicationCreate,
    CommunicationRecord, ComponentRecord, ComponentStatus, ComponentStatusUpdate,
    MessageKind, MessageState, MetricsRecord, Mutation, PageState, StatusCommunicationStatus,
    StatusPageCreate, StatusPageRecord,
)


class StatusCommunicationService:
    def __init__(self) -> None:
        self.pages: dict[UUID, StatusPageRecord] = {}
        self.messages: dict[UUID, CommunicationRecord] = {}
        self.approvals: list[ApprovalRecord] = []
        self.audit: list[AuditRecord] = []

    def _audit(self, workspace_id: str, action: str, entity_type: str, entity_id: UUID | None, actor_id: str, details: dict | None = None) -> None:
        self.audit.append(AuditRecord(workspace_id=workspace_id, action=action, entity_type=entity_type, entity_id=entity_id, actor_id=actor_id, details=details or {}))

    def status(self) -> StatusCommunicationStatus:
        components = sum(len(page.components) for page in self.pages.values())
        published = sum(item.state == MessageState.PUBLISHED for item in self.messages.values())
        return StatusCommunicationStatus(pages=len(self.pages), components=components, communications=len(self.messages), published_messages=published)

    def create_page(self, payload: StatusPageCreate) -> StatusPageRecord:
        if any(page.workspace_id == payload.workspace_id and page.page_key == payload.page_key and page.state != PageState.RETIRED for page in self.pages.values()):
            raise ValueError("active status page key already exists")
        components = [ComponentRecord(component_key=item.component_key, name=item.name, service_key=item.service_key, description=item.description, display_order=item.display_order, status=item.initial_status) for item in payload.components]
        page = StatusPageRecord(
            workspace_id=payload.workspace_id,
            owner_id=payload.owner_id,
            page_key=payload.page_key,
            name=payload.name,
            description=payload.description,
            timezone_name=payload.timezone_name,
            components=components,
            default_audiences=payload.default_audiences,
            labels=payload.labels,
            metadata=payload.metadata,
        )
        self.pages[page.id] = page
        self._audit(page.workspace_id, "status-page.created", "status-page", page.id, page.owner_id)
        return page

    def list_pages(self, workspace_id: str, state: PageState | None = None) -> list[StatusPageRecord]:
        return [item for item in self.pages.values() if item.workspace_id == workspace_id and (state is None or item.state == state)]

    def get_page(self, page_id: UUID, workspace_id: str) -> StatusPageRecord | None:
        page = self.pages.get(page_id)
        return page if page and page.workspace_id == workspace_id else None

    def set_page_state(self, page_id: UUID, workspace_id: str, payload: Mutation, state: PageState) -> StatusPageRecord | None:
        page = self.get_page(page_id, workspace_id)
        if page is None or page.owner_id != payload.requester_id:
            return None
        allowed = {
            PageState.DRAFT: {PageState.ACTIVE, PageState.RETIRED},
            PageState.ACTIVE: {PageState.PAUSED, PageState.RETIRED},
            PageState.PAUSED: {PageState.ACTIVE, PageState.RETIRED},
            PageState.RETIRED: set(),
        }
        if state not in allowed[page.state]:
            raise ValueError(f"invalid status-page transition: {page.state} -> {state}")
        page.state = state
        page.updated_at = datetime.now(timezone.utc)
        self._audit(workspace_id, f"status-page.{state.value}", "status-page", page.id, payload.requester_id, {"reason": payload.reason})
        return page

    def update_component(self, payload: ComponentStatusUpdate) -> ComponentRecord:
        page = self.get_page(payload.page_id, payload.workspace_id)
        if page is None:
            raise ValueError("status page not found")
        if page.owner_id != payload.requester_id:
            raise ValueError("only the page owner may update component status")
        component = next((item for item in page.components if item.id == payload.component_id), None)
        if component is None:
            raise ValueError("component not found")
        old_status = component.status
        component.status = payload.status
        component.updated_at = datetime.now(timezone.utc)
        page.updated_at = component.updated_at
        self._audit(payload.workspace_id, "component.status-updated", "component", component.id, payload.requester_id, {"from": old_status.value, "to": payload.status.value, "reason": payload.reason, "related_incident_id": str(payload.related_incident_id) if payload.related_incident_id else None})
        return component

    def create_message(self, payload: CommunicationCreate) -> CommunicationRecord:
        page = self.get_page(payload.page_id, payload.workspace_id)
        if page is None:
            raise ValueError("status page not found")
        if page.owner_id != payload.owner_id:
            raise ValueError("communication owner must own the status page")
        if any(item.workspace_id == payload.workspace_id and item.message_key == payload.message_key and item.state not in {MessageState.ARCHIVED, MessageState.CANCELLED} for item in self.messages.values()):
            raise ValueError("active communication key already exists")
        component_ids = {item.id for item in page.components}
        if any(item not in component_ids for item in payload.affected_component_ids):
            raise ValueError("affected component does not belong to status page")
        message = CommunicationRecord(**payload.model_dump())
        self.messages[message.id] = message
        self._audit(payload.workspace_id, "communication.created", "communication", message.id, payload.owner_id)
        return message

    def list_messages(self, workspace_id: str, state: MessageState | None = None, page_id: UUID | None = None) -> list[CommunicationRecord]:
        return [item for item in self.messages.values() if item.workspace_id == workspace_id and (state is None or item.state == state) and (page_id is None or item.page_id == page_id)]

    def set_message_state(self, message_id: UUID, workspace_id: str, payload: Mutation, state: MessageState) -> CommunicationRecord | None:
        message = self.messages.get(message_id)
        if message is None or message.workspace_id != workspace_id or message.owner_id != payload.requester_id:
            return None
        allowed = {
            MessageState.DRAFT: {MessageState.REVIEW, MessageState.CANCELLED},
            MessageState.REVIEW: {MessageState.DRAFT, MessageState.CANCELLED},
            MessageState.APPROVED: {MessageState.PUBLISHED, MessageState.CANCELLED},
            MessageState.PUBLISHED: {MessageState.ARCHIVED},
            MessageState.ARCHIVED: set(),
            MessageState.CANCELLED: set(),
        }
        if state not in allowed[message.state]:
            raise ValueError(f"invalid communication transition: {message.state} -> {state}")
        if state == MessageState.PUBLISHED:
            page = self.get_page(message.page_id, workspace_id)
            if page is None or page.state != PageState.ACTIVE:
                raise ValueError("status page must be active before publication")
            if message.approval_count < message.required_approvals:
                raise ValueError("required communication approvals are missing")
            message.published_at = datetime.now(timezone.utc)
        message.state = state
        message.updated_at = datetime.now(timezone.utc)
        self._audit(workspace_id, f"communication.{state.value}", "communication", message.id, payload.requester_id, {"reason": payload.reason})
        return message

    def approve(self, payload: ApprovalCreate) -> ApprovalRecord:
        message = self.messages.get(payload.communication_id)
        if message is None or message.workspace_id != payload.workspace_id:
            raise ValueError("communication not found")
        if message.state != MessageState.REVIEW:
            raise ValueError("communication must be in review")
        if message.owner_id == payload.requester_id:
            raise ValueError("communication owner cannot self-approve")
        if any(item.communication_id == message.id and item.requester_id == payload.requester_id for item in self.approvals):
            raise ValueError("reviewer has already approved this communication")
        approval = ApprovalRecord(**payload.model_dump())
        self.approvals.append(approval)
        message.approval_count += 1
        if message.approval_count >= message.required_approvals:
            message.state = MessageState.APPROVED
        message.updated_at = datetime.now(timezone.utc)
        self._audit(payload.workspace_id, "communication.approved", "communication", message.id, payload.requester_id, {"approval_count": message.approval_count})
        return approval

    def metrics(self, workspace_id: str) -> MetricsRecord:
        pages = self.list_pages(workspace_id)
        messages = self.list_messages(workspace_id)
        components = [component for page in pages for component in page.components]
        return MetricsRecord(
            workspace_id=workspace_id,
            pages=len(pages),
            active_pages=sum(item.state == PageState.ACTIVE for item in pages),
            components=len(components),
            degraded_components=sum(item.status == ComponentStatus.DEGRADED for item in components),
            outage_components=sum(item.status in {ComponentStatus.PARTIAL_OUTAGE, ComponentStatus.MAJOR_OUTAGE} for item in components),
            draft_messages=sum(item.state == MessageState.DRAFT for item in messages),
            review_messages=sum(item.state == MessageState.REVIEW for item in messages),
            published_messages=sum(item.state == MessageState.PUBLISHED for item in messages),
            maintenance_messages=sum(item.kind == MessageKind.MAINTENANCE for item in messages),
        )

    def list_audit(self, workspace_id: str) -> list[AuditRecord]:
        return [item for item in self.audit if item.workspace_id == workspace_id]


status_communication_service = StatusCommunicationService()
