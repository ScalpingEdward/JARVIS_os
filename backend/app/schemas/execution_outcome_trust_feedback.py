from __future__ import annotations

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class OutcomeTrustState(str, Enum):
    BLOCKED = "blocked"
    EVIDENCE_READY = "evidence-ready"
    SCORED = "scored"
    REVIEW_REQUIRED = "review-required"
    APPROVED = "approved"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    REVOKED = "revoked"
    ARCHIVED = "archived"


class OutcomeTrustObservation(BaseModel):
    attestation_record_id: str = Field(min_length=1)
    attestation_digest: str = Field(min_length=8)
    adapter_id: str = Field(min_length=1)
    worker_id: str = Field(min_length=1)
    policy_profile_id: str = Field(min_length=1)
    planner_context_id: str = Field(min_length=1)
    operation: str = Field(min_length=1)
    target: str = Field(min_length=1)
    attestation_state: str = Field(min_length=1)
    postconditions_passed: bool
    no_prohibited_side_effects: bool
    receipt_reconciled: bool
    response_integrity: float = Field(ge=0, le=1)
    latency_quality: float = Field(ge=0, le=1)
    reliability_signal: float = Field(ge=0, le=1)
    evidence_confidence: float = Field(ge=0, le=1)
    freshness: float = Field(ge=0, le=1)
    criticality: float = Field(default=0.5, ge=0, le=1)


class OutcomeTrustCreate(BaseModel):
    workspace_id: str = Field(min_length=1)
    source_key: str = Field(min_length=1)
    requested_by: str = Field(min_length=1)
    observations: List[OutcomeTrustObservation] = Field(min_length=1)
    min_trust_score: float = Field(default=0.82, ge=0, le=1)
    max_residual_risk: float = Field(default=0.25, ge=0, le=1)


class OutcomeTrustFeedback(BaseModel):
    adapter_id: str
    worker_id: str
    policy_profile_id: str
    planner_context_id: str
    trust_score: float = Field(ge=0, le=1)
    residual_risk: float = Field(ge=0, le=1)
    feedback_signal: str
    recommendations: List[str] = Field(default_factory=list)


class OutcomeTrustScores(BaseModel):
    execution_trust: float = Field(ge=0, le=1)
    adapter_reliability: float = Field(ge=0, le=1)
    worker_reliability: float = Field(ge=0, le=1)
    policy_quality: float = Field(ge=0, le=1)
    planner_feedback_quality: float = Field(ge=0, le=1)
    aggregate_residual_risk: float = Field(ge=0, le=1)


class OutcomeTrustRecord(BaseModel):
    record_id: str
    workspace_id: str
    source_key: str
    state: OutcomeTrustState
    scores: OutcomeTrustScores
    feedback: List[OutcomeTrustFeedback]
    risk_flags: List[str] = Field(default_factory=list)
    approved_by: Optional[str] = None
    version: int = 1


class OutcomeTrustAction(BaseModel):
    workspace_id: str = Field(min_length=1)
    action: str = Field(min_length=1)
    actor: str = Field(min_length=1)
    operation_id: str = Field(min_length=1)
    reason: Optional[str] = None
