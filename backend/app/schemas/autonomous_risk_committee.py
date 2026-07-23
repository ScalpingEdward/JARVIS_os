from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class RiskCommitteeState(str, Enum):
    BLOCKED = "blocked"
    DRAFT = "draft"
    EVIDENCE_READY = "evidence-ready"
    DELIBERATING = "deliberating"
    REVIEW_REQUIRED = "review-required"
    APPROVED = "approved"
    ACTIVE = "active"
    MONITORING = "monitoring"
    STABLE = "stable"
    RISK_WARNING = "risk-warning"
    LIMIT_REVIEW = "limit-review"
    CAPITAL_PRESERVATION = "capital-preservation"
    INFRASTRUCTURE_HOLD = "infrastructure-hold"
    ESCALATED = "escalated"
    SUSPENDED = "suspended"
    REVOKED = "revoked"
    ARCHIVED = "archived"


class CommitteeMemberAssessment(BaseModel):
    member_id: str = Field(min_length=1, max_length=120)
    domain: str = Field(min_length=1, max_length=80)
    stance: str = Field(pattern="^(support|caution|oppose|abstain)$")
    confidence: float = Field(ge=0, le=1)
    severity: float = Field(ge=0, le=1)
    rationale: str = Field(min_length=1, max_length=1000)
    evidence_refs: List[str] = Field(default_factory=list)


class RiskCommitteeCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    source_key: str = Field(min_length=1, max_length=160)
    portfolio_brain_record_id: str = Field(min_length=1, max_length=160)
    assessments: List[CommitteeMemberAssessment] = Field(min_length=1)
    quorum_threshold: float = Field(default=0.60, gt=0, le=1)
    approval_threshold: float = Field(default=0.67, gt=0, le=1)
    veto_domains: List[str] = Field(default_factory=lambda: ["risk-brain", "compliance"])
    requested_by: str = Field(min_length=1, max_length=120)


class RiskCommitteeDecision(BaseModel):
    decision: str
    approval_ratio: float
    opposition_ratio: float
    weighted_risk_severity: float
    quorum_met: bool
    veto_triggered: bool
    required_actions: List[str]


class RiskCommitteeRecord(BaseModel):
    record_id: str
    workspace_id: str
    source_key: str
    state: RiskCommitteeState
    decision: RiskCommitteeDecision
    assessments: List[CommitteeMemberAssessment]
    approved_by: Optional[str] = None
    version: int = 1


class RiskCommitteeAction(BaseModel):
    action: str = Field(pattern="^(deliberate|submit-review|approve|activate|monitor|suspend|revoke|archive)$")
    actor: str = Field(min_length=1, max_length=120)
    operation_id: str = Field(min_length=1, max_length=160)
    reason: Optional[str] = Field(default=None, max_length=500)
