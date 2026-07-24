from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class ModelAssuranceState(str, Enum):
    BLOCKED = "blocked"
    DRAFT = "draft"
    EVIDENCE_READY = "evidence-ready"
    ASSESSED = "assessed"
    VALIDATION_REQUIRED = "validation-required"
    REVIEW_REQUIRED = "review-required"
    APPROVED = "approved"
    ACTIVE = "active"
    MONITORING = "monitoring"
    ASSURED = "assured"
    DRIFT_ALERT = "drift-alert"
    BIAS_ALERT = "bias-alert"
    EXPLAINABILITY_GAP = "explainability-gap"
    DATA_QUALITY_ALERT = "data-quality-alert"
    VALIDATION_FAILURE = "validation-failure"
    ESCALATED = "escalated"
    SUSPENDED = "suspended"
    REVOKED = "revoked"
    ARCHIVED = "archived"


class ModelObservation(BaseModel):
    model_id: str = Field(min_length=1, max_length=120)
    model_version: str = Field(min_length=1, max_length=80)
    model_type: str = Field(min_length=1, max_length=80)
    business_criticality: float = Field(ge=0, le=1)
    validation_coverage: float = Field(ge=0, le=1)
    performance_stability: float = Field(ge=0, le=1)
    calibration_quality: float = Field(ge=0, le=1)
    explainability_coverage: float = Field(ge=0, le=1)
    fairness_score: float = Field(ge=0, le=1)
    data_quality_score: float = Field(ge=0, le=1)
    drift_score: float = Field(ge=0, le=1)
    robustness_score: float = Field(ge=0, le=1)
    fallback_readiness: float = Field(ge=0, le=1)
    human_oversight_coverage: float = Field(ge=0, le=1)
    incident_count: int = Field(default=0, ge=0)
    open_validation_findings: int = Field(default=0, ge=0)
    confidence: float = Field(default=1, ge=0, le=1)
    freshness: float = Field(default=1, ge=0, le=1)
    provenance: List[str] = Field(default_factory=list)


class ModelRiskAssuranceCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    source_key: str = Field(min_length=1, max_length=160)
    observations: List[ModelObservation] = Field(min_length=1)
    max_acceptable_risk: float = Field(default=0.35, ge=0, le=1)
    required_validation_coverage: float = Field(default=0.80, ge=0, le=1)
    requested_by: str = Field(min_length=1, max_length=120)


class ModelDisposition(BaseModel):
    model_id: str
    model_version: str
    assurance_score: float
    residual_risk: float
    lifecycle_signal: str
    required_actions: List[str]


class ModelRiskAssuranceScores(BaseModel):
    validation_strength: float
    performance_resilience: float
    explainability_strength: float
    fairness_integrity: float
    data_governance_quality: float
    operational_resilience: float
    aggregate_assurance: float
    aggregate_residual_risk: float
    confidence: float


class ModelRiskAssuranceRecord(BaseModel):
    record_id: str
    workspace_id: str
    source_key: str
    state: ModelAssuranceState
    scores: ModelRiskAssuranceScores
    dispositions: List[ModelDisposition]
    risk_flags: List[str]
    approved_by: Optional[str] = None
    version: int = 1


class ModelRiskAssuranceAction(BaseModel):
    action: str = Field(pattern="^(assess|submit-review|approve|activate|monitor|suspend|revoke|archive)$")
    actor: str = Field(min_length=1, max_length=120)
    operation_id: str = Field(min_length=1, max_length=160)
    reason: Optional[str] = Field(default=None, max_length=500)
