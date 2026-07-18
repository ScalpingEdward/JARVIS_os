from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator


class EventOutcome(str, Enum):
    SUCCESS = "success"
    FAILURE = "failure"
    DENIED = "denied"
    WARNING = "warning"


class FindingSeverity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class FindingState(str, Enum):
    OPEN = "open"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"
    ARCHIVED = "archived"


class ReportState(str, Enum):
    DRAFT = "draft"
    REVIEWED = "reviewed"
    APPROVED = "approved"
    ARCHIVED = "archived"


class AuditEventCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    actor_id: str = Field(min_length=1, max_length=120)
    module: str = Field(min_length=1, max_length=160)
    action: str = Field(min_length=1, max_length=240)
    outcome: EventOutcome
    entity_type: str = Field(default="", max_length=160)
    entity_id: str = Field(default="", max_length=240)
    policy_key: str = Field(default="", max_length=180)
    source_ip: str = Field(default="", max_length=100)
    metadata: dict[str, Any] = Field(default_factory=dict)
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    execute_action: bool = False

    @model_validator(mode="after")
    def safety(self) -> "AuditEventCreate":
        if self.execute_action:
            raise ValueError("audit events never execute actions")
        return self


class AuditEventRecord(AuditEventCreate):
    id: UUID = Field(default_factory=uuid4)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ComplianceRuleCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    owner_id: str = Field(min_length=1, max_length=120)
    rule_key: str = Field(min_length=1, max_length=180, pattern=r"^[a-z0-9_.-]+$")
    name: str = Field(min_length=1, max_length=300)
    module: str = Field(default="*", min_length=1, max_length=160)
    action_prefix: str = Field(default="", max_length=240)
    prohibited_outcomes: list[EventOutcome] = Field(default_factory=list)
    max_failures: int = Field(default=0, ge=0, le=100000)
    window_minutes: int = Field(default=60, ge=1, le=525600)
    severity: FindingSeverity = FindingSeverity.MEDIUM
    enabled: bool = True
    automatic_remediation: bool = False

    @model_validator(mode="after")
    def safety(self) -> "ComplianceRuleCreate":
        if not self.prohibited_outcomes and self.max_failures == 0:
            raise ValueError("rule requires prohibited outcomes or a failure threshold")
        if self.automatic_remediation:
            raise ValueError("automatic remediation is disabled")
        return self


class ComplianceRuleRecord(ComplianceRuleCreate):
    id: UUID = Field(default_factory=uuid4)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class FindingRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    rule_id: UUID
    event_id: UUID
    severity: FindingSeverity
    state: FindingState = FindingState.OPEN
    title: str
    description: str
    acknowledged_by: str = ""
    resolved_by: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Mutation(BaseModel):
    requester_id: str = Field(min_length=1, max_length=120)
    reason: str = Field(default="", max_length=4000)
    human_approved: bool = True

    @model_validator(mode="after")
    def require_human(self) -> "Mutation":
        if not self.human_approved:
            raise ValueError("human approval is required")
        return self


class ReportCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    owner_id: str = Field(min_length=1, max_length=120)
    title: str = Field(min_length=1, max_length=300)
    period_start: datetime
    period_end: datetime

    @model_validator(mode="after")
    def dates(self) -> "ReportCreate":
        if self.period_end <= self.period_start:
            raise ValueError("report period end must be after start")
        return self


class ReportRecord(ReportCreate):
    id: UUID = Field(default_factory=uuid4)
    state: ReportState = ReportState.DRAFT
    compliance_score: float = Field(ge=0, le=100)
    total_events: int = 0
    failed_events: int = 0
    open_findings: int = 0
    critical_findings: int = 0
    reviewed_by: str = ""
    approved_by: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class MetricsRecord(BaseModel):
    workspace_id: str
    audit_events: int
    compliance_rules: int
    open_findings: int
    critical_findings: int
    reports: int
    compliance_score: float


class AuditComplianceStatus(BaseModel):
    version: str = "11.2"
    external_compliance_services: bool = False
    automatic_remediation: bool = False
    system_mutation: bool = False
    human_approval_required: bool = True
