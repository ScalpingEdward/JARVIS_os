from datetime import datetime
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator


class GovernanceStatus(str, Enum):
    draft = "draft"
    assessed = "assessed"
    compliant = "compliant"
    non_compliant = "non_compliant"


class ControlSeverity(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class GovernanceRole(BaseModel):
    actor_id: str = Field(min_length=1, max_length=100)
    role: str = Field(min_length=1, max_length=100)
    accountable_for: list[str] = Field(default_factory=list)
    decision_rights: list[str] = Field(default_factory=list)


class GovernanceControl(BaseModel):
    control_key: str = Field(min_length=1, max_length=100)
    title: str = Field(min_length=1, max_length=200)
    owner_id: str = Field(min_length=1, max_length=100)
    severity: ControlSeverity = ControlSeverity.medium
    required: bool = True
    evidence_refs: list[str] = Field(default_factory=list)
    passed: bool | None = None


class ReviewCycle(BaseModel):
    review_key: str = Field(min_length=1, max_length=100)
    title: str = Field(min_length=1, max_length=200)
    reviewer_ids: list[str] = Field(min_length=1)
    frequency_days: int = Field(gt=0, le=3650)
    last_reviewed_at: datetime | None = None
    next_review_at: datetime | None = None


class EscalationRule(BaseModel):
    trigger: str = Field(min_length=1, max_length=200)
    severity: ControlSeverity
    escalation_owner_id: str = Field(min_length=1, max_length=100)
    response_sla_hours: int = Field(gt=0, le=8760)


class GovernanceFrameworkCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=100)
    owner_id: str = Field(min_length=1, max_length=100)
    title: str = Field(min_length=1, max_length=200)
    scope: str = Field(min_length=1, max_length=1000)
    strategy_plan_ids: list[UUID] = Field(default_factory=list)
    scorecard_ids: list[UUID] = Field(default_factory=list)
    roles: list[GovernanceRole] = Field(min_length=1)
    controls: list[GovernanceControl] = Field(min_length=1)
    review_cycles: list[ReviewCycle] = Field(default_factory=list)
    escalation_rules: list[EscalationRule] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_framework(self):
        role_pairs = [(item.actor_id, item.role) for item in self.roles]
        if len(role_pairs) != len(set(role_pairs)):
            raise ValueError("Governance role assignments must be unique")
        keys = [item.control_key for item in self.controls]
        if len(keys) != len(set(keys)):
            raise ValueError("Governance control keys must be unique")
        return self


class ControlResult(BaseModel):
    control_key: str
    passed: bool
    blocking: bool
    severity: ControlSeverity
    explanation: str


class GovernanceViolation(BaseModel):
    violation_key: str
    control_key: str
    severity: ControlSeverity
    owner_id: str
    escalation_owner_id: str | None = None
    response_sla_hours: int | None = None
    explanation: str


class AccountabilityAssessment(BaseModel):
    assessed_at: datetime
    accountability_score: float = Field(ge=0, le=100)
    governance_compliance_score: float = Field(ge=0, le=100)
    role_coverage_score: float = Field(ge=0, le=100)
    review_readiness_score: float = Field(ge=0, le=100)
    control_results: list[ControlResult]
    violations: list[GovernanceViolation]
    escalation_queue: list[GovernanceViolation]
    recommendations: list[str]
    executive_summary: str
    autonomous_actions_enabled: bool = False


class ControlUpdate(BaseModel):
    actor_id: str = Field(min_length=1, max_length=100)
    control_key: str = Field(min_length=1, max_length=100)
    passed: bool
    evidence_refs: list[str] = Field(default_factory=list)


class ExecutiveGovernanceFramework(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    owner_id: str
    title: str
    scope: str
    strategy_plan_ids: list[UUID]
    scorecard_ids: list[UUID]
    roles: list[GovernanceRole]
    controls: list[GovernanceControl]
    review_cycles: list[ReviewCycle]
    escalation_rules: list[EscalationRule]
    status: GovernanceStatus = GovernanceStatus.draft
    version: int = 1
    assessment: AccountabilityAssessment | None = None
    created_at: datetime
    updated_at: datetime


class GovernanceStatusResponse(BaseModel):
    version: str = "18.5"
    frameworks: int
    assessed_frameworks: int
    compliant_frameworks: int
    open_violations: int
    autonomous_actions_enabled: bool = False


class GovernanceListResponse(BaseModel):
    items: list[ExecutiveGovernanceFramework]
    count: int


class AuditRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    action: str
    actor_id: str
    framework_id: UUID | None = None
    details: dict = Field(default_factory=dict)
    created_at: datetime
