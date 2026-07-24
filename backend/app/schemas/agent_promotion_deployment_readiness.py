from __future__ import annotations

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field, model_validator


class AgentPromotionState(str, Enum):
    BLOCKED = "blocked"
    DRAFT = "draft"
    EVIDENCE_READY = "evidence-ready"
    ASSESSED = "assessed"
    REVIEW_REQUIRED = "review-required"
    APPROVED = "approved"
    ACTIVE = "active"
    MONITORING = "monitoring"
    PROMOTION_READY = "promotion-ready"
    VALIDATION_GAP = "validation-gap"
    COMPATIBILITY_ALERT = "compatibility-alert"
    OBSERVABILITY_ALERT = "observability-alert"
    ROLLBACK_ALERT = "rollback-alert"
    RELEASE_RISK_ALERT = "release-risk-alert"
    ESCALATED = "escalated"
    SUSPENDED = "suspended"
    REVOKED = "revoked"
    ARCHIVED = "archived"


class PromotionCandidateObservation(BaseModel):
    agent_id: str = Field(min_length=1, max_length=160)
    candidate_version: str = Field(min_length=1, max_length=80)
    current_version: str = Field(min_length=1, max_length=80)
    validation_coverage: float = Field(ge=0.0, le=1.0)
    regression_coverage: float = Field(ge=0.0, le=1.0)
    safety_validation_score: float = Field(ge=0.0, le=1.0)
    compatibility_score: float = Field(ge=0.0, le=1.0)
    dependency_readiness: float = Field(ge=0.0, le=1.0)
    observability_readiness: float = Field(ge=0.0, le=1.0)
    rollback_readiness: float = Field(ge=0.0, le=1.0)
    canary_readiness: float = Field(ge=0.0, le=1.0)
    change_traceability: float = Field(ge=0.0, le=1.0)
    human_review_coverage: float = Field(ge=0.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)
    freshness: float = Field(ge=0.0, le=1.0)
    blocking_findings: int = Field(default=0, ge=0)
    failed_regressions: int = Field(default=0, ge=0)
    rollback_failures: int = Field(default=0, ge=0)
    unresolved_dependencies: int = Field(default=0, ge=0)
    observability_gaps: int = Field(default=0, ge=0)
    business_criticality: float = Field(default=0.5, ge=0.0, le=1.0)


class AgentPromotionCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    source_key: str = Field(min_length=1, max_length=200)
    requested_by: str = Field(min_length=1, max_length=160)
    observations: List[PromotionCandidateObservation] = Field(min_length=1)
    min_validation_coverage: float = Field(default=0.90, ge=0.0, le=1.0)
    min_safety_validation: float = Field(default=0.90, ge=0.0, le=1.0)
    min_compatibility_score: float = Field(default=0.85, ge=0.0, le=1.0)
    min_observability_readiness: float = Field(default=0.85, ge=0.0, le=1.0)
    min_rollback_readiness: float = Field(default=0.90, ge=0.0, le=1.0)
    max_residual_risk: float = Field(default=0.35, ge=0.0, le=1.0)

    @model_validator(mode="after")
    def unique_candidates(self):
        pairs = [(o.agent_id, o.candidate_version) for o in self.observations]
        if len(pairs) != len(set(pairs)):
            raise ValueError("duplicate agent/version observation")
        return self


class PromotionDisposition(BaseModel):
    agent_id: str
    candidate_version: str
    readiness_score: float = Field(ge=0.0, le=1.0)
    residual_risk: float = Field(ge=0.0, le=1.0)
    lifecycle_signal: str
    required_actions: List[str] = Field(default_factory=list)


class AgentPromotionScores(BaseModel):
    validation_assurance: float = Field(ge=0.0, le=1.0)
    safety_assurance: float = Field(ge=0.0, le=1.0)
    compatibility_assurance: float = Field(ge=0.0, le=1.0)
    dependency_assurance: float = Field(ge=0.0, le=1.0)
    observability_assurance: float = Field(ge=0.0, le=1.0)
    rollback_assurance: float = Field(ge=0.0, le=1.0)
    release_assurance: float = Field(ge=0.0, le=1.0)
    aggregate_readiness: float = Field(ge=0.0, le=1.0)
    aggregate_residual_risk: float = Field(ge=0.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)


class AgentPromotionRecord(BaseModel):
    record_id: str
    workspace_id: str
    source_key: str
    state: AgentPromotionState
    scores: AgentPromotionScores
    dispositions: List[PromotionDisposition]
    risk_flags: List[str] = Field(default_factory=list)
    approved_by: Optional[str] = None
    version: int = 1


class AgentPromotionAction(BaseModel):
    workspace_id: str = Field(min_length=1)
    action: str = Field(min_length=1)
    actor: str = Field(min_length=1)
    operation_id: str = Field(min_length=1)
    reason: Optional[str] = None
