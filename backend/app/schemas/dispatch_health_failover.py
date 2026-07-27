from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field

class DispatchHealthState(str, Enum):
    BLOCKED="blocked"; EVIDENCE_READY="evidence-ready"; HEALTHY="healthy"; DEGRADED="degraded"; REVIEW_REQUIRED="review-required"; APPROVED="approved"; FAILOVER_AUTHORIZED="failover-authorized"; REVOKED="revoked"; ARCHIVED="archived"

class DispatchHealthEvidence(BaseModel):
    primary_available: bool
    latency_ms: float = Field(ge=0)
    receipt_reconciliation: float = Field(ge=0, le=1)
    worker_heartbeat_ok: bool
    gateway_healthy: bool
    adapter_healthy: bool
    confidence: float = Field(default=1, ge=0, le=1)
    freshness: float = Field(default=1, ge=0, le=1)

class DispatchHealthCreate(BaseModel):
    workspace_id: str = Field(min_length=1)
    source_key: str = Field(min_length=1)
    requested_by: str = Field(min_length=1)
    dispatch_plan_id: str = Field(min_length=1)
    dispatch_plan_digest: str = Field(min_length=8)
    operation: str = Field(min_length=1)
    target: str = Field(min_length=1)
    primary_adapter_id: str = Field(min_length=1)
    primary_worker_id: str = Field(min_length=1)
    standby_adapter_id: str = Field(min_length=1)
    standby_worker_id: str = Field(min_length=1)
    max_latency_ms: float = Field(default=1500, gt=0)
    min_receipt_reconciliation: float = Field(default=.95, ge=0, le=1)
    upstream_risk_brain_blocked: bool = False
    evidence: DispatchHealthEvidence

class DispatchHealthScores(BaseModel):
    health_assurance: float = Field(ge=0, le=1)
    failover_confidence: float = Field(ge=0, le=1)
    residual_risk: float = Field(ge=0, le=1)

class DispatchHealthRecord(BaseModel):
    record_id: str; workspace_id: str; source_key: str; state: DispatchHealthState
    dispatch_plan_id: str; dispatch_plan_digest: str; operation: str; target: str
    primary_adapter_id: str; primary_worker_id: str; standby_adapter_id: str; standby_worker_id: str
    triggers: List[str] = Field(default_factory=list); scores: DispatchHealthScores
    evidence_digest: str; decision_digest: str
    approved_by: Optional[str] = None; version: int = 1

class DispatchHealthAction(BaseModel):
    workspace_id: str = Field(min_length=1)
    action: str = Field(min_length=1)
    actor: str = Field(min_length=1)
    operation_id: str = Field(min_length=1)
    reason: Optional[str] = None
