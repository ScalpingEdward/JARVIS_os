from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator


class IncidentSeverity(str, Enum):
    SEV1 = "sev1"
    SEV2 = "sev2"
    SEV3 = "sev3"
    SEV4 = "sev4"


class IncidentState(str, Enum):
    DECLARED = "declared"
    INVESTIGATING = "investigating"
    MITIGATING = "mitigating"
    MONITORING = "monitoring"
    RESOLVED = "resolved"
    CLOSED = "closed"
    CANCELLED = "cancelled"


class TimelineKind(str, Enum):
    DETECTION = "detection"
    STATUS = "status"
    DIAGNOSIS = "diagnosis"
    MITIGATION = "mitigation"
    COMMUNICATION = "communication"
    RECOVERY = "recovery"
    NOTE = "note"


class ActionState(str, Enum):
    OPEN = "open"
    IN_PROGRESS = "in-progress"
    BLOCKED = "blocked"
    DONE = "done"
    CANCELLED = "cancelled"


class PostmortemState(str, Enum):
    DRAFT = "draft"
    REVIEW = "review"
    APPROVED = "approved"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class IncidentCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    owner_id: str = Field(min_length=1, max_length=120)
    incident_key: str = Field(min_length=1, max_length=180, pattern=r"^[a-z0-9_.-]+$")
    title: str = Field(min_length=1, max_length=300)
    summary: str = Field(default="", max_length=6000)
    severity: IncidentSeverity
    commander_id: str = Field(min_length=1, max_length=120)
    affected_services: list[str] = Field(default_factory=list, max_length=500)
    related_slo_ids: list[UUID] = Field(default_factory=list, max_length=200)
    detected_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    labels: dict[str, str] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
    human_approved: bool = True
    automatic_declaration: bool = False
    execute_mitigation: bool = False
    notify_external: bool = False

    @model_validator(mode="after")
    def safety(self) -> "IncidentCreate":
        if not self.human_approved:
            raise ValueError("human approval is required")
        if self.automatic_declaration:
            raise ValueError("automatic incident declaration is disabled")
        if self.execute_mitigation:
            raise ValueError("incident records never execute mitigation actions")
        if self.notify_external:
            raise ValueError("automatic external incident notification is disabled")
        return self


class IncidentRecord(IncidentCreate):
    id: UUID = Field(default_factory=uuid4)
    state: IncidentState = IncidentState.DECLARED
    responder_ids: list[str] = Field(default_factory=list)
    resolved_at: datetime | None = None
    closed_at: datetime | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class IncidentMutation(BaseModel):
    requester_id: str = Field(min_length=1, max_length=120)
    reason: str = Field(default="", max_length=4000)
    human_approved: bool = True

    @model_validator(mode="after")
    def require_human(self) -> "IncidentMutation":
        if not self.human_approved:
            raise ValueError("human approval is required")
        return self


class ResponderMutation(IncidentMutation):
    responder_id: str = Field(min_length=1, max_length=120)


class TimelineCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    requester_id: str = Field(min_length=1, max_length=120)
    incident_id: UUID
    kind: TimelineKind
    message: str = Field(min_length=1, max_length=6000)
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    source_reference: str = Field(default="", max_length=1000)
    metadata: dict[str, Any] = Field(default_factory=dict)
    human_approved: bool = True
    execute_action: bool = False

    @model_validator(mode="after")
    def safety(self) -> "TimelineCreate":
        if not self.human_approved:
            raise ValueError("human approval is required")
        if self.execute_action:
            raise ValueError("timeline entries never execute operational actions")
        return self


class TimelineRecord(TimelineCreate):
    id: UUID = Field(default_factory=uuid4)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class FollowUpCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    requester_id: str = Field(min_length=1, max_length=120)
    incident_id: UUID
    title: str = Field(min_length=1, max_length=300)
    description: str = Field(default="", max_length=6000)
    assignee_id: str = Field(min_length=1, max_length=120)
    priority: IncidentSeverity = IncidentSeverity.SEV3
    due_at: datetime | None = None
    source_reference: str = Field(default="", max_length=1000)
    human_approved: bool = True
    create_external_ticket: bool = False
    execute_remediation: bool = False

    @model_validator(mode="after")
    def safety(self) -> "FollowUpCreate":
        if not self.human_approved:
            raise ValueError("human approval is required")
        if self.create_external_ticket:
            raise ValueError("automatic external ticket creation is disabled")
        if self.execute_remediation:
            raise ValueError("follow-up actions never execute remediation")
        return self


class FollowUpRecord(FollowUpCreate):
    id: UUID = Field(default_factory=uuid4)
    state: ActionState = ActionState.OPEN
    completed_at: datetime | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class PostmortemCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    requester_id: str = Field(min_length=1, max_length=120)
    incident_id: UUID
    title: str = Field(min_length=1, max_length=300)
    impact: str = Field(min_length=1, max_length=10000)
    root_cause: str = Field(min_length=1, max_length=10000)
    contributing_factors: list[str] = Field(default_factory=list, max_length=500)
    detection_analysis: str = Field(default="", max_length=10000)
    response_analysis: str = Field(default="", max_length=10000)
    lessons_learned: list[str] = Field(default_factory=list, max_length=500)
    human_approved: bool = True
    automatic_publication: bool = False
    submit_external: bool = False

    @model_validator(mode="after")
    def safety(self) -> "PostmortemCreate":
        if not self.human_approved:
            raise ValueError("human approval is required")
        if self.automatic_publication:
            raise ValueError("automatic postmortem publication is disabled")
        if self.submit_external:
            raise ValueError("external postmortem submission is disabled")
        return self


class PostmortemRecord(PostmortemCreate):
    id: UUID = Field(default_factory=uuid4)
    state: PostmortemState = PostmortemState.DRAFT
    approved_by: str | None = None
    approved_at: datetime | None = None
    published_at: datetime | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class IncidentMetrics(BaseModel):
    workspace_id: str
    incidents: int
    active_incidents: int
    resolved_incidents: int
    closed_incidents: int
    sev1_open: int
    sev2_open: int
    timeline_entries: int
    open_follow_ups: int
    overdue_follow_ups: int
    postmortems_pending: int


class AuditRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    action: str
    entity_type: str
    entity_id: UUID | None = None
    actor_id: str
    details: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class IncidentStatus(BaseModel):
    version: str = "10.2"
    incidents: int
    active_incidents: int
    postmortems: int
    open_follow_ups: int
    automatic_declaration_enabled: bool = False
    automatic_mitigation_enabled: bool = False
    automatic_external_notification_enabled: bool = False
    automatic_publication_enabled: bool = False
