from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class ComplianceState(str, Enum):
    BLOCKED = "blocked"
    DRAFT = "draft"
    EVIDENCE_READY = "evidence-ready"
    ASSESSED = "assessed"
    POLICY_READY = "policy-ready"
    REVIEW_REQUIRED = "review-required"
    APPROVED = "approved"
    ACTIVE = "active"
    MONITORING = "monitoring"
    COMPLIANT = "compliant"
    CONTROL_GAP = "control-gap"
    DISCLOSURE_GAP = "disclosure-gap"
    RESTRICTION_ALERT = "restriction-alert"
    SURVEILLANCE_ALERT = "surveillance-alert"
    RECORDKEEPING_ALERT = "recordkeeping-alert"
    ESCALATED = "escalated"
    SUSPENDED = "suspended"
    REVOKED = "revoked"
    ARCHIVED = "archived"


class ComplianceObservation(BaseModel):
    control_id: str = Field(min_length=1, max_length=120)
    domain: str = Field(min_length=1, max_length=80)
    jurisdiction: str = Field(min_length=1, max_length=80)
    policy_coverage: float = Field(ge=0, le=1)
    evidence_completeness: float = Field(ge=0, le=1)
    control_effectiveness: float = Field(ge=0, le=1)
    disclosure_readiness: float = Field(ge=0, le=1)
    surveillance_coverage: float = Field(ge=0, le=1)
    recordkeeping_quality: float = Field(ge=0, le=1)
    restriction_breach_count: int = Field(default=0, ge=0)
    unresolved_findings: int = Field(default=0, ge=0)
    materiality: float = Field(default=0.5, ge=0, le=1)
    confidence: float = Field(default=1, ge=0, le=1)
    freshness: float = Field(default=1, ge=0, le=1)
    provenance: List[str] = Field(default_factory=list)


class InstitutionalComplianceCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    source_key: str = Field(min_length=1, max_length=160)
    observations: List[ComplianceObservation] = Field(min_length=1)
    restricted_domains: List[str] = Field(default_factory=list)
    required_jurisdictions: List[str] = Field(default_factory=list)
    requested_by: str = Field(min_length=1, max_length=120)


class ComplianceAssessment(BaseModel):
    control_id: str
    domain: str
    jurisdiction: str
    compliance_score: float
    evidence_score: float
    monitoring_score: float
    severity_score: float
    disposition: str


class InstitutionalComplianceScores(BaseModel):
    policy_coverage: float
    evidence_integrity: float
    control_effectiveness: float
    disclosure_readiness: float
    surveillance_coverage: float
    recordkeeping_quality: float
    restriction_integrity: float
    aggregate_compliance: float
    confidence: float


class InstitutionalComplianceRecord(BaseModel):
    record_id: str
    workspace_id: str
    source_key: str
    state: ComplianceState
    scores: InstitutionalComplianceScores
    assessments: List[ComplianceAssessment]
    required_actions: List[str]
    risk_flags: List[str]
    approved_by: Optional[str] = None
    version: int = 1


class InstitutionalComplianceAction(BaseModel):
    action: str = Field(pattern="^(assess|submit-review|approve|activate|monitor|suspend|revoke|archive)$")
    actor: str = Field(min_length=1, max_length=120)
    operation_id: str = Field(min_length=1, max_length=160)
    reason: Optional[str] = Field(default=None, max_length=500)
