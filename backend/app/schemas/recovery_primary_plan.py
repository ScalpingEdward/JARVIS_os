from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field


class RecoveryPrimaryPlanState(str, Enum):
    BLOCKED = "blocked"
    DRAFT = "draft"
    PRECONDITION_READY = "precondition-ready"
    REVIEW_REQUIRED = "review-required"
    APPROVED = "approved"
    READY = "ready"
    REVOKED = "revoked"
    ARCHIVED = "archived"


class RecoveryPreconditions(BaseModel):
    primary_available: bool = True
    primary_healthy: bool = True
    primary_latency_ms: float = Field(ge=0)
    max_primary_latency_ms: float = Field(default=1500, gt=0)
    primary_receipt_reconciliation: float = Field(ge=0, le=1)
    min_primary_receipt_reconciliation: float = Field(default=.95, ge=0, le=1)
    failover_path_stable: bool = True
    no_open_side_effect_findings: bool = True
    confidence: float = Field(default=1, ge=0, le=1)
    freshness: float = Field(default=1, ge=0, le=1)


class RecoveryPrimaryPlanCreate(BaseModel):
    workspace_id: str = Field(min_length=1)
    source_key: str = Field(min_length=1)
    requested_by: str = Field(min_length=1)
    recovery_readiness_id: str = Field(min_length=1)
    recovery_readiness_digest: str = Field(min_length=8)
    dispatch_plan_id: str = Field(min_length=1)
    dispatch_plan_digest: str = Field(min_length=8)
    operation: str = Field(min_length=1)
    target: str = Field(min_length=1)
    primary_adapter_id: str = Field(min_length=1)
    primary_worker_id: str = Field(min_length=1)
    standby_adapter_id: str = Field(min_length=1)
    standby_worker_id: str = Field(min_length=1)
    gateway_id: str = Field(min_length=1)
    sandbox_policy_digest: str = Field(min_length=8)
    gateway_policy_digest: str = Field(min_length=8)
    worker_policy_digest: str = Field(min_length=8)
    preconditions: RecoveryPreconditions
    rollback_criteria: List[str] = Field(default_factory=lambda: [
        "primary-unavailable",
        "primary-latency-degraded",
        "primary-receipt-reconciliation-degraded",
        "primary-health-loss",
        "worker-heartbeat-loss",
        "gateway-health-loss",
    ])
    validation_checks: List[str] = Field(default_factory=lambda: [
        "primary-availability",
        "latency-threshold",
        "receipt-reconciliation",
        "worker-heartbeat",
        "gateway-health",
        "read-only-side-effect-attestation",
    ])
    upstream_risk_brain_blocked: bool = False


class RecoveryPrimaryPlanScores(BaseModel):
    precondition_assurance: float = Field(ge=0, le=1)
    rollback_readiness: float = Field(ge=0, le=1)
    validation_readiness: float = Field(ge=0, le=1)
    residual_risk: float = Field(ge=0, le=1)


class RecoveryPrimaryPlanRecord(BaseModel):
    record_id: str
    workspace_id: str
    source_key: str
    state: RecoveryPrimaryPlanState
    recovery_readiness_id: str
    recovery_readiness_digest: str
    dispatch_plan_id: str
    dispatch_plan_digest: str
    operation: str
    target: str
    primary_adapter_id: str
    primary_worker_id: str
    standby_adapter_id: str
    standby_worker_id: str
    gateway_id: str
    sandbox_policy_digest: str
    gateway_policy_digest: str
    worker_policy_digest: str
    rollback_criteria: List[str]
    validation_checks: List[str]
    precondition_failures: List[str]
    scores: RecoveryPrimaryPlanScores
    plan_digest: str
    approved_by: Optional[str] = None
    version: int = 1


class RecoveryPrimaryPlanAction(BaseModel):
    workspace_id: str = Field(min_length=1)
    action: str = Field(min_length=1)
    actor: str = Field(min_length=1)
    operation_id: str = Field(min_length=1)
    reason: Optional[str] = None
