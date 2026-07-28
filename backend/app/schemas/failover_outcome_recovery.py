from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field


class FailoverRecoveryState(str, Enum):
    BLOCKED = "blocked"
    EVIDENCE_READY = "evidence-ready"
    REVIEW_REQUIRED = "review-required"
    APPROVED = "approved"
    RECOVERY_READY = "recovery-ready"
    HOLD = "hold"
    REVOKED = "revoked"
    ARCHIVED = "archived"


class FailoverOutcomeEvidence(BaseModel):
    completion_attested: bool
    side_effect_safe: bool
    receipt_reconciled: bool
    standby_stable: bool
    primary_available: bool
    primary_latency_ms: float = Field(ge=0)
    primary_health: float = Field(ge=0, le=1)
    primary_receipt_reconciliation: float = Field(ge=0, le=1)
    confidence: float = Field(default=1, ge=0, le=1)
    freshness: float = Field(default=1, ge=0, le=1)


class FailoverRecoveryCreate(BaseModel):
    workspace_id: str = Field(min_length=1)
    source_key: str = Field(min_length=1)
    requested_by: str = Field(min_length=1)
    failover_attestation_id: str = Field(min_length=1)
    failover_attestation_digest: str = Field(min_length=8)
    dispatch_plan_id: str = Field(min_length=1)
    dispatch_plan_digest: str = Field(min_length=8)
    operation: str = Field(min_length=1)
    target: str = Field(min_length=1)
    primary_adapter_id: str = Field(min_length=1)
    primary_worker_id: str = Field(min_length=1)
    standby_adapter_id: str = Field(min_length=1)
    standby_worker_id: str = Field(min_length=1)
    max_primary_latency_ms: float = Field(default=1500, gt=0)
    min_primary_health: float = Field(default=.9, ge=0, le=1)
    min_primary_receipt_reconciliation: float = Field(default=.95, ge=0, le=1)
    upstream_risk_brain_blocked: bool = False
    evidence: FailoverOutcomeEvidence


class FailoverRecoveryScores(BaseModel):
    failover_trust: float = Field(ge=0, le=1)
    primary_recovery_readiness: float = Field(ge=0, le=1)
    residual_risk: float = Field(ge=0, le=1)


class FailoverRecoveryRecord(BaseModel):
    record_id: str
    workspace_id: str
    source_key: str
    state: FailoverRecoveryState
    failover_attestation_id: str
    failover_attestation_digest: str
    dispatch_plan_id: str
    dispatch_plan_digest: str
    operation: str
    target: str
    primary_adapter_id: str
    primary_worker_id: str
    standby_adapter_id: str
    standby_worker_id: str
    findings: List[str] = Field(default_factory=list)
    recommendations: List[str] = Field(default_factory=list)
    scores: FailoverRecoveryScores
    evidence_digest: str
    recovery_digest: str
    approved_by: Optional[str] = None
    version: int = 1


class FailoverRecoveryAction(BaseModel):
    workspace_id: str = Field(min_length=1)
    action: str = Field(min_length=1)
    actor: str = Field(min_length=1)
    operation_id: str = Field(min_length=1)
    reason: Optional[str] = None
