from __future__ import annotations

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field, model_validator


class OptimizationState(str, Enum):
    BLOCKED = "blocked"
    EVIDENCE_READY = "evidence-ready"
    ASSESSED = "assessed"
    REVIEW_REQUIRED = "review-required"
    APPROVED = "approved"
    ADVISORY_READY = "advisory-ready"
    MONITORING = "monitoring"
    SUSPENDED = "suspended"
    REVOKED = "revoked"
    ARCHIVED = "archived"


class OptimizationObservation(BaseModel):
    agent_id: str = Field(min_length=1, max_length=160)
    agent_version: str = Field(min_length=1, max_length=80)
    recommendation_id: str = Field(min_length=1, max_length=160)
    performance_gain_confidence: float = Field(ge=0.0, le=1.0)
    cost_reduction_confidence: float = Field(ge=0.0, le=1.0)
    resource_efficiency_gain: float = Field(ge=0.0, le=1.0)
    reliability_impact: float = Field(ge=0.0, le=1.0)
    reversibility: float = Field(ge=0.0, le=1.0)
    validation_coverage: float = Field(ge=0.0, le=1.0)
    observability_readiness: float = Field(ge=0.0, le=1.0)
    rollback_readiness: float = Field(ge=0.0, le=1.0)
    dependency_impact_clarity: float = Field(ge=0.0, le=1.0)
    human_review_coverage: float = Field(ge=0.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)
    freshness: float = Field(ge=0.0, le=1.0)
    unresolved_validation_findings: int = Field(default=0, ge=0)
    dependency_risk_findings: int = Field(default=0, ge=0)
    rollback_failures: int = Field(default=0, ge=0)
    criticality: float = Field(default=0.5, ge=0.0, le=1.0)


class OptimizationCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    source_key: str = Field(min_length=1, max_length=200)
    requested_by: str = Field(min_length=1, max_length=160)
    observations: List[OptimizationObservation] = Field(min_length=1)
    min_validation: float = Field(default=0.90, ge=0.0, le=1.0)
    min_reversibility: float = Field(default=0.90, ge=0.0, le=1.0)
    min_human_review: float = Field(default=0.95, ge=0.0, le=1.0)
    max_residual_risk: float = Field(default=0.30, ge=0.0, le=1.0)

    @model_validator(mode="after")
    def unique_recommendations(self):
        keys = [(o.agent_id, o.recommendation_id) for o in self.observations]
        if len(keys) != len(set(keys)):
            raise ValueError("duplicate agent/recommendation observation")
        return self


class OptimizationDisposition(BaseModel):
    agent_id: str
    agent_version: str
    recommendation_id: str
    value_score: float = Field(ge=0.0, le=1.0)
    assurance: float = Field(ge=0.0, le=1.0)
    residual_risk: float = Field(ge=0.0, le=1.0)
    lifecycle_signal: str
    required_actions: List[str] = Field(default_factory=list)


class OptimizationScores(BaseModel):
    value_assurance: float = Field(ge=0.0, le=1.0)
    safety_assurance: float = Field(ge=0.0, le=1.0)
    reversibility_assurance: float = Field(ge=0.0, le=1.0)
    validation_assurance: float = Field(ge=0.0, le=1.0)
    aggregate_assurance: float = Field(ge=0.0, le=1.0)
    aggregate_residual_risk: float = Field(ge=0.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)


class OptimizationRecord(BaseModel):
    record_id: str
    workspace_id: str
    source_key: str
    state: OptimizationState
    scores: OptimizationScores
    dispositions: List[OptimizationDisposition]
    risk_flags: List[str] = Field(default_factory=list)
    approved_by: Optional[str] = None
    version: int = 1


class OptimizationAction(BaseModel):
    workspace_id: str = Field(min_length=1)
    action: str = Field(min_length=1)
    actor: str = Field(min_length=1)
    operation_id: str = Field(min_length=1)
    reason: Optional[str] = None
